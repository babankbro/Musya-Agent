"""Obsidian Knowledge Vault indexer.

Walks the vault directory, parses YAML frontmatter from each .md file,
and UPSERTs records into the obsidian_notes table.

Usage:
    python scripts/index_obsidian.py [vault_id]
    python scripts/index_obsidian.py health_region_10

Defaults to health_region_10 vault if no vault_id given.
"""
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow importing src.* from Agent/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # PyYAML — already in requirements via CrewAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("index_obsidian")

# ── Constants ──────────────────────────────────────────────────────────────────

KNOWN_PROVINCES = {
    "อุบลราชธานี", "ศรีสะเกษ", "ยโสธร", "อำนาจเจริญ", "มุกดาหาร",
}

# Map frontmatter tags → note_type
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_dict, body_without_frontmatter).
    """
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
    """Detect note_type from tags and filename."""
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
    # A file named exactly the same as its parent directory is typically a district stub
    if name == rel_path.parent.name:
        return "district"

    return "report"


def _extract_year(rel_path: Path, fm: dict) -> int | None:
    """Extract year (CE or BE) from filename or frontmatter."""
    # Check frontmatter
    for key in ("year", "ปี", "fiscal_year"):
        val = fm.get(key)
        if isinstance(val, int) and 2000 <= val <= 2100:
            return val if val < 2500 else val - 543  # convert BE to CE

    # Extract from filename
    name = str(rel_path.stem)
    matches = YEAR_PATTERN.findall(name)
    for m in reversed(matches):
        y = int(m)
        if 2500 <= y <= 2600:  # Thai BE year
            return y - 543
        if 2000 <= y <= 2100:  # CE year
            return y
    return None


def _extract_title(body: str, rel_path: Path) -> str:
    """Extract title from first H1 heading or filename."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return rel_path.stem


def _parse_province_district(rel_path: Path) -> tuple[str | None, str | None]:
    """Extract province and district from the relative path structure.

    Expected: province/district/note.md or province/note.md or note.md
    """
    parts = rel_path.parts
    province = None
    district = None

    for i, part in enumerate(parts[:-1]):  # exclude filename
        if part in KNOWN_PROVINCES:
            province = part
            if i + 1 < len(parts) - 1:
                district = parts[i + 1]
            break

    return province, district


# ── Core indexer ───────────────────────────────────────────────────────────────

def index_vault(vault_id: str = "health_region_10") -> dict:
    """Walk vault directory and UPSERT notes into obsidian_notes table.

    Returns a summary dict with inserted/updated/unchanged/errors counts.
    """
    from src.config import get_settings
    from src.db.pool import query_db, execute_db

    settings = get_settings()
    start = time.time()

    # Resolve vault path
    agent_root = Path(__file__).parent.parent
    vault_path_rel = settings.OBSIDIAN_VAULT_PATH  # e.g. "obsidian_knowledge"
    vault_root = agent_root / vault_path_rel

    if not vault_root.exists():
        raise FileNotFoundError(f"Vault directory not found: {vault_root}")

    # Get vault registry entry
    rows = query_db("SELECT vault_id, vault_path FROM obsidian_vaults WHERE vault_id = %s", (vault_id,))
    if not rows:
        raise ValueError(f"Vault '{vault_id}' not found in obsidian_vaults table. Run migration 025 first.")

    # Walk and process all .md files
    inserted = updated = unchanged = errors = 0
    total_files = 0

    md_files = list(vault_root.rglob("*.md"))
    logger.info("Found %d .md files in %s", len(md_files), vault_root)

    now = datetime.now(timezone.utc)

    for md_path in md_files:
        total_files += 1
        rel_path = md_path.relative_to(vault_root)

        try:
            raw_text = md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Cannot read %s: %s", md_path, e)
            errors += 1
            continue

        fm, body = _parse_frontmatter(raw_text)

        # Build metadata
        province, district = _parse_province_district(rel_path)
        note_type = _detect_note_type(rel_path, fm)
        year = _extract_year(rel_path, fm)
        title = _extract_title(body, rel_path)

        tags: list[str] = []
        raw_tags = fm.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags = [str(t) for t in raw_tags if t]

        source_file: str | None = fm.get("source") or fm.get("source_file")

        note_id = f"{vault_id}::{rel_path.as_posix()}"

        # Check if already exists with same content
        existing = query_db(
            "SELECT note_id FROM obsidian_notes WHERE note_id = %s AND content = %s",
            (note_id, raw_text),
        )
        if existing:
            unchanged += 1
            continue

        try:
            execute_db(
                """
                INSERT INTO obsidian_notes
                    (note_id, vault_id, relative_path, title, province, district,
                     note_type, tags, source_file, year, content, content_stripped, indexed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (note_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    province = EXCLUDED.province,
                    district = EXCLUDED.district,
                    note_type = EXCLUDED.note_type,
                    tags = EXCLUDED.tags,
                    source_file = EXCLUDED.source_file,
                    year = EXCLUDED.year,
                    content = EXCLUDED.content,
                    content_stripped = EXCLUDED.content_stripped,
                    indexed_at = EXCLUDED.indexed_at
                """,
                (
                    note_id, vault_id, str(rel_path.as_posix()),
                    title, province, district, note_type,
                    tags, source_file, year,
                    raw_text, body, now,
                ),
            )
            # Track insert vs update
            check = query_db(
                "SELECT note_id FROM obsidian_notes WHERE note_id = %s AND indexed_at >= %s",
                (note_id, now),
            )
            if check:
                inserted += 1
            else:
                updated += 1
            logger.debug("Indexed: %s [%s / %s]", note_id[:80], province, note_type)
        except Exception as e:
            logger.error("Error indexing %s: %s", note_id[:80], e)
            errors += 1
            continue

    # Update vault note_count and indexed_at
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
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info(
        "Indexing complete: inserted=%d updated=%d unchanged=%d errors=%d elapsed=%.1fs",
        inserted, updated, unchanged, errors, elapsed,
    )
    return summary


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    vault_id = sys.argv[1] if len(sys.argv) > 1 else "health_region_10"
    try:
        result = index_vault(vault_id)
        print(f"\n✅ Done: {result}")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
