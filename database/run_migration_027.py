#!/usr/bin/env python3
"""Apply migration 027: Obsidian PDF Assets table."""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "chat-aio")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

sql_file = Path(__file__).parent / "027_obsidian_pdf_assets.sql"

print("=" * 60)
print("  Migration 027 — Obsidian PDF Assets")
print("=" * 60)
print(f"  DB   : {DB_NAME} @ {DB_HOST}:{DB_PORT}")
print(f"  File : {sql_file.name}")
print()

sql = sql_file.read_text(encoding="utf-8")

try:
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Executing SQL...")
    cur.execute(sql)
    print("SQL executed successfully.")

    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'obsidian_pdf_assets'"
    )
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTable confirmed: {tables}")

    cur.execute(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename = 'obsidian_pdf_assets' "
        "ORDER BY indexname"
    )
    indexes = [r[0] for r in cur.fetchall()]
    print(f"Indexes confirmed: {indexes}")

    cur.close()
    conn.close()
    print("\n✅ Migration 027 complete.")

except psycopg2.Error as e:
    print(f"\n✗ ERROR: {e}")
    sys.exit(1)
