"""
Import real accident data from CSV files (2023, 2024, 2025) into the Agent database.

Run from the Agent project root:
    python database/import_csv.py
"""
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running from project root or from database/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
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
BATCH_SIZE = 500


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_int(val, default=0):
    try:
        return int(val) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def parse_datetime(date_str, time_str):
    """Parse Thai CSV date/time into datetime object."""
    try:
        return datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%m/%d/%Y %H:%M")
    except Exception:
        try:
            return datetime.strptime(date_str.strip(), "%m/%d/%Y")
        except Exception:
            return None


def severity(death, injured):
    if death > 0:
        return "เสียชีวิต"
    elif injured > 0:
        return "บาดเจ็บ"
    return "รอดปลอดภัย"


def timeband(dt):
    """Return Thai timeband label from datetime."""
    if dt is None:
        return "ไม่ทราบ"
    h = dt.hour
    if 6 <= h < 12:
        return "เช้า (06-12)"
    elif 12 <= h < 18:
        return "กลางวัน (12-18)"
    elif 18 <= h < 24:
        return "เย็น/กลางคืน (18-24)"
    else:
        return "กลางคืน (00-06)"


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("=" * 65)
    print("  Musya Agent — Import Real Accident CSV Data")
    print("=" * 65)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Step 1: Truncate existing mockup data ────────────────────────────────
    print("\n[1/6] Truncating existing data...")
    cur.execute("TRUNCATE mart_accident_hotspot, mart_accident_summary, fact_accident_person, fact_accident_event, dim_road_segment RESTART IDENTITY CASCADE")
    conn.commit()
    print("      Done.")

    # ── Step 2: Upsert data source entries ───────────────────────────────────
    print("\n[2/6] Upserting dim_source...")
    source_ids = {}
    for _, year in CSV_FILES:
        cur.execute("""
            INSERT INTO dim_source (source_name, source_type, owner_org, update_frequency, quality_level)
            VALUES (%s, 'csv', 'กรมทางหลวงชนบท', 'yearly', 'official')
            ON CONFLICT DO NOTHING
            RETURNING source_id
        """, (f"accident{year}.csv",))
        row = cur.fetchone()
        if row:
            source_ids[year] = row[0]
        else:
            cur.execute("SELECT source_id FROM dim_source WHERE source_name = %s", (f"accident{year}.csv",))
            source_ids[year] = cur.fetchone()[0]
    conn.commit()
    print(f"      source_ids: {source_ids}")

    # ── Step 3: Collect provinces → upsert dim_geography ────────────────────
    print("\n[3/6] Building dim_geography from provinces...")
    province_coords: dict[str, tuple[float, float]] = {}
    for csv_path, year in CSV_FILES:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                prov = row["จังหวัด"].strip()
                if prov and prov not in province_coords:
                    try:
                        lat = float(row["LATITUDE"])
                        lon = float(row["LONGITUDE"])
                        province_coords[prov] = (lat, lon)
                    except (ValueError, TypeError):
                        province_coords.setdefault(prov, (0.0, 0.0))

    geo_id_map: dict[str, int] = {}
    for prov, (lat, lon) in province_coords.items():
        cur.execute("""
            INSERT INTO dim_geography (province_name, latitude, longitude, country_code)
            VALUES (%s, %s, %s, 'TH')
            ON CONFLICT DO NOTHING
            RETURNING geography_id
        """, (prov, lat, lon))
        row = cur.fetchone()
        if row:
            geo_id_map[prov] = row[0]
        else:
            cur.execute("SELECT geography_id FROM dim_geography WHERE province_name = %s", (prov,))
            geo_id_map[prov] = cur.fetchone()[0]
    conn.commit()
    print(f"      {len(geo_id_map)} provinces in dim_geography.")

    # ── Step 4: Collect road segments → upsert dim_road_segment ─────────────
    # Key: (road_code, province) for uniqueness; fall back to (road_name, province)
    print("\n[4/6] Building dim_road_segment (with road_code + geography_id)...")
    # road_key → dict of attributes
    road_segments: dict[tuple, dict] = {}
    for csv_path, year in CSV_FILES:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                road_name = row["สายทาง"].strip()
                road_code = row["รหัสสายทาง"].strip()
                prov = row["จังหวัด"].strip()
                # Use (road_code, province) as key when code available, else (road_name, province)
                key = (road_code if road_code else road_name, prov)
                if key not in road_segments:
                    road_segments[key] = {
                        "road_name": road_name or road_code or "ไม่ทราบ",
                        "road_code": road_code or None,
                        "road_type": row["หน่วยงาน"].strip() or "ไม่ทราบ",
                        "curvature_type": row["บริเวณที่เกิดเหตุ"].strip() or "",
                        "cause_type": row["มูลเหตุสันนิษฐาน"].strip() or "",
                        "province": prov,
                        "geo_id": geo_id_map.get(prov),
                    }

    road_id_map: dict[tuple, int] = {}
    road_list = list(road_segments.items())
    for i in range(0, len(road_list), BATCH_SIZE):
        chunk = road_list[i:i + BATCH_SIZE]
        for key, attrs in chunk:
            cur.execute("""
                INSERT INTO dim_road_segment
                    (road_name, road_code, road_type, curvature_type, cause_type, geography_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING road_segment_id
            """, (
                attrs["road_name"],
                attrs["road_code"],
                attrs["road_type"],
                attrs["curvature_type"],
                attrs["cause_type"],
                attrs["geo_id"],
            ))
            road_id_map[key] = cur.fetchone()[0]
        conn.commit()
    print(f"      {len(road_id_map)} road segments in dim_road_segment.")

    # ── Step 5: Bulk insert fact_accident_event ──────────────────────────────
    print("\n[5/6] Inserting fact_accident_event...")
    total_inserted = 0
    insert_sql = """
        INSERT INTO fact_accident_event
            (event_datetime, geography_id, road_segment_id, weather_condition,
             accident_type, vehicle_type, severity_level, injured_count, death_count, source_id)
        VALUES %s
    """

    for csv_path, year in CSV_FILES:
        year_count = 0
        batch = []
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                dt = parse_datetime(row["วันที่เกิดเหตุ"], row["เวลา"])
                prov = row["จังหวัด"].strip()
                road_name = row["สายทาง"].strip()
                road_code = row["รหัสสายทาง"].strip()
                road_key = (road_code if road_code else road_name, prov)
                geo_id = geo_id_map.get(prov)
                road_id = road_id_map.get(road_key)
                death = to_int(row["ผู้เสียชีวิต"])
                injured = to_int(row["รวมจำนวนผู้บาดเจ็บ"])

                batch.append((
                    dt,
                    geo_id,
                    road_id,
                    row["สภาพอากาศ"].strip() or "ไม่ทราบ",
                    row["ลักษณะการเกิดเหตุ"].strip() or "ไม่ทราบ",
                    row["รถคันที่1"].strip() or "ไม่ทราบ",
                    severity(death, injured),
                    injured,
                    death,
                    source_ids[year],
                ))

                if len(batch) >= BATCH_SIZE:
                    psycopg2.extras.execute_values(cur, insert_sql, batch)
                    conn.commit()
                    year_count += len(batch)
                    total_inserted += len(batch)
                    batch = []
                    print(f"      {year}: {year_count:>6} rows...", end="\r")

        if batch:
            psycopg2.extras.execute_values(cur, insert_sql, batch)
            conn.commit()
            year_count += len(batch)
            total_inserted += len(batch)

        print(f"      {year}: {year_count:>6} rows inserted.     ")

    print(f"      Total: {total_inserted} rows in fact_accident_event.")

    # ── Step 6: Rebuild mart tables via SQL aggregation ──────────────────────
    print("\n[6/6] Rebuilding mart tables...")

    # mart_accident_summary: group by year, month, province
    cur.execute("""
        INSERT INTO mart_accident_summary
            (year_no, month_no, geography_id, accident_count, injured_count, death_count,
             high_risk_timeband, dominant_road_cond)
        SELECT
            EXTRACT(YEAR FROM e.event_datetime)::INT,
            EXTRACT(MONTH FROM e.event_datetime)::INT,
            e.geography_id,
            COUNT(*)                          AS accident_count,
            SUM(e.injured_count)              AS injured_count,
            SUM(e.death_count)                AS death_count,
            -- most common hour band
            MODE() WITHIN GROUP (ORDER BY
                CASE
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6 AND 11  THEN 'เช้า (06-12)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'กลางวัน (12-18)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 18 AND 23 THEN 'เย็น/กลางคืน (18-24)'
                    ELSE 'กลางคืน (00-06)'
                END
            )                                 AS high_risk_timeband,
            MODE() WITHIN GROUP (ORDER BY e.weather_condition) AS dominant_road_cond
        FROM fact_accident_event e
        WHERE e.event_datetime IS NOT NULL
          AND e.geography_id IS NOT NULL
        GROUP BY 1, 2, 3
    """)
    conn.commit()

    # mart_accident_hotspot: group by geography + road_segment
    cur.execute("""
        INSERT INTO mart_accident_hotspot
            (geography_id, road_segment_id, accident_count, injured_count, death_count,
             hotspot_score, dominant_timeband)
        SELECT
            e.geography_id,
            e.road_segment_id,
            COUNT(*)                          AS accident_count,
            SUM(e.injured_count)              AS injured_count,
            SUM(e.death_count)                AS death_count,
            COUNT(*) + SUM(e.death_count) * 10 + SUM(e.injured_count) * 2 AS hotspot_score,
            MODE() WITHIN GROUP (ORDER BY
                CASE
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6 AND 11  THEN 'เช้า (06-12)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'กลางวัน (12-18)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 18 AND 23 THEN 'เย็น/กลางคืน (18-24)'
                    ELSE 'กลางคืน (00-06)'
                END
            )                                 AS dominant_timeband
        FROM fact_accident_event e
        WHERE e.geography_id IS NOT NULL
        GROUP BY e.geography_id, e.road_segment_id
    """)
    conn.commit()
    print("      mart_accident_summary and mart_accident_hotspot rebuilt.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  Import Complete! Row counts:")
    for table in ["dim_geography", "dim_road_segment", "dim_source",
                  "fact_accident_event", "mart_accident_summary", "mart_accident_hotspot"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"    {table:<32} {cur.fetchone()[0]:>8} rows")
    print("=" * 65)

    cur.close()
    conn.close()


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n  Total time: {time.time()-t0:.1f}s")
