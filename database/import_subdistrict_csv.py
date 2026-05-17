"""
Migration 017 — Reimport accident data from accident_all_with_subdistrict.csv

What this script does:
  1. Truncates fact_accident_event, fact_accident_person, and all mart tables
     (dim_geography / dim_road_segment are UPSERTED, not truncated)
  2. Reads accident_all_with_subdistrict.csv (2021-2026, 115K rows)
  3. Upserts dim_geography with province + district + subdistrict
  4. Upserts dim_road_segment
  5. Bulk-inserts fact_accident_event (ON CONFLICT DO NOTHING)
  6. Rebuilds mart_accident_summary, mart_accident_hotspot,
     mart_province_year, mart_province_road

Run from the Agent/ directory:
    python database/import_subdistrict_csv.py
"""

import csv
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "chat-aio"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "1234"),
)

CSV_PATH = Path(__file__).parent / "accident_all_with_subdistrict.csv"
BATCH = 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(row, key, default=None):
    """Get CSV value, strip whitespace, return default if empty/missing."""
    v = row.get(key, "")
    if v is None:
        return default
    v = str(v).strip()
    return default if v in ("", "nan", "None", "NULL") else v


def _float(row, key):
    v = _f(row, key)
    try:
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def _int(row, key):
    v = _float(row, key)
    return int(v) if v is not None else None


def _parse_date(row):
    """Parse วันที่เกิดเหตุ (d/m/yyyy or d/m/yy) + เวลา (H:MM) → datetime."""
    date_str = _f(row, "วันที่เกิดเหตุ", "")
    time_str = _f(row, "เวลา", "0:00")
    if not date_str:
        return None
    try:
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                d = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            return None
        h, m = (time_str + ":00").split(":")[:2]
        return d.replace(hour=int(h) % 24, minute=int(m) % 60)
    except Exception:
        return None


def _dominant(values):
    """Return the most frequent non-None value in a list."""
    from collections import Counter
    c = Counter(v for v in values if v)
    return c.most_common(1)[0][0] if c else None


# ---------------------------------------------------------------------------
# Geography upsert
# ---------------------------------------------------------------------------

def upsert_geography(cur, province, district, subdistrict,
                     prov_code, dist_code, sub_code, lat, lon):
    district    = district    or ""
    subdistrict = subdistrict or ""
    # Uses: uq_dim_geography_province_district_sub (from Migration 017)
    cur.execute(
        """
        INSERT INTO dim_geography
            (province_name, district_name, subdistrict_name,
             province_code, district_code, subdistrict_code,
             latitude, longitude)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (province_name, district_name, subdistrict_name)
        WHERE province_name IS NOT NULL
        DO UPDATE SET
            province_code    = COALESCE(EXCLUDED.province_code,    dim_geography.province_code),
            district_code    = COALESCE(EXCLUDED.district_code,    dim_geography.district_code),
            subdistrict_code = COALESCE(EXCLUDED.subdistrict_code, dim_geography.subdistrict_code),
            latitude  = COALESCE(EXCLUDED.latitude,  dim_geography.latitude),
            longitude = COALESCE(EXCLUDED.longitude, dim_geography.longitude)
        RETURNING geography_id
        """,
        (province, district, subdistrict,
         prov_code or "", dist_code or "", sub_code or "", lat, lon),
    )
    return cur.fetchone()[0]


def ensure_geography_unique_constraint(cur):
    pass  # Migration 017 SQL must be run first (drops old, creates new index)


# ---------------------------------------------------------------------------
# Road segment upsert
# ---------------------------------------------------------------------------

