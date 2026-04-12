"""
Import real accident data from ALL CSV files (2020–2026) into the Agent database.

Key data quirks handled:
  - 2020–2023: วันที่เกิดเหตุ format "M/D/YYYY" or "MM/DD/YYYY"
  - 2024–2026: วันที่เกิดเหตุ is an Excel serial number (integer days since 1899-12-30)
  - 2026:      ACC_CODE column is missing → all columns shift left by one position
  - All years: serious_injured (ผู้บาดเจ็บสาหัส) is stored in fact table
  - dim_road_segment gets road_code + geography_id (province-linked)

Run from the Agent project root:
    python database/import_csv_all_years.py
"""
import csv
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
DB_DSN = (
    f"host={os.getenv('DB_HOST','localhost')} "
    f"port={os.getenv('DB_PORT','5432')} "
    f"dbname={os.getenv('DB_NAME','chat-aio')} "
    f"user={os.getenv('DB_USER','postgres')} "
    f"password={os.getenv('DB_PASSWORD','1234')}"
)
CSV_DIR = Path(__file__).parent
CSV_FILES = [
    (CSV_DIR / "accident2020.csv", 2020),
    (CSV_DIR / "accident2021.csv", 2021),
    (CSV_DIR / "accident2022.csv", 2022),
    (CSV_DIR / "accident2023.csv", 2023),
    (CSV_DIR / "accident2024.csv", 2024),
    (CSV_DIR / "accident2025.csv", 2025),
    (CSV_DIR / "accident2026.csv", 2026),
]
BATCH_SIZE = 500

# Excel epoch: serial 1 = 1900-01-01 (with Lotus 1-2-3 bug where 1900 is leap year)
EXCEL_EPOCH = datetime(1899, 12, 30)


# ── Helpers ────────────────────────────────────────────────────────────────────
def to_int(val, default=0):
    try:
        return int(float(val)) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def excel_serial_to_date(serial_str: str) -> datetime | None:
    """Convert Excel serial date string (e.g. '45292') to datetime."""
    try:
        serial = int(float(serial_str.strip()))
        if serial <= 0:
            return None
        return EXCEL_EPOCH + timedelta(days=serial)
    except (ValueError, TypeError):
        return None


