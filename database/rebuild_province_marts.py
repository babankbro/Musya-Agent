"""
Rebuild province-level mart tables from real accident data.
Also fixes NULL geography_id in fact_accident_event using lat/lon → nearest province.

Run from project root:
    python database/rebuild_province_marts.py
"""
import csv
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DB_DSN = (
    f"host={os.getenv('DB_HOST','localhost')} "
    f"port={os.getenv('DB_PORT','5432')} "
    f"dbname={os.getenv('DB_NAME','chat-aio')} "
    f"user={os.getenv('DB_USER','postgres')} "
    f"password={os.getenv('DB_PASSWORD','1234')}"
)
CSV_DIR = Path(__file__).parent
CSV_FILES = [
    (CSV_DIR / "accident2023.csv", 2023),
    (CSV_DIR / "accident2024.csv", 2024),
    (CSV_DIR / "accident2025.csv", 2025),
]


def run():
    print("=" * 70)
    print("  Musya Agent — Rebuild Province Mart Tables")
    print("=" * 70)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ── Step 1: Fix NULL geography_id in fact_accident_event ─────────────────
    print("\n[1/4] Fixing NULL geography_id in fact_accident_event...")
    cur.execute("SELECT COUNT(*) FROM fact_accident_event WHERE geography_id IS NULL")
    null_count = cur.fetchone()[0]
    print(f"      Found {null_count} rows with NULL geography_id")

    if null_count > 0:
        # Load province coords from dim_geography
        cur.execute("SELECT geography_id, province_name, latitude, longitude FROM dim_geography")
        geo_rows = cur.fetchall()
        geo_map = {r["province_name"]: r["geography_id"] for r in geo_rows}

        # Load CSV to get province for each ACC_CODE
        acc_code_prov: dict[str, int] = {}
        for csv_path, year in CSV_FILES:
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    code = row["ACC_CODE"].strip()
                    prov = row["จังหวัด"].strip()
                    if code and prov and prov in geo_map:
                        acc_code_prov[code] = geo_map[prov]

        # Get NULL fact rows — update via acc_code stored in source
        # Since we don't store acc_code in fact, fix via position-based update
        # Use the datetime + road approach: match on event_datetime + road_segment
        # Simpler: re-import just the NULLs by setting geography from road_segment.geography_id
        cur.execute("""
            UPDATE fact_accident_event e
            SET geography_id = r.geography_id
            FROM dim_road_segment r
            WHERE e.road_segment_id = r.road_segment_id
              AND e.geography_id IS NULL
              AND r.geography_id IS NOT NULL
        """)
        fixed = cur.rowcount
        conn.commit()
        print(f"      Fixed {fixed} rows via road_segment.geography_id")

        cur.execute("SELECT COUNT(*) FROM fact_accident_event WHERE geography_id IS NULL")
        still_null = cur.fetchone()[0]
        if still_null > 0:
            print(f"      Still {still_null} NULL rows — these have no road or province data, leaving as NULL")
    else:
        print("      No NULL rows to fix.")

    # ── Step 2: Rebuild mart_province_year ────────────────────────────────────
    print("\n[2/4] Rebuilding mart_province_year...")
    cur.execute("TRUNCATE mart_province_year RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_province_year
            (year_no, geography_id, province_name,
             accident_count, injured_count, death_count,
             road_count, top_vehicle, top_cause, top_timeband, top_weather)
        SELECT
            EXTRACT(YEAR FROM e.event_datetime)::INT                     AS year_no,
            e.geography_id,
            g.province_name,
            COUNT(*)                                                      AS accident_count,
            SUM(e.injured_count)                                          AS injured_count,
            SUM(e.death_count)                                            AS death_count,
            COUNT(DISTINCT e.road_segment_id)                            AS road_count,
            MODE() WITHIN GROUP (ORDER BY e.vehicle_type)                AS top_vehicle,
            MODE() WITHIN GROUP (ORDER BY e.accident_type)               AS top_cause,
            MODE() WITHIN GROUP (ORDER BY
                CASE
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6  AND 11 THEN 'เช้า (06-12)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'กลางวัน (12-18)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 18 AND 23 THEN 'เย็น/กลางคืน (18-24)'
                    ELSE 'กลางคืน (00-06)'
                END
            )                                                             AS top_timeband,
            MODE() WITHIN GROUP (ORDER BY e.weather_condition)           AS top_weather
        FROM fact_accident_event e
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE e.event_datetime IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM e.event_datetime)::INT, e.geography_id, g.province_name
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_province_year")
    print(f"      {cur.fetchone()[0]} rows in mart_province_year.")

    # ── Step 3: Rebuild mart_province_road ────────────────────────────────────
    print("\n[3/4] Rebuilding mart_province_road...")
    cur.execute("TRUNCATE mart_province_road RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_province_road
            (year_no, geography_id, province_name, road_segment_id, road_name, road_code,
             accident_count, injured_count, death_count, hotspot_score,
             dominant_cause, dominant_vehicle)
        SELECT
            EXTRACT(YEAR FROM e.event_datetime)::INT                     AS year_no,
            e.geography_id,
            g.province_name,
            r.road_segment_id,
            r.road_name,
            r.road_code,
            COUNT(*)                                                      AS accident_count,
            SUM(e.injured_count)                                          AS injured_count,
            SUM(e.death_count)                                            AS death_count,
            COUNT(*) + SUM(e.death_count)*10 + SUM(e.injured_count)*2   AS hotspot_score,
            MODE() WITHIN GROUP (ORDER BY e.accident_type)               AS dominant_cause,
            MODE() WITHIN GROUP (ORDER BY e.vehicle_type)                AS dominant_vehicle
        FROM fact_accident_event e
        JOIN dim_geography g  ON e.geography_id  = g.geography_id
        JOIN dim_road_segment r ON e.road_segment_id = r.road_segment_id
        WHERE e.event_datetime IS NOT NULL
        GROUP BY
            EXTRACT(YEAR FROM e.event_datetime)::INT,
            e.geography_id, g.province_name,
            r.road_segment_id, r.road_name, r.road_code
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_province_road")
    print(f"      {cur.fetchone()[0]} rows in mart_province_road.")

    # ── Step 4: Rebuild mart_accident_summary (monthly) ──────────────────────
    print("\n[4/4] Rebuilding mart_accident_summary (monthly)...")
    cur.execute("TRUNCATE mart_accident_summary RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_accident_summary
            (year_no, month_no, geography_id, accident_count, injured_count, death_count,
             high_risk_timeband, dominant_road_cond)
        SELECT
            EXTRACT(YEAR  FROM e.event_datetime)::INT,
            EXTRACT(MONTH FROM e.event_datetime)::INT,
            e.geography_id,
            COUNT(*),
            SUM(e.injured_count),
            SUM(e.death_count),
            MODE() WITHIN GROUP (ORDER BY
                CASE
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6  AND 11 THEN 'เช้า (06-12)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'กลางวัน (12-18)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 18 AND 23 THEN 'เย็น/กลางคืน (18-24)'
                    ELSE 'กลางคืน (00-06)'
                END
            ),
            MODE() WITHIN GROUP (ORDER BY e.weather_condition)
        FROM fact_accident_event e
        WHERE e.event_datetime IS NOT NULL
          AND e.geography_id IS NOT NULL
        GROUP BY 1, 2, 3
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_accident_summary")
    print(f"      {cur.fetchone()[0]} rows in mart_accident_summary.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Final Row Counts:")
    for table in [
        "dim_geography", "dim_road_segment",
        "fact_accident_event",
        "mart_province_year", "mart_province_road",
        "mart_accident_summary", "mart_accident_hotspot",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"    {table:<35} {cur.fetchone()[0]:>8} rows")

    print("\n  Sample mart_province_year (top 5 provinces 2024):")
    cur.execute("""
        SELECT year_no, province_name, accident_count, death_count, road_count, top_vehicle
        FROM mart_province_year
        WHERE year_no = 2024
        ORDER BY accident_count DESC LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"    {r['year_no']} {r['province_name']}: "
              f"accidents={r['accident_count']}, deaths={r['death_count']}, "
              f"roads={r['road_count']}, top_vehicle={r['top_vehicle']}")

    print("\n  Sample mart_province_road (top 5 roads in เชียงใหม่ 2024):")
    cur.execute("""
        SELECT year_no, province_name, road_name, road_code,
               accident_count, death_count, hotspot_score
        FROM mart_province_road
        WHERE province_name = 'เชียงใหม่' AND year_no = 2024
        ORDER BY hotspot_score DESC LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"    {r['year_no']} {r['province_name']} | {r['road_name'][:45]} "
              f"({r['road_code']}): accidents={r['accident_count']}, score={r['hotspot_score']}")

    print("=" * 70)
    cur.close()
    conn.close()


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n  Total time: {time.time()-t0:.1f}s")
