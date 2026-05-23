"""Import Obsidian Knowledge Vault data from a JSON export dump.

Reads obsidian_vaults.json + obsidian_notes.json produced by export_obsidian.py
and UPSERTs them into the target PostgreSQL database.

Usage:
  python scripts/import_obsidian_dump.py
  python scripts/import_obsidian_dump.py --src exports/obsidian
  python scripts/import_obsidian_dump.py --src exports/obsidian --vault health_region_10
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def import_obsidian_dump(src_dir: str = "exports/obsidian", vault_id: str | None = None):
    from src.db.pool import execute_db, query_db

    vaults_path = os.path.join(src_dir, "obsidian_vaults.json")
    notes_path  = os.path.join(src_dir, "obsidian_notes.json")

    if not os.path.exists(vaults_path):
        print(f"❌ Not found: {vaults_path}")
        sys.exit(1)
    if not os.path.exists(notes_path):
        print(f"❌ Not found: {notes_path}")
        sys.exit(1)

    with open(vaults_path, encoding="utf-8") as f:
        vaults = json.load(f)
    with open(notes_path, encoding="utf-8") as f:
        notes = json.load(f)

    # Filter by vault_id if specified
    if vault_id:
        vaults = [v for v in vaults if v["vault_id"] == vault_id]
        notes  = [n for n in notes  if n["vault_id"] == vault_id]

    if not vaults:
        print(f"❌ No vault data found for vault_id={vault_id!r}")
        sys.exit(1)

    print(f"📦 Source : {os.path.abspath(src_dir)}")
    print(f"   Vaults : {len(vaults)}")
    print(f"   Notes  : {len(notes)}")

    # ── Upsert vaults ──────────────────────────────────────────────────────────
    vault_ok = 0
    for v in vaults:
        execute_db(
            """
            INSERT INTO obsidian_vaults (vault_id, name, vault_path, description, note_count, indexed_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (vault_id) DO UPDATE SET
                name        = EXCLUDED.name,
                vault_path  = EXCLUDED.vault_path,
                description = EXCLUDED.description,
                note_count  = EXCLUDED.note_count,
                indexed_at  = EXCLUDED.indexed_at
            """,
            (
                v["vault_id"],
                v["name"],
                v["vault_path"],
                v.get("description"),
                v.get("note_count", 0),
                v.get("indexed_at"),
                v.get("created_at"),
            ),
        )
        vault_ok += 1
    print(f"✅ Upserted {vault_ok} vault row(s)")

    # ── Upsert notes ───────────────────────────────────────────────────────────
    inserted = updated = errors = 0
    for note in notes:
        try:
            has_content = "content" in note
            if has_content:
                execute_db(
                    """
                    INSERT INTO obsidian_notes
                        (note_id, vault_id, relative_path, title, province, district,
                         note_type, tags, source_file, year, content, content_stripped, indexed_at)
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
                        note["note_id"], note["vault_id"], note["relative_path"],
                        note.get("title"), note.get("province"), note.get("district"),
                        note.get("note_type"), note.get("tags", []), note.get("source_file"),
                        note.get("year"), note.get("content"), note.get("content_stripped"),
                        note.get("indexed_at"),
                    ),
                )
            else:
                execute_db(
                    """
                    INSERT INTO obsidian_notes
                        (note_id, vault_id, relative_path, title, province, district,
                         note_type, tags, source_file, year, indexed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (note_id) DO UPDATE SET
                        title       = EXCLUDED.title,
                        province    = EXCLUDED.province,
                        district    = EXCLUDED.district,
                        note_type   = EXCLUDED.note_type,
                        tags        = EXCLUDED.tags,
                        source_file = EXCLUDED.source_file,
                        year        = EXCLUDED.year,
                        indexed_at  = EXCLUDED.indexed_at
                    """,
                    (
                        note["note_id"], note["vault_id"], note["relative_path"],
                        note.get("title"), note.get("province"), note.get("district"),
                        note.get("note_type"), note.get("tags", []), note.get("source_file"),
                        note.get("year"), note.get("indexed_at"),
                    ),
                )
            inserted += 1
        except Exception as e:
            print(f"  ⚠️  Error on note_id={note.get('note_id', '?')}: {e}")
            errors += 1

    print(f"✅ Notes upserted: {inserted}  errors: {errors}")

    # ── Final count ────────────────────────────────────────────────────────────
    rows = query_db(
        "SELECT note_count FROM obsidian_vaults WHERE vault_id = %s",
        (vaults[0]["vault_id"],),
    )
    print(f"\n📊 obsidian_vaults.note_count = {rows[0]['note_count'] if rows else 'n/a'}")
    print("   (Run scripts/index_obsidian.py to refresh note_count if needed)")
    return {"imported": inserted, "errors": errors}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Obsidian dump into PostgreSQL")
    parser.add_argument("--src", default="exports/obsidian", help="Source directory (default: exports/obsidian)")
    parser.add_argument("--vault", default=None, help="Filter by vault_id (default: all vaults in dump)")
    args = parser.parse_args()

    import_obsidian_dump(src_dir=args.src, vault_id=args.vault)