def parse_datetime(date_str: str, time_str: str, year: int) -> datetime | None:
    """Parse date+time from CSV row. Handles both string and Excel serial formats."""
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()

    if not date_str:
        return None

    # Excel serial number (numeric only)
    if date_str.isdigit() or (date_str.replace(".", "", 1).isdigit() and "." in date_str):
        dt = excel_serial_to_date(date_str)
        if dt and time_str:
            try:
                hm = datetime.strptime(time_str, "%H:%M")
                dt = dt.replace(hour=hm.hour, minute=hm.minute)
            except ValueError:
                pass
        return dt

    # String date formats
    for fmt in ("%m/%d/%Y", "%-m/%-d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if time_str:
                try:
                    hm = datetime.strptime(time_str, "%H:%M")
                    dt = dt.replace(hour=hm.hour, minute=hm.minute)
                except ValueError:
                    pass
            return dt
        except ValueError:
            continue

    return None


def normalize_row_2026(row: dict) -> dict:
    """Fix 2026 column shift: ACC_CODE is missing so columns after หน่วยงาน shift left.

    Raw 2026 row (from DictReader with correct headers) maps:
      ACC_CODE    -> หน่วยงาน value (wrong)
      หน่วยงาน   -> สายทางหน่วยงาน value
      ...
    We detect this by checking if ACC_CODE looks like an agency name.
    Fix: shift values back by injecting empty ACC_CODE.
    """
    # If ACC_CODE contains Thai text (agency name), it's the shifted row
    acc = row.get("ACC_CODE", "")
    if acc and not acc.isdigit() and any("\u0e00" <= c <= "\u0e7f" for c in acc):
        cols_after_acccode = [
            "ACC_CODE", "หน่วยงาน", "สายทางหน่วยงาน", "รหัสสายทาง", "สายทาง",
            "KM", "จังหวัด", "รถคันที่1", "บริเวณที่เกิดเหตุ", "มูลเหตุสันนิษฐาน",
            "ลักษณะการเกิดเหตุ", "สภาพอากาศ", "LATITUDE", "LONGITUDE",
            "รถที่เกิดเหตุ", "รถและคนที่เกิดเหตุ",
            "รถจักรยานยนต์", "รถสามล้อเครื่อง", "รถยนต์นั่งส่วนบุคคล", "รถตู้",
            "รถปิคอัพโดยสาร", "รถโดยสารมากกว่า4ล้อ", "รถปิคอัพบรรทุก4ล้อ",
            "รถบรรทุก6ล้อ", "รถบรรทุกไม่เกิน10ล้อ", "รถบรรทุกมากกว่า10ล้อ",
            "รถอีแต๋น", "รถอื่นๆ", "คนเดินเท้า",
            "ผู้เสียชีวิต", "ผู้บาดเจ็บสาหัส", "ผู้บาดเจ็บเล็กน้อย", "รวมจำนวนผู้บาดเจ็บ",
        ]
        # Current values are shifted: row["ACC_CODE"] has หน่วยงาน value, etc.
        shifted_vals = [row.get(c, "") for c in cols_after_acccode]
        # Insert empty string at position 0 (ACC_CODE) and pop last
        fixed_vals = [""] + shifted_vals[:-1]
        fixed = dict(row)
        for col, val in zip(cols_after_acccode, fixed_vals):
            fixed[col] = val
        return fixed
    return row


def severity(death: int, injured: int) -> str:
    if death > 0:
        return "เสียชีวิต"
    elif injured > 0:
        return "บาดเจ็บ"
    else:
        return "รอดปลอดภัย"


def parse_coordinate(coord_str: str) -> float | None:
    """Parse latitude/longitude from CSV, handling various formats."""
    if not coord_str:
        return None
    coord_str = coord_str.strip()
    if not coord_str or coord_str == "0" or coord_str == "0.0":
        return None
    try:
        val = float(coord_str)
        # Basic validation: Thailand coordinates
        # Latitude: ~5.6 to 20.5, Longitude: ~97.3 to 105.6
        if val == 0.0:
            return None
        return val
    except (ValueError, TypeError):
        return None


def timeband(dt: datetime | None) -> str:
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


# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    print("=" * 70)
    print("  Musya Agent — Import ALL Accident CSV Data (2020–2026)")
    print("=" * 70)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Step 1: Truncate ──────────────────────────────────────────────────────
    print("\n[1/6] Truncating existing data...")
    cur.execute("""
        TRUNCATE mart_accident_hotspot, mart_accident_summary,
                 mart_province_year, mart_province_road,
                 fact_accident_person, fact_accident_event,
                 dim_road_segment
        RESTART IDENTITY CASCADE
    """)
    conn.commit()
    print("      Done.")

    # ── Step 2: Upsert dim_source ─────────────────────────────────────────────
    print("\n[2/6] Upserting dim_source (one per CSV year)...")
    source_ids: dict[int, int] = {}
    for csv_path, year in CSV_FILES:
        if not csv_path.exists():
            print(f"      SKIP: {csv_path.name} not found")
            continue
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

    # ── Step 3: Build dim_geography (provinces) from all CSVs ─────────────────
    print("\n[3/6] Building dim_geography from all CSV provinces...")
    province_coords: dict[str, tuple[float, float]] = {}
    for csv_path, year in CSV_FILES:
        if not csv_path.exists():
            continue
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if year == 2026:
                    row = normalize_row_2026(row)
                prov = row.get("จังหวัด", "").strip()
                if not prov or len(prov) > 50:
                    continue
                if prov not in province_coords:
                    try:
                        lat = float(row.get("LATITUDE", "") or 0)
                        lon = float(row.get("LONGITUDE", "") or 0)
                        if lat != 0.0 and lon != 0.0:
                            province_coords[prov] = (lat, lon)
                        else:
                            province_coords.setdefault(prov, (0.0, 0.0))
                    except (ValueError, TypeError):
                        province_coords.setdefault(prov, (0.0, 0.0))

    geo_id_map: dict[str, int] = {}
    for prov, (lat, lon) in province_coords.items():
        cur.execute("""
            INSERT INTO dim_geography (province_name, latitude, longitude, country_code)
            VALUES (%s, %s, %s, 'TH')
            ON CONFLICT (province_name) WHERE province_name IS NOT NULL
            DO UPDATE SET
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude
            RETURNING geography_id
        """, (prov, lat, lon))
        row = cur.fetchone()
        if row:
            geo_id_map[prov] = row[0]
        else:
            cur.execute("SELECT geography_id FROM dim_geography WHERE province_name = %s", (prov,))
            r = cur.fetchone()
            if r:
                geo_id_map[prov] = r[0]
    conn.commit()
    print(f"      {len(geo_id_map)} provinces in dim_geography.")

    # ── Step 4: Build dim_road_segment (road_code + province linked) ───────────
    print("\n[4/6] Building dim_road_segment (road_code + geography_id)...")
    road_segments: dict[tuple, dict] = {}
    for csv_path, year in CSV_FILES:
        if not csv_path.exists():
            continue
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if year == 2026:
                    row = normalize_row_2026(row)
                road_name = row.get("สายทาง", "").strip()
                road_code = row.get("รหัสสายทาง", "").strip()
                prov = row.get("จังหวัด", "").strip()
                if not prov or len(prov) > 50:
                    continue
                key = (road_code if road_code else road_name, prov)
                if key not in road_segments:
                    road_segments[key] = {
                        "road_name": road_name or road_code or "ไม่ทราบ",
                        "road_code": road_code or None,
                        "road_type": row.get("หน่วยงาน", "").strip() or "ไม่ทราบ",
                        "curvature_type": row.get("บริเวณที่เกิดเหตุ", "").strip() or "",
                        "cause_type": row.get("มูลเหตุสันนิษฐาน", "").strip() or "",
                        "province": prov,
                        "geo_id": geo_id_map.get(prov),
                    }

    road_id_map: dict[tuple, int] = {}
    road_list = list(road_segments.items())
    for i in range(0, len(road_list), BATCH_SIZE):
        chunk = road_list[i: i + BATCH_SIZE]
        for key, attrs in chunk:
            # Use ON CONFLICT to handle duplicates
            if attrs["road_code"]:
                cur.execute("""
                    INSERT INTO dim_road_segment
                        (road_name, road_code, road_type, curvature_type, cause_type, geography_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (road_code, geography_id)
                        WHERE road_code IS NOT NULL AND geography_id IS NOT NULL
                    DO UPDATE SET
                        road_name = EXCLUDED.road_name,
                        road_type = EXCLUDED.road_type,
                        curvature_type = EXCLUDED.curvature_type,
                        cause_type = EXCLUDED.cause_type
                    RETURNING road_segment_id
                """, (
                    attrs["road_name"],
                    attrs["road_code"],
                    attrs["road_type"],
                    attrs["curvature_type"],
                    attrs["cause_type"],
                    attrs["geo_id"],
                ))
            else:
                cur.execute("""
                    INSERT INTO dim_road_segment
                        (road_name, road_code, road_type, curvature_type, cause_type, geography_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (road_name, geography_id)
                        WHERE road_code IS NULL AND road_name IS NOT NULL AND geography_id IS NOT NULL
                    DO UPDATE SET
                        road_type = EXCLUDED.road_type,
                        curvature_type = EXCLUDED.curvature_type,
                        cause_type = EXCLUDED.cause_type
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

    # ── Step 5: Insert fact_accident_event (all years) ─────────────────────────
    print("\n[5/6] Inserting fact_accident_event for all years...")
    total_inserted = 0
    total_skipped = 0
    insert_sql = """
        INSERT INTO fact_accident_event
            (event_datetime, geography_id, road_segment_id, weather_condition,
             accident_type, vehicle_type, severity_level,
             injured_count, serious_injured, death_count,
             source_id, csv_year, latitude, longitude)
        VALUES %s
        ON CONFLICT (event_datetime, geography_id, road_segment_id, csv_year)
            WHERE event_datetime IS NOT NULL 
              AND geography_id IS NOT NULL 
              AND road_segment_id IS NOT NULL
              AND csv_year IS NOT NULL
        DO NOTHING
    """

    for csv_path, year in CSV_FILES:
        if not csv_path.exists():
            print(f"      SKIP: {csv_path.name}")
            continue
        year_count = 0
        year_skipped = 0
        batch = []
        seen_in_csv = set()  # Track duplicates within CSV file
        
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if year == 2026:
                    row = normalize_row_2026(row)

                dt = parse_datetime(row.get("วันที่เกิดเหตุ", ""), row.get("เวลา", ""), year)
                prov = row.get("จังหวัด", "").strip()
                if not prov or len(prov) > 50:
                    continue

                road_name = row.get("สายทาง", "").strip()
                road_code = row.get("รหัสสายทาง", "").strip()
                road_key = (road_code if road_code else road_name, prov)
                geo_id = geo_id_map.get(prov)
                road_id = road_id_map.get(road_key)

                # Detect duplicates within CSV file
                if dt and geo_id and road_id:
                    dup_key = (dt, geo_id, road_id, year)
                    if dup_key in seen_in_csv:
                        year_skipped += 1
                        total_skipped += 1
                        continue
                    seen_in_csv.add(dup_key)

                death = to_int(row.get("ผู้เสียชีวิต", ""))
                injured = to_int(row.get("รวมจำนวนผู้บาดเจ็บ", ""))
                serious = to_int(row.get("ผู้บาดเจ็บสาหัส", ""))
                
                # Parse coordinates
                lat = parse_coordinate(row.get("LATITUDE", ""))
                lon = parse_coordinate(row.get("LONGITUDE", ""))

                batch.append((
                    dt,
                    geo_id,
                    road_id,
                    row.get("สภาพอากาศ", "").strip() or "ไม่ทราบ",
                    row.get("ลักษณะการเกิดเหตุ", "").strip() or "ไม่ทราบ",
                    row.get("รถคันที่1", "").strip() or "ไม่ทราบ",
                    severity(death, injured),
                    injured,
                    serious,
                    death,
                    source_ids.get(year),
                    year,
                    lat,
                    lon,
                ))

                if len(batch) >= BATCH_SIZE:
                    psycopg2.extras.execute_values(cur, insert_sql, batch)
                    conn.commit()
                    year_count += len(batch)
                    total_inserted += len(batch)
                    batch = []
                    print(f"      {year}: {year_count:>7} rows...", end="\r")

        if batch:
            psycopg2.extras.execute_values(cur, insert_sql, batch)
            conn.commit()
            year_count += len(batch)
            total_inserted += len(batch)

        dup_msg = f" ({year_skipped} CSV duplicates skipped)" if year_skipped > 0 else ""
        print(f"      {year}: {year_count:>7} rows inserted{dup_msg}.       ")

    print(f"      ── Total: {total_inserted} rows inserted.")
    if total_skipped > 0:
        print(f"      ── Skipped: {total_skipped} duplicate rows found in CSV files.")
    
    # Check how many events have coordinates
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(latitude) as with_lat,
            COUNT(longitude) as with_lon,
            COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as with_both
        FROM fact_accident_event
    """)
    coord_stats = cur.fetchone()
    if coord_stats:
        total, with_lat, with_lon, with_both = coord_stats
        pct = (with_both / total * 100) if total > 0 else 0
        print(f"      ── Coordinates: {with_both}/{total} events ({pct:.1f}%) have lat/lon")

    # ── Step 6: Rebuild all mart tables ───────────────────────────────────────
    print("\n[6/6] Rebuilding mart tables...")

    # mart_accident_summary (monthly, by province)
    cur.execute("TRUNCATE mart_accident_summary RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_accident_summary
            (year_no, month_no, geography_id, province_name,
             accident_count, injured_count, death_count,
             high_risk_timeband, dominant_road_cond)
        SELECT
            EXTRACT(YEAR  FROM e.event_datetime)::INT,
            EXTRACT(MONTH FROM e.event_datetime)::INT,
            e.geography_id,
            g.province_name,
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
        JOIN dim_geography g ON e.geography_id = g.geography_id
        WHERE e.event_datetime IS NOT NULL
          AND e.geography_id IS NOT NULL
        GROUP BY 1, 2, 3, g.province_name
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_accident_summary")
    print(f"      mart_accident_summary: {cur.fetchone()[0]} rows")

    # mart_province_year (yearly per province, full detail)
    cur.execute("TRUNCATE mart_province_year RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_province_year
            (year_no, geography_id, province_name,
             accident_count, injured_count, serious_injured, death_count,
             road_count, top_vehicle, top_cause, top_timeband, top_weather)
        SELECT
            EXTRACT(YEAR FROM e.event_datetime)::INT                     AS year_no,
            e.geography_id,
            g.province_name,
            COUNT(*)                                                      AS accident_count,
            SUM(e.injured_count)                                          AS injured_count,
            SUM(e.serious_injured)                                        AS serious_injured,
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
    print(f"      mart_province_year:    {cur.fetchone()[0]} rows")

    # mart_province_road (per province, road, year)
    cur.execute("TRUNCATE mart_province_road RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_province_road
            (year_no, geography_id, province_name,
             road_segment_id, road_name, road_code,
             accident_count, injured_count, serious_injured, death_count,
             hotspot_score, dominant_cause, dominant_vehicle)
        SELECT
            EXTRACT(YEAR FROM e.event_datetime)::INT                     AS year_no,
            e.geography_id,
            g.province_name,
            r.road_segment_id,
            r.road_name,
            r.road_code,
            COUNT(*)                                                      AS accident_count,
            SUM(e.injured_count)                                          AS injured_count,
            SUM(e.serious_injured)                                        AS serious_injured,
            SUM(e.death_count)                                            AS death_count,
            COUNT(*) + SUM(e.death_count)*10 + SUM(e.injured_count)*2   AS hotspot_score,
            MODE() WITHIN GROUP (ORDER BY e.accident_type)               AS dominant_cause,
            MODE() WITHIN GROUP (ORDER BY e.vehicle_type)                AS dominant_vehicle
        FROM fact_accident_event e
        JOIN dim_geography g    ON e.geography_id    = g.geography_id
        JOIN dim_road_segment r ON e.road_segment_id = r.road_segment_id
        WHERE e.event_datetime IS NOT NULL
        GROUP BY
            EXTRACT(YEAR FROM e.event_datetime)::INT,
            e.geography_id, g.province_name,
            r.road_segment_id, r.road_name, r.road_code
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_province_road")
    print(f"      mart_province_road:    {cur.fetchone()[0]} rows")

    # mart_accident_hotspot (all-time, province + road)
    cur.execute("TRUNCATE mart_accident_hotspot RESTART IDENTITY")
    cur.execute("""
        INSERT INTO mart_accident_hotspot
            (geography_id, road_segment_id,
             accident_count, injured_count, death_count,
             hotspot_score, dominant_timeband)
        SELECT
            e.geography_id,
            e.road_segment_id,
            COUNT(*),
            SUM(e.injured_count),
            SUM(e.death_count),
            COUNT(*) + SUM(e.death_count)*10 + SUM(e.injured_count)*2,
            MODE() WITHIN GROUP (ORDER BY
                CASE
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 6  AND 11 THEN 'เช้า (06-12)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 12 AND 17 THEN 'กลางวัน (12-18)'
                    WHEN EXTRACT(HOUR FROM e.event_datetime) BETWEEN 18 AND 23 THEN 'เย็น/กลางคืน (18-24)'
                    ELSE 'กลางคืน (00-06)'
                END
            )
        FROM fact_accident_event e
        WHERE e.geography_id IS NOT NULL
        GROUP BY e.geography_id, e.road_segment_id
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM mart_accident_hotspot")
    print(f"      mart_accident_hotspot: {cur.fetchone()[0]} rows")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Final Row Counts:")
    for table in [
        "dim_geography", "dim_road_segment", "dim_source",
        "fact_accident_event",
        "mart_accident_summary", "mart_province_year",
        "mart_province_road", "mart_accident_hotspot",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"    {table:<35} {cur.fetchone()[0]:>8} rows")

    print("\n  Years in fact table:")
    cur.execute("""
        SELECT csv_year, COUNT(*) as cnt, SUM(death_count) as deaths
        FROM fact_accident_event
        WHERE csv_year IS NOT NULL
        GROUP BY csv_year ORDER BY csv_year
    """)
    for r in cur.fetchall():
        print(f"    {r[0]}: {r[1]:>7} events, {r[2]} deaths")

    print("\n  Top 10 provinces by total accidents (all years):")
    cur.execute("""
        SELECT province_name,
               SUM(accident_count) AS total_accidents,
               SUM(death_count)    AS total_deaths
        FROM mart_province_year
        GROUP BY province_name
        ORDER BY total_accidents DESC
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"    {r[0]:<20} accidents={r[1]:>7}, deaths={r[2]:>5}")

    # ── Verification: Compare fact vs mart counts ─────────────────────────────
    print("\n" + "=" * 70)
    print("  Data Verification: Fact vs Mart Counts")
    print("=" * 70)
    
    # Get total from fact table
    cur.execute("SELECT COUNT(*) FROM fact_accident_event")
    fact_total = cur.fetchone()[0]
    
    # Get total from mart_province_year (should match fact table)
    cur.execute("SELECT SUM(accident_count) FROM mart_province_year")
    mart_total = cur.fetchone()[0] or 0
    
    print(f"  fact_accident_event total:  {fact_total:>8} rows")
    print(f"  mart_province_year total:   {mart_total:>8} accidents")
    
    if fact_total == mart_total:
        print("  ✓ PASS: Fact and mart counts match (no duplicates)")
    else:
        diff = abs(fact_total - mart_total)
        pct = (diff / fact_total * 100) if fact_total > 0 else 0
        print(f"  ✗ WARN: Counts differ by {diff} ({pct:.1f}%)")
        if mart_total > fact_total:
            print("         Mart has MORE - possible duplicate counting in aggregation")
        else:
            print("         Fact has MORE - possible missing data in mart rebuild")
    
    # Sample verification: Check one province (เชียงใหม่)
    print("\n  Sample: เชียงใหม่ yearly breakdown")
    cur.execute("""
        SELECT csv_year, COUNT(*) as fact_count
        FROM fact_accident_event f
        JOIN dim_geography g ON f.geography_id = g.geography_id
        WHERE g.province_name LIKE '%เชียงใหม่%'
        GROUP BY csv_year
        ORDER BY csv_year
    """)
    fact_cm = {r[0]: r[1] for r in cur.fetchall()}
    
    cur.execute("""
        SELECT year_no, accident_count
        FROM mart_province_year
        WHERE province_name LIKE '%เชียงใหม่%'
        ORDER BY year_no
    """)
    mart_cm = {r[0]: r[1] for r in cur.fetchall()}
    
    all_years = sorted(set(fact_cm.keys()) | set(mart_cm.keys()))
    match_count = 0
    for yr in all_years:
        f_cnt = fact_cm.get(yr, 0)
        m_cnt = mart_cm.get(yr, 0)
        status = "✓" if f_cnt == m_cnt else "✗"
        print(f"    {yr}: fact={f_cnt:>5}, mart={m_cnt:>5} {status}")
        if f_cnt == m_cnt:
            match_count += 1
    
    if match_count == len(all_years):
        print("  ✓ PASS: All years match for เชียงใหม่")
    else:
        print(f"  ✗ WARN: {len(all_years) - match_count}/{len(all_years)} years have mismatches")

    print("=" * 70)
    cur.close()
    conn.close()


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"\n  Total time: {time.time() - t0:.1f}s")
