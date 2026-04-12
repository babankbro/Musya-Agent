"""Run migration 007 against the database."""
import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

dsn = (
    f"host={os.getenv('DB_HOST','localhost')} "
    f"port={os.getenv('DB_PORT','5432')} "
    f"dbname={os.getenv('DB_NAME','chat-aio')} "
    f"user={os.getenv('DB_USER','postgres')} "
    f"password={os.getenv('DB_PASSWORD','1234')}"
)

sql = (Path(__file__).parent / "007_all_years_province.sql").read_text(encoding="utf-8")

conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
print("Migration 007 applied successfully.")

cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='fact_accident_event' ORDER BY ordinal_position"
)
print("fact_accident_event columns:", [r[0] for r in cur.fetchall()])

cur.execute(
    "SELECT table_name FROM information_schema.views "
    "WHERE table_name LIKE 'v_province%'"
)
print("Province views:", [r[0] for r in cur.fetchall()])

conn.close()
