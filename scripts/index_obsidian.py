"""Obsidian Knowledge Vault indexer — hybrid edition.

Walks the vault directory, parses YAML frontmatter from each .md file,
and UPSERTs into three tables:
  - obsidian_notes       : one row per .md file (metadata + full content)
  - obsidian_note_chunks : one row per ## section (for precise snippet matching)
  - obsidian_note_links  : one row per resolved [[wikilink]] edge (for graph expansion)

Usage:
    python scripts/index_obsidian.py [vault_id]
    python scripts/index_obsidian.py health_region_10
"""
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("index_obsidian")

# ── Constants ──────────────────────────────────────────────────────────────────

KNOWN_PROVINCES = {
    "อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร",
}

TAG_TO_TYPE: dict[str, str] = {
    "MOC": "MOC",
    "HealthRegion10": "MOC",
    "PDF": "report",
    "Ingest": "report",
    "คปสอ": "report",
    "ตรวจราชการ": "report",
    "แผนปฏิบัติการ": "policy",
    "นโยบาย": "policy",
    "วิจัย": "research",
    "Research": "research",
}

YEAR_PATTERN = re.compile(r"(\d{4})")
WIKILINK_RE  = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
H2_SPLIT_RE  = re.compile(r"\n(?=## )")


# ── Pure parsing helpers (importable by tests) ─────────────────────────────────

def split_chunks(body: str) -> list[tuple[int, str | None, str]]:
    """Split a markdown body into (chunk_index, header, content) tuples.

    Splits on H2 (##) headers only.  The intro block (everything before the
    first ##) is index 0 with header=None.  Empty chunks are kept so that
    chunk_index stays stable across re-index runs.

    Returns:
        List of (chunk_index, header_text_or_None, chunk_body).
    """
    sections = H2_SPLIT_RE.split(body)
    chunks: list[tuple[int, str | None, str]] = []

    for i, section in enumerate(sections):
        if i == 0:
            # Everything before the first ## — may be empty for notes that
            # start immediately with a heading.
            chunks.append((0, None, section.strip()))
        else:
            # section starts with "## Some Header\n..."
            first_newline = section.find("\n")
            if first_newline == -1:
                header = section.lstrip("#").strip()
                content = ""
            else:
                header = section[:first_newline].lstrip("#").strip()
                content = section[first_newline + 1:].strip()
            chunks.append((i, header, content))

    return chunks


def parse_wikilinks(body: str) -> list[str]:
    """Return de-duplicated list of wikilink target stems from a markdown body.

    Handles:
        [[Note Name]]           → "Note Name"
        [[Note Name|Display]]   → "Note Name"  (stem before the pipe)
        [[Folder/Note]]         → "Folder/Note"

    Strips leading/trailing whitespace from each stem.
    """
    seen: set[str] = set()
    stems: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        stem = m.group(1).strip()
        if stem and stem not in seen:
            seen.add(stem)
            stems.append(stem)
    return stems


# ── Metadata helpers ───────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_yaml = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        fm = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _detect_note_type(rel_path: Path, fm: dict) -> str:
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        t = TAG_TO_TYPE.get(str(tag))
        if t:
            return t
    name = rel_path.stem
    if name.startswith(("ULTRA_DETAILED", "MASTER_")):
        return "report"
    if name.startswith("000_"):
        return "MOC"
    if name.startswith(("สรุปผลการดำเนินงาน", "สรุปงานวิจัย")):
        return "report"
    if name == rel_path.parent.name:
        return "district"
    return "report"


def _extract_year(rel_path: Path, fm: dict) -> int | None:
    for key in ("year", "ปี", "fiscal_year"):
        val = fm.get(key)
        if isinstance(val, int) and 2000 <= val <= 2100:
            return val if val < 2500 else val - 543
    name = str(rel_path.stem)
    for m in reversed(YEAR_PATTERN.findall(name)):
        y = int(m)
        if 2500 <= y <= 2600:
            return y - 543
        if 2000 <= y <= 2100:
            return y
    return None


def _extract_title(body: str, rel_path: Path) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return rel_path.stem


def _parse_province_district(rel_path: Path) -> tuple[str | None, str | None]:
    parts = rel_path.parts
    province = district = None
    for i, part in enumerate(parts[:-1]):
        if part in KNOWN_PROVINCES:
            province = part
            if i + 1 < len(parts) - 1:
                district = parts[i + 1]
            break
    return province, district