def upsert_road(cur, road_name, road_code, geography_id, km):
    road_name = road_name or None   # NULL in DB when truly unknown (not 'unknown' string)
    road_code = road_code or None  # keep NULL for the conditional unique index

    if road_code:
        # Uses: idx_road_segment_unique (road_code, geography_id) WHERE road_code IS NOT NULL
        cur.execute(
            """
            INSERT INTO dim_road_segment (road_name, road_code, geography_id, km_marker)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (road_code, geography_id) WHERE road_code IS NOT NULL AND geography_id IS NOT NULL
            DO UPDATE SET
                road_name  = EXCLUDED.road_name,
                km_marker  = EXCLUDED.km_marker
            RETURNING road_segment_id
            """,
            (road_name, road_code, geography_id, km),
        )
    else:
        # Uses: idx_road_segment_name_unique (road_name, geography_id) WHERE road_code IS NULL
        cur.execute(
            """
            INSERT INTO dim_road_segment (road_name, road_code, geography_id, km_marker)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (road_name, geography_id) WHERE road_code IS NULL AND road_name IS NOT NULL AND geography_id IS NOT NULL
            DO UPDATE SET km_marker = EXCLUDED.km_marker
            RETURNING road_segment_id
            """,
            (road_name, road_code, geography_id, km),
        )
    return cur.fetchone()[0]


def ensure_road_unique_constraint(cur):
    pass  # existing constraints in dim_road_segment are sufficient


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

