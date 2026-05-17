-- Migration 022: Add district_name column to mart_province_road
-- Allows hotspot road queries to show which district(s) each road passes through.

ALTER TABLE mart_province_road
    ADD COLUMN IF NOT EXISTS district_name VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_prov_road_district
    ON mart_province_road(district_name);
