"""Export Obsidian Knowledge Vault data from PostgreSQL.

Outputs two files in the export directory:
  obsidian_vaults.json   — vault metadata
  obsidian_notes.json    — all indexed notes (full content)

Usage:
  python scripts/export_obsidian.py
  python scripts/export_obsidian.py --vault health_region_10 --out exports/obsidian
  python scripts/export_obsidian.py --no-content   # skip full markdown (smaller file)
"""
import argparse
import json
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _json_serial(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def export_obsidian(vault_id: str = "health_region_10", out_dir: str = "exports/obsidian", include_content: bool = True):
    from src.db.pool import query_db

    os.makedirs(out_dir, exist_ok=True)

    # ── Export obsidian_vaults ─────────────────────────────────────────────────
    vaults = query_db(
        "SELECT vault_id, name, vault_path, description, note_count, indexed_at, created_at "
        "FROM obsidian_vaults WHERE vault_id = %s",
        (vault_id,),
    )
    if not vaults:
        print(f"❌ Vault '{vault_id}' not found in obsidian_vaults.")
        sys.exit(1)

    vaults_data = [dict(row) for row in vaults]
    vaults_path = os.path.join(out_dir, "obsidian_vaults.json")
    with open(vaults_path, "w", encoding="utf-8") as f:
        json.dump(vaults_data, f, ensure_ascii=False, indent=2, default=_json_serial)
    print(f"✅ Exported {len(vaults_data)} vault(s) → {vaults_path}")

    # ── Export obsidian_notes ──────────────────────────────────────────────────
    if include_content:
        cols = "note_id, vault_id, relative_path, title, province, district, note_type, tags, source_file, year, content, content_stripped, indexed_at"
    else:
        cols = "note_id, vault_id, relative_path, title, province, district, note_type, tags, source_file, year, indexed_at"

    notes = query_db(
        f"SELECT {cols} FROM obsidian_notes WHERE vault_id = %s ORDER BY province, district, title",
        (vault_id,),
    )
    notes_data = [dict(row) for row in notes]
    notes_path = os.path.join(out_dir, "obsidian_notes.json")
    with open(notes_path, "w", encoding="utf-8") as f:
        json.dump(notes_data, f, ensure_ascii=False, indent=2, default=_json_serial)

    size_kb = os.path.getsize(notes_path) / 1024
    print(f"✅ Exported {len(notes_data)} notes → {notes_path} ({size_kb:.1f} KB)")

    # ── Write summary ──────────────────────────────────────────────────────────
    summary = {
        "exported_at": datetime.now().isoformat(),
        "vault_id": vault_id,
        "total_notes": len(notes_data),
        "include_content": include_content,
        "files": {
            "vaults": "obsidian_vaults.json",
            "notes": "obsidian_notes.json",
        },
        "province_counts": {},
        "type_counts": {},
    }
    for note in notes_data:
        prov = note.get("province") or "(none)"
        summary["province_counts"][prov] = summary["province_counts"].get(prov, 0) + 1
        ntype = note.get("note_type") or "(none)"
        summary["type_counts"][ntype] = summary["type_counts"].get(ntype, 0) + 1

    summary_path = os.path.join(out_dir, "export_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n📋 Export summary → {summary_path}")
    print(f"   Total notes : {summary['total_notes']}")
    print(f"   Provinces   : {dict(sorted(summary['province_counts'].items(), key=lambda x: -x[1]))}")
    print(f"   Types       : {dict(sorted(summary['type_counts'].items(), key=lambda x: -x[1]))}")
    print(f"\n📁 Output directory: {os.path.abspath(out_dir)}")
    print("   Files:")
    print(f"     obsidian_vaults.json  — vault metadata")
    print(f"     obsidian_notes.json   — {len(notes_data)} notes {'(full content)' if include_content else '(metadata only)'}")
    print(f"     export_summary.json   — summary")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Obsidian Knowledge Vault from PostgreSQL")
    parser.add_argument("--vault", default="health_region_10", help="Vault ID to export (default: health_region_10)")
    parser.add_argument("--out", default="exports/obsidian", help="Output directory (default: exports/obsidian)")
    parser.add_argument("--no-content", action="store_true", help="Skip full markdown content (metadata only, smaller file)")
    args = parser.parse_args()

    export_obsidian(
        vault_id=args.vault,
        out_dir=args.out,
        include_content=not args.no_content,
    )
