"""Run a SQL migration file using the app's DB pool."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import execute_db, query_db

sql_file = sys.argv[1] if len(sys.argv) > 1 else None
if not sql_file:
    print("Usage: python scripts/run_migration.py <file.sql>")
    sys.exit(1)

with open(sql_file, encoding="utf-8") as f:
    sql = f.read()

print(f"Running migration: {sql_file}")
try:
    execute_db(sql)
    print("Migration applied.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

# Verify thaijo_search_cache exists if that's what we just created
rows = query_db(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_name = 'thaijo_search_cache' AND table_schema = 'public'"
)
if rows:
    print("Verified: table 'thaijo_search_cache' exists.")
    idx = query_db(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename = 'thaijo_search_cache'"
    )
    for r in idx:
        print(f"  index: {r['indexname']}")
else:
    print("Table 'thaijo_search_cache' NOT found — migration may have failed or table name differs.")
