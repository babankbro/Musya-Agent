#!/usr/bin/env python3
"""
Populate obsidian_pdf_assets.note_id FK using basename-matched source_file.

Strategy:
  strip path prefix from obsidian_notes.source_file  (handles PDF/province/file.pdf,
  C:\\Users\\...\\file.pdf, province/file.pdf patterns), then match against
  obsidian_pdf_assets.filename within the same province.

Safe to re-run — uses ON CONFLICT / WHERE note_id IS NULL guard.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "chat-aio")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

UPDATE_SQL = r"""
UPDATE obsidian_pdf_assets p
SET note_id = sub.note_id
FROM (
    SELECT DISTINCT ON (p2.id)
        p2.id      AS asset_id,
        n.note_id
    FROM obsidian_pdf_assets p2
    JOIN obsidian_notes n
      ON  n.province = p2.province
      AND regexp_replace(
              replace(n.source_file, '\', '/'),
              '^.*/', ''
          ) = p2.filename
    WHERE n.source_file IS NOT NULL
      AND n.source_file NOT LIKE '%.md'
    ORDER BY p2.id, n.note_id
) sub
WHERE p.id = sub.asset_id
  AND (p.note_id IS NULL OR p.note_id != sub.note_id);
"""

VERIFY_SQL = """
SELECT
    COUNT(*) FILTER (WHERE note_id IS NOT NULL)    AS linked,
    COUNT(*) FILTER (WHERE note_id IS NULL)        AS unlinked,
    COUNT(*)                                        AS total
FROM obsidian_pdf_assets;
"""

PROVINCE_SQL = """
SELECT p.province,
       COUNT(*) FILTER (WHERE p.note_id IS NOT NULL) AS linked,
       COUNT(*) FILTER (WHERE p.note_id IS NULL)     AS unlinked
FROM obsidian_pdf_assets p
GROUP BY p.province
ORDER BY p.province;
"""

print("=" * 60)
print("  Update obsidian_pdf_assets.note_id FK")
print("=" * 60)

try:
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Before
    cur.execute(VERIFY_SQL)
    before = cur.fetchone()
    print(f"\nBefore: linked={before[0]}  unlinked={before[1]}  total={before[2]}")

    print("Running UPDATE...")
    cur.execute(UPDATE_SQL)
    print(f"  Rows affected: {cur.rowcount}")

    # After
    cur.execute(VERIFY_SQL)
    after = cur.fetchone()
    print(f"After:  linked={after[0]}  unlinked={after[1]}  total={after[2]}")
    print(f"New links created: {after[0] - before[0]}")

    print("\nBy province:")
    cur.execute(PROVINCE_SQL)
    for row in cur.fetchall():
        pct = round(row[1] / (row[1]+row[2]) * 100) if (row[1]+row[2]) > 0 else 0
        print(f"  {row[0]:20s}  linked={row[1]:3d}  unlinked={row[2]:3d}  ({pct}%)")

    cur.close()
    conn.close()
    print("\n✅ Done.")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    sys.exit(1)
