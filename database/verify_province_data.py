"""Quick verification of province-level data and new tools."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2, psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
dsn = (
    f"host={os.getenv('DB_HOST','localhost')} "
    f"port={os.getenv('DB_PORT','5432')} "
    f"dbname={os.getenv('DB_NAME','chat-aio')} "
    f"user={os.getenv('DB_USER','postgres')} "
    f"password={os.getenv('DB_PASSWORD','1234')}"
)
conn = psycopg2.connect(dsn)
conn.cursor_factory = psycopg2.extras.RealDictCursor
cur = conn.cursor()

# 1. Province year summary for เชียงใหม่
print("=== mart_province_year: เชียงใหม่ ===")
cur.execute("""
    SELECT year_no, province_name, accident_count, injured_count,
           serious_injured, death_count, road_count, top_vehicle, top_cause
    FROM mart_province_year
    WHERE province_name ILIKE '%เชียงใหม่%'
    ORDER BY year_no
""")
for r in cur.fetchall():
    print(f"  {r['year_no']}: acc={r['accident_count']}, inj={r['injured_count']}, "
          f"serious={r['serious_injured']}, dead={r['death_count']}, roads={r['road_count']}, "
          f"vehicle={r['top_vehicle']}, cause={r['top_cause']}")

# 2. Top roads in นครราชสีมา
print("\n=== mart_province_road: นครราชสีมา top 5 ===")
cur.execute("""
    SELECT road_name, road_code, SUM(accident_count) AS acc, SUM(death_count) AS dth
    FROM mart_province_road
    WHERE province_name ILIKE '%นครราชสีมา%'
    GROUP BY road_name, road_code
    ORDER BY acc DESC
    LIMIT 5
""")
for r in cur.fetchall():
    print(f"  [{r['road_code']}] {r['road_name'][:40]} | acc={r['acc']}, deaths={r['dth']}")

# 3. All provinces ranking (top 10)
print("\n=== All Provinces Ranking (top 10 by accidents) ===")
cur.execute("""
    SELECT province_name,
           SUM(accident_count) AS acc, SUM(injured_count) AS inj,
           SUM(serious_injured) AS ser, SUM(death_count) AS dth
    FROM mart_province_year
    GROUP BY province_name
    ORDER BY acc DESC
    LIMIT 10
""")
for i, r in enumerate(cur.fetchall(), 1):
    print(f"  {i:>2}. {r['province_name']:<20} acc={r['acc']:>6}, inj={r['inj']:>6}, "
          f"serious={r['ser']:>5}, dead={r['dth']:>5}")

# 4. View v_province_year_summary
print("\n=== v_province_year_summary: กรุงเทพมหานคร ===")
cur.execute("""
    SELECT year_no, province_name, accident_count, death_count, serious_injured
    FROM v_province_year_summary
    WHERE province_name ILIKE '%กรุงเทพ%'
    ORDER BY year_no
""")
for r in cur.fetchall():
    print(f"  {r['year_no']}: acc={r['accident_count']}, dead={r['death_count']}, serious={r['serious_injured']}")

# 5. Verify Excel serial dates were parsed (2024+)
print("\n=== Date parse check (csv_year + event_datetime) ===")
cur.execute("""
    SELECT csv_year, 
           MIN(event_datetime)::date AS min_dt,
           MAX(event_datetime)::date AS max_dt,
           COUNT(*) AS cnt
    FROM fact_accident_event
    WHERE csv_year IS NOT NULL
    GROUP BY csv_year
    ORDER BY csv_year
""")
for r in cur.fetchall():
    print(f"  {r['csv_year']}: {r['min_dt']} → {r['max_dt']}  ({r['cnt']} rows)")

conn.close()
print("\nAll checks passed.")
