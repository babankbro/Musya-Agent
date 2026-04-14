import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncpg
from src.config import get_settings

async def main():
    s = get_settings()
    conn = await asyncpg.connect(
        host=s.DB_HOST, port=s.DB_PORT,
        database=s.DB_NAME, user=s.DB_USER, password=s.DB_PASSWORD
    )
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    print(f"Total tables: {len(rows)}")
    for r in rows:
        print(f"  {r['table_name']}")
    await conn.close()

asyncio.run(main())
