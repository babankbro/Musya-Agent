"""Quick verification of obsidian_notes + obsidian_vaults tables."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import query_db

print("=== obsidian_vaults ===")
for row in query_db("SELECT vault_id, name, note_count, indexed_at FROM obsidian_vaults"):
    print(dict(row))

print("\n=== obsidian_notes summary ===")
r = query_db(
    "SELECT COUNT(*) as total, COUNT(DISTINCT province) as provinces, "
    "COUNT(DISTINCT note_type) as types FROM obsidian_notes WHERE vault_id=%s",
    ("health_region_10",),
)
print(dict(r[0]))

print("\n=== note_type breakdown ===")
for row in query_db(
    "SELECT note_type, COUNT(*) as cnt FROM obsidian_notes "
    "WHERE vault_id=%s GROUP BY note_type ORDER BY cnt DESC",
    ("health_region_10",),
):
    print(f"  {row['note_type'] or '(none)'}: {row['cnt']}")

print("\n=== province breakdown ===")
for row in query_db(
    "SELECT province, COUNT(*) as cnt FROM obsidian_notes "
    "WHERE vault_id=%s GROUP BY province ORDER BY cnt DESC",
    ("health_region_10",),
):
    print(f"  {row['province'] or '(none)'}: {row['cnt']}")