def ensure_source(cur, agency):
    cur.execute(
        "SELECT source_id FROM dim_source WHERE source_name = %s", (agency,)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO dim_source (source_name, source_type) VALUES (%s, 'government') RETURNING source_id",
        (agency,),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Mart rebuild
# ---------------------------------------------------------------------------

MART_ACCIDENT_SUMMARY = """
TRUNCATE mart_accident_summary;
INSERT INTO mart_accident_summary
    (year_no, month_no, geography_id, province_name,
     accident_count, injured_count, death_count,
     high_risk_timeband, dominant_road_cond)
SELECT
    EXTRACT(YEAR  FROM e.event_datetime)::int,
    EXTRACT(MONTH FROM e.event_datetime)::int,
    e.geography_id,
    g.province_name,
    COUNT(*)                          AS accident_count,
    COALESCE(SUM(e.injured_count),0)  AS injured_count,
    COALESCE(SUM(e.death_count),0)    AS death_count,
    NULL                              AS high_risk_timeband,
    MODE() WITHIN GROUP (ORDER BY e.weather_condition) AS dominant_road_cond
FROM fact_accident_event e
JOIN dim_geography g USING (geography_id)
WHERE e.event_datetime IS NOT NULL
GROUP BY 1,2,3,4;
"""

MART_ACCIDENT_HOTSPOT = """
TRUNCATE mart_accident_hotspot;
INSERT INTO mart_accident_hotspot
    (geography_id, road_segment_id,
     accident_count, injured_count, death_count,
     hotspot_score, dominant_timeband)
SELECT
    e.geography_id,
    e.road_segment_id,
    COUNT(*)                          AS accident_count,
    COALESCE(SUM(e.injured_count),0)  AS injured_count,
    COALESCE(SUM(e.death_count),0)    AS death_count,
    COUNT(*) * 1.0
      + COALESCE(SUM(e.death_count),0) * 3.0
      + COALESCE(SUM(e.serious_injured),0) * 2.0 AS hotspot_score,
    NULL AS dominant_timeband
FROM fact_accident_event e
WHERE e.road_segment_id IS NOT NULL
GROUP BY e.geography_id, e.road_segment_id;
"""

MART_PROVINCE_YEAR = """
TRUNCATE mart_province_year;
INSERT INTO mart_province_year
    (province_name, year_no,
     accident_count, injured_count, serious_injured, death_count,
     road_count, top_vehicle, top_cause, top_timeband, top_weather)
SELECT
    g.province_name,
    e.csv_year                        AS year_no,
    COUNT(*)                          AS accident_count,
    COALESCE(SUM(e.injured_count),0)  AS injured_count,
    COALESCE(SUM(e.serious_injured),0) AS serious_injured,
    COALESCE(SUM(e.death_count),0)    AS death_count,
    COUNT(DISTINCT e.road_segment_id) AS road_count,
    MODE() WITHIN GROUP (ORDER BY e.vehicle_type)     AS top_vehicle,
    MODE() WITHIN GROUP (ORDER BY e.accident_type)    AS top_cause,
    NULL                              AS top_timeband,
    MODE() WITHIN GROUP (ORDER BY e.weather_condition) AS top_weather
FROM fact_accident_event e
JOIN dim_geography g USING (geography_id)
WHERE e.csv_year IS NOT NULL
GROUP BY g.province_name, e.csv_year;
"""

MART_PROVINCE_ROAD = """
TRUNCATE mart_province_road;
INSERT INTO mart_province_road
    (province_name, road_name, road_code, year_no,
     accident_count, injured_count, serious_injured, death_count,
     hotspot_score, dominant_cause, dominant_vehicle)
SELECT
    g.province_name,
    r.road_name,
    r.road_code,
    e.csv_year                        AS year_no,
    COUNT(*)                          AS accident_count,
    COALESCE(SUM(e.injured_count),0)  AS injured_count,
    COALESCE(SUM(e.serious_injured),0) AS serious_injured,
    COALESCE(SUM(e.death_count),0)    AS death_count,
    COUNT(*) * 1.0
      + COALESCE(SUM(e.death_count),0) * 3.0    AS hotspot_score,
    MODE() WITHIN GROUP (ORDER BY e.accident_type)  AS dominant_cause,
    MODE() WITHIN GROUP (ORDER BY e.vehicle_type)   AS dominant_vehicle
FROM fact_accident_event e
JOIN dim_geography g USING (geography_id)
JOIN dim_road_segment r USING (road_segment_id)
WHERE e.csv_year IS NOT NULL
GROUP BY g.province_name, r.road_name, r.road_code, e.csv_year;
"""


def rebuild_marts(conn):
    log.info("Rebuilding mart tables …")
    with conn.cursor() as cur:
        for name, sql in [
            ("mart_accident_summary", MART_ACCIDENT_SUMMARY),
            ("mart_accident_hotspot", MART_ACCIDENT_HOTSPOT),
            ("mart_province_year",    MART_PROVINCE_YEAR),
            ("mart_province_road",    MART_PROVINCE_ROAD),
        ]:
            log.info("  Rebuilding %s …", name)
            cur.execute(sql)
    conn.commit()
    log.info("Mart rebuild complete.")


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def run():
    log.info("Connecting to %s:%s/%s …", DB["host"], DB["port"], DB["dbname"])
    conn = psycopg2.connect(**DB)

    with conn.cursor() as cur:
        # Ensure unique constraints exist before upserts
        ensure_geography_unique_constraint(cur)
        ensure_road_unique_constraint(cur)
        conn.commit()

        # Truncate fact + mart tables (keep dimensions)
        log.info("Truncating fact and mart tables …")
        cur.execute("""
            TRUNCATE fact_accident_person CASCADE;
            TRUNCATE fact_accident_event CASCADE;
        """)
        conn.commit()

    geo_cache: dict[tuple, int] = {}   # (province, district, subdistrict) → geography_id
    road_cache: dict[tuple, int] = {}  # (road_name, road_code, geo_id) → road_segment_id
    source_cache: dict[str, int] = {}

    inserted = skipped = 0

    log.info("Reading %s …", CSV_PATH)
    with (
        open(CSV_PATH, encoding="utf-8-sig", newline="") as f,
        conn.cursor() as cur,
    ):
        reader = csv.DictReader(f)
        batch = []

        for i, row in enumerate(reader, 1):
            # --- Geography ---
            province   = _f(row, "จังหวัด", "")
            district   = _f(row, "อำเภอ", "") or _f(row, "adm2_name", "") or ""
            subdistrict = _f(row, "ตำบล", "") or _f(row, "adm3_name", "") or ""
            prov_code  = _f(row, "adm1_pcode", "")
            dist_code  = _f(row, "adm2_pcode", "")
            sub_code   = _f(row, "adm3_pcode", "")
            lat        = _float(row, "LATITUDE")
            lon        = _float(row, "LONGITUDE")

            if not province:
                skipped += 1
                continue

            geo_key = (province, district, subdistrict)
            if geo_key not in geo_cache:
                geo_cache[geo_key] = upsert_geography(
                    cur, province, district, subdistrict,
                    prov_code, dist_code, sub_code, lat, lon,
                )

            geography_id = geo_cache[geo_key]

            # --- Road segment ---
            road_name_raw = _f(row, "สายทาง", "")  # keep empty string if blank
            road_name = road_name_raw if road_name_raw else None  # None = truly unknown
            road_code = _f(row, "รหัสสายทาง", "") or None
            km        = _float(row, "KM")
            road_key  = (road_name, road_code, geography_id)
            if road_key not in road_cache:
                road_cache[road_key] = upsert_road(cur, road_name, road_code, geography_id, km)
            road_segment_id = road_cache[road_key]

            # --- Source ---
            agency = _f(row, "หน่วยงาน", "unknown")
            if agency not in source_cache:
                source_cache[agency] = ensure_source(cur, agency)
            source_id = source_cache[agency]

            # --- Event datetime ---
            event_dt = _parse_date(row)
            csv_year = _int(row, "year") or _int(row, "ปีที่เกิดเหตุ")

            # --- Counts ---
            death_count    = _int(row, "ผู้เสียชีวิต") or 0
            serious_inj    = _int(row, "ผู้บาดเจ็บสาหัส") or 0
            minor_inj      = _int(row, "ผู้บาดเจ็บเล็กน้อย") or 0
            total_inj      = _int(row, "รวมจำนวนผู้บาดเจ็บ") or (serious_inj + minor_inj)
            weather        = _f(row, "สภาพอากาศ", "")
            accident_type  = _f(row, "ลักษณะการเกิดเหตุ", "")
            cause          = _f(row, "มูลเหตุสันนิษฐาน", "")
            vehicle_type   = _f(row, "รถคันที่1", "")

            # Severity derived from counts
            if death_count > 0:
                severity = "fatal"
            elif serious_inj > 0:
                severity = "serious"
            elif total_inj > 0:
                severity = "minor"
            else:
                severity = "property_damage"

            batch.append((
                event_dt, geography_id, road_segment_id,
                weather, None, None,            # weather, road_cond, light_cond
                cause, severity, vehicle_type,
                total_inj, death_count, source_id,
                serious_inj, csv_year, lat, lon,
            ))

            if len(batch) >= BATCH:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    INSERT INTO fact_accident_event
                        (event_datetime, geography_id, road_segment_id,
                         weather_condition, road_condition, light_condition,
                         accident_type, severity_level, vehicle_type,
                         injured_count, death_count, source_id,
                         serious_injured, csv_year, latitude, longitude)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    """,
                    batch,
                )
                inserted += len(batch)
                batch.clear()
                conn.commit()
                if (i % 10000) == 0:
                    log.info("  Processed %d rows …", i)

        # Flush remaining
        if batch:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO fact_accident_event
                    (event_datetime, geography_id, road_segment_id,
                     weather_condition, road_condition, light_condition,
                     accident_type, severity_level, vehicle_type,
                     injured_count, death_count, source_id,
                     serious_injured, csv_year, latitude, longitude)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                batch,
            )
            inserted += len(batch)
            conn.commit()

    log.info("Inserted %d rows, skipped %d", inserted, skipped)
    log.info("dim_geography cache: %d unique locations", len(geo_cache))
    log.info("dim_road_segment cache: %d unique roads", len(road_cache))

    rebuild_marts(conn)
    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    run()