# ── Core indexer ───────────────────────────────────────────────────────────────

def index_vault(vault_id: str = "health_region_10") -> dict:
    """Walk vault and UPSERT notes, chunks, and wikilink edges into PostgreSQL.

    Three-phase execution:
      Phase 1 — Build stem→note_id map (needed for link resolution)
      Phase 2 — UPSERT notes + chunks
      Phase 3 — UPSERT wikilink edges (all targets must exist first)

    Returns summary dict with counts for each table.
    """
    from src.config import get_settings
    from src.db.pool import query_db, execute_db

    settings = get_settings()
    start = time.time()

    agent_root = Path(__file__).parent.parent
    vault_root = agent_root / settings.OBSIDIAN_VAULT_PATH

    if not vault_root.exists():
        raise FileNotFoundError(f"Vault directory not found: {vault_root}")

    rows = query_db(
        "SELECT vault_id FROM obsidian_vaults WHERE vault_id = %s", (vault_id,)
    )
    if not rows:
        raise ValueError(
            f"Vault '{vault_id}' not found in obsidian_vaults table. "
            "Run migration 025 first."
        )

    md_files = list(vault_root.rglob("*.md"))
    logger.info("Found %d .md files in %s", len(md_files), vault_root)

    # ── Detect hybrid table availability (migration 026) ──────────────────────
    def _table_exists(table: str) -> bool:
        try:
            query_db(f"SELECT 1 FROM {table} LIMIT 0", ())
            return True
        except Exception:
            return False

    chunks_table = _table_exists("obsidian_note_chunks")
    links_table  = _table_exists("obsidian_note_links")

    if not chunks_table:
        logger.warning(
            "obsidian_note_chunks not found — chunk indexing skipped. "
            "Run database/026_obsidian_hybrid.sql to enable hybrid search."
        )
    if not links_table:
        logger.warning(
            "obsidian_note_links not found — wikilink indexing skipped. "
            "Run database/026_obsidian_hybrid.sql to enable graph expansion."
        )

    # ── Phase 1: Build stem → note_id map ─────────────────────────────────────
    stem_to_note_id: dict[str, str] = {}
    for md_path in md_files:
        rel = md_path.relative_to(vault_root)
        note_id = f"{vault_id}::{rel.as_posix()}"
        stem = md_path.stem
        stem_to_note_id[stem] = note_id
        # Also register short last-segment path for wikilinks like [[Folder/Note]]
        stem_to_note_id[rel.as_posix().replace(".md", "")] = note_id

    logger.info("Built stem map with %d entries", len(stem_to_note_id))

    # ── Phase 2: UPSERT notes + chunks ────────────────────────────────────────
    now = datetime.now(timezone.utc)
    inserted = updated = unchanged = errors = 0
    chunks_written = 0
    total_files = 0

    for md_path in md_files:
        total_files += 1
        rel_path = md_path.relative_to(vault_root)
        note_id = f"{vault_id}::{rel_path.as_posix()}"

        try:
            raw_text = md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Cannot read %s: %s", md_path, e)
            errors += 1
            continue

        fm, body = _parse_frontmatter(raw_text)
        province, district = _parse_province_district(rel_path)
        note_type = _detect_note_type(rel_path, fm)
        year = _extract_year(rel_path, fm)
        title = _extract_title(body, rel_path)

        raw_tags = fm.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags = [str(t) for t in raw_tags if t]
        source_file: str | None = fm.get("source") or fm.get("source_file")

        # Skip if content unchanged AND chunks already exist for this note.
        # We must NOT skip when chunks_table is new (post-026 first run) because
        # notes already in obsidian_notes would never get their chunks written.
        existing = query_db(
            "SELECT note_id FROM obsidian_notes WHERE note_id = %s AND content = %s",
            (note_id, raw_text),
        )
        if existing:
            if chunks_table:
                has_chunks = bool(query_db(
                    "SELECT 1 FROM obsidian_note_chunks WHERE note_id = %s LIMIT 1",
                    (note_id,),
                ))
                if has_chunks:
                    unchanged += 1
                    continue
                # chunks missing for this note — fall through to write them
            else:
                unchanged += 1
                continue

        try:
            # UPSERT note
            is_new = not bool(
                query_db("SELECT 1 FROM obsidian_notes WHERE note_id = %s", (note_id,))
            )
            execute_db(
                """
                INSERT INTO obsidian_notes
                    (note_id, vault_id, relative_path, title, province, district,
                     note_type, tags, source_file, year, content, content_stripped,
                     indexed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (note_id) DO UPDATE SET
                    title            = EXCLUDED.title,
                    province         = EXCLUDED.province,
                    district         = EXCLUDED.district,
                    note_type        = EXCLUDED.note_type,
                    tags             = EXCLUDED.tags,
                    source_file      = EXCLUDED.source_file,
                    year             = EXCLUDED.year,
                    content          = EXCLUDED.content,
                    content_stripped = EXCLUDED.content_stripped,
                    indexed_at       = EXCLUDED.indexed_at
                """,
                (
                    note_id, vault_id, rel_path.as_posix(),
                    title, province, district, note_type,
                    tags, source_file, year,
                    raw_text, body, now,
                ),
            )

            # Replace chunks (delete old, insert new) — only if table exists
            if chunks_table:
                execute_db(
                    "DELETE FROM obsidian_note_chunks WHERE note_id = %s", (note_id,)
                )
                for idx, header, content in split_chunks(body):
                    if not content.strip():
                        continue  # skip empty sections
                    chunk_id = f"{note_id}::{idx}"
                    execute_db(
                        """
                        INSERT INTO obsidian_note_chunks
                            (chunk_id, note_id, chunk_index, header, chunk_content, indexed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            header        = EXCLUDED.header,
                            chunk_content = EXCLUDED.chunk_content,
                            indexed_at    = EXCLUDED.indexed_at
                        """,
                        (chunk_id, note_id, idx, header, content, now),
                    )
                    chunks_written += 1

            if is_new:
                inserted += 1
            else:
                updated += 1

            logger.debug(
                "Indexed: %s [%s / %s]", note_id[:80], province, note_type
            )

        except Exception as e:
            logger.error("Error indexing %s: %s", note_id[:80], e)
            errors += 1

    logger.info(
        "Phase 2 done: inserted=%d updated=%d unchanged=%d errors=%d chunks=%d",
        inserted, updated, unchanged, errors, chunks_written,
    )

    # ── Phase 3: Resolve + UPSERT wikilink edges ───────────────────────────────
    links_written = link_errors = 0

    if links_table:
        for md_path in md_files:
            rel_path = md_path.relative_to(vault_root)
            source_note_id = f"{vault_id}::{rel_path.as_posix()}"

            try:
                raw_text = md_path.read_text(encoding="utf-8")
            except Exception:
                continue

            _, body = _parse_frontmatter(raw_text)
            stems = parse_wikilinks(body)

            if not stems:
                continue

            # Remove all existing outgoing links from this note before re-inserting
            execute_db(
                "DELETE FROM obsidian_note_links WHERE source_note_id = %s",
                (source_note_id,),
            )

            for stem in stems:
                target_note_id = stem_to_note_id.get(stem)
                if not target_note_id:
                    continue  # unresolvable link (external or not-yet-indexed)
                if target_note_id == source_note_id:
                    continue  # self-link, skip
                try:
                    execute_db(
                        """
                        INSERT INTO obsidian_note_links
                            (source_note_id, target_note_id, link_text)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (source_note_id, target_note_id, stem),
                    )
                    links_written += 1
                except Exception as e:
                    logger.debug("Link error %s→%s: %s", source_note_id[:40], stem, e)
                    link_errors += 1

    logger.info(
        "Phase 3 done: links_written=%d link_errors=%d", links_written, link_errors
    )

    # ── Update vault stats ─────────────────────────────────────────────────────
    execute_db(
        "UPDATE obsidian_vaults SET note_count = %s, indexed_at = %s WHERE vault_id = %s",
        (inserted + updated + unchanged, now, vault_id),
    )

    elapsed = time.time() - start
    summary = {
        "vault_id": vault_id,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "errors": errors,
        "total_files": total_files,
        "chunks_written": chunks_written,
        "links_written": links_written,
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info(
        "Index complete in %.1fs: notes=%d chunks=%d links=%d",
        elapsed,
        inserted + updated + unchanged,
        chunks_written,
        links_written,
    )
    return summary


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    vault_id = sys.argv[1] if len(sys.argv) > 1 else "health_region_10"
    try:
        result = index_vault(vault_id)
        print(f"\n✅ Done:")
        for k, v in result.items():
            print(f"   {k}: {v}")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
