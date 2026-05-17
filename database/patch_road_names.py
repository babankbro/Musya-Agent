"""Patch road_name in dim_road_segment from CSV data.

dim_road_segment currently has road_name='unknown' for all rows because
the previous import had blank สายทาง values. The CSV accident_all_with_subdistrict.csv
actually contains road names — this script:

  1. Reads all unique (road_code, road_name) pairs from the CSV
     (picking the most frequent non-blank name per road_code)
  2. UPDATEs dim_road_segment SET road_name = <csv_name>
     WHERE road_code = <code> AND road_name = 'unknown'
  3. Rebuilds mart_province_road with the corrected road names

Run from Agent/ directory:
    python database/patch_road_names.py
"""
import csv
import os
import logging
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent / "accident_all_with_subdistrict.csv"

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "chat-aio"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "1234"),
)

MART_PROVINCE_ROAD = """
TRUNCATE mart_province_road;
INSERT INTO mart_province_road
    (province_name, district_name, road_name, road_code, road_type_label, year_no,
     accident_count, injured_count, serious_injured, death_count,
     hotspot_score, dominant_cause, dominant_vehicle)
SELECT
    g.province_name,
    g.district_name,
    r.road_name,
    r.road_code,
    CASE
        WHEN r.road_type = 'กรมทางหลวง' OR r.road_type = 'การทางพิเศษแห่งประเทศไทย'
             THEN 'สายหลัก'
        WHEN r.road_type = 'กรมทางหลวงชนบท'
             THEN 'สายรอง'
        WHEN r.road_code ~ '^[0-9]+$'
             THEN 'สายหลัก'
        WHEN r.road_code IS NOT NULL AND r.road_code !~ '^[0-9]+$'
             THEN 'สายรอง'
        ELSE 'ไม่ระบุ'
    END                               AS road_type_label,
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
GROUP BY g.province_name, g.district_name, r.road_name, r.road_code, r.road_type, e.csv_year;
"""


def _f(row, key, default=""):
    v = row.get(key, "")
    if v is None:
        return default
    v = str(v).strip()
    return default if v.lower() in ("", "nan", "none", "null") else v


def build_road_name_map() -> dict[str, str]:
    """Build best road_name per road_code from CSV (most-frequent non-blank name)."""
    # road_code → Counter of road_names
    code_names: dict[str, Counter] = defaultdict(Counter)

    log.info("Reading CSV: %s", CSV_PATH)
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            road_name = _f(row, "สายทาง")
            road_code = _f(row, "รหัสสายทาง")
            if road_code and road_name:
                code_names[road_code][road_name] += 1

    log.info("Found %d unique road_codes with names in CSV", len(code_names))

    # Pick the most frequent name per code
    result: dict[str, str] = {}
    for code, counter in code_names.items():
        best_name = counter.most_common(1)[0][0]
        result[code] = best_name

    # Sample
    sample = list(result.items())[:10]
    for code, name in sample:
        log.info("  road_code=%s → name=%s", repr(code), repr(name))

    return result


def patch_dim_road_segment(conn, road_name_map: dict[str, str]) -> int:
    """UPDATE dim_road_segment road_name WHERE road_code matches and name is 'unknown'."""
    updated_total = 0
    with conn.cursor() as cur:
        # Build update pairs
        updates = [(name, code) for code, name in road_name_map.items()]
        log.info("Applying %d road_name updates …", len(updates))

        for name, code in updates:
            cur.execute(
                """
                UPDATE dim_road_segment
                SET road_name = %s
                WHERE road_code = %s
                  AND (road_name IS NULL OR road_name = 'unknown' OR road_name = '')
                """,
                (name, code),
            )
            updated_total += cur.rowcount

        conn.commit()
    log.info("Updated %d rows in dim_road_segment", updated_total)
    return updated_total


def verify_patch(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT road_name, road_code, COUNT(*) as cnt "
            "FROM dim_road_segment "
            "GROUP BY road_name, road_code "
            "ORDER BY cnt DESC LIMIT 20"
        )
        rows = cur.fetchall()
        log.info("\n--- dim_road_segment after patch (top 20) ---")
        for r in rows:
            log.info("  name=%s code=%s cnt=%d", repr(r[0]), repr(r[1]), r[2])

        cur.execute(
            "SELECT COUNT(*) FROM dim_road_segment WHERE road_name = 'unknown'"
        )
        still_unknown = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dim_road_segment")
        total = cur.fetchone()[0]
        log.info(
            "Still 'unknown': %d / %d (%.1f%%)",
            still_unknown, total,
            100.0 * still_unknown / total if total else 0,
        )


def rebuild_mart_province_road(conn):
    log.info("Rebuilding mart_province_road …")
    with conn.cursor() as cur:
        cur.execute(MART_PROVINCE_ROAD)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT road_name, road_code, SUM(accident_count) as acc "
            "FROM mart_province_road "
            "GROUP BY road_name, road_code "
            "ORDER BY acc DESC LIMIT 20"
        )
        rows = cur.fetchall()
        log.info("\n--- mart_province_road after rebuild (top 20) ---")
        for r in rows:
            log.info("  name=%s code=%s acc=%s", repr(r[0]), repr(r[1]), r[2])

        cur.execute(
            "SELECT COUNT(*) FROM mart_province_road WHERE road_name = 'unknown'"
        )
        still_unknown = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM mart_province_road")
        total = cur.fetchone()[0]
        log.info(
            "mart_province_road still 'unknown': %d / %d",
            still_unknown, total,
        )


def run():
    log.info("Connecting to %s:%s/%s …", DB["host"], DB["port"], DB["dbname"])
    conn = psycopg2.connect(**DB)

    # Step 1: build map from CSV
    road_name_map = build_road_name_map()
    if not road_name_map:
        log.error("No road names found in CSV — aborting")
        return

    # Step 2: patch dim_road_segment
    updated = patch_dim_road_segment(conn, road_name_map)

    # Step 3: verify
    verify_patch(conn)

    # Step 4: rebuild mart_province_road
    rebuild_mart_province_road(conn)

    conn.close()
    log.info("Patch complete. Updated %d dim_road_segment rows.", updated)


if __name__ == "__main__":
    run()
