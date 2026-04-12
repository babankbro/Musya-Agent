-- Migration 007: Support all years 2020-2026 with province-level query capability
-- Changes:
--   1. fact_accident_event: add serious_injured, csv_year (for Excel-date-only files)
--   2. mart_accident_summary: add province_name denorm for faster province queries
--   3. mart_province_year / mart_province_road: add serious_injured column
--   4. New mart: mart_province_year_road — one row per (province, road, year) for fast lookup

-- ── 1. fact_accident_event additions ──────────────────────────────────────────
ALTER TABLE fact_accident_event
    ADD COLUMN IF NOT EXISTS serious_injured INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS csv_year        INT;   -- source CSV year (2020-2026)

CREATE INDEX IF NOT EXISTS idx_accident_csvyear ON fact_accident_event(csv_year);

-- ── 2. mart_accident_summary: add province_name for direct province filtering ──
ALTER TABLE mart_accident_summary
    ADD COLUMN IF NOT EXISTS province_name VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_mart_summary_prov ON mart_accident_summary(province_name);

-- ── 3. mart_province_year: add serious_injured ─────────────────────────────────
ALTER TABLE mart_province_year
    ADD COLUMN IF NOT EXISTS serious_injured INT DEFAULT 0;

-- ── 4. mart_province_road: add serious_injured ────────────────────────────────
ALTER TABLE mart_province_road
    ADD COLUMN IF NOT EXISTS serious_injured INT DEFAULT 0;

-- ── 5. New view: province yearly summary (fast query without JOIN) ─────────────
CREATE OR REPLACE VIEW v_province_year_summary AS
SELECT
    py.year_no,
    py.province_name,
    py.accident_count,
    py.injured_count,
    py.serious_injured,
    py.death_count,
    py.road_count,
    py.top_vehicle,
    py.top_cause,
    py.top_timeband,
    py.top_weather,
    g.latitude,
    g.longitude
FROM mart_province_year py
LEFT JOIN dim_geography g ON py.geography_id = g.geography_id;

-- ── 6. New view: province road yearly (fast lookup by province + year) ──────────
CREATE OR REPLACE VIEW v_province_road_year AS
SELECT
    pr.year_no,
    pr.province_name,
    pr.road_name,
    pr.road_code,
    pr.accident_count,
    pr.injured_count,
    pr.serious_injured,
    pr.death_count,
    pr.hotspot_score,
    pr.dominant_cause,
    pr.dominant_vehicle
FROM mart_province_road pr;
