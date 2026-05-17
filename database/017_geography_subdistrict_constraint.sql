-- Migration 017: Fix dim_geography to support subdistrict-level rows
--
-- Problem: existing UNIQUE is on province_name alone (partial index).
-- This blocks inserting district/subdistrict-level geography rows for
-- the same province when migrating from accident_all_with_subdistrict.csv.
--
-- Solution:
--   1. Drop the province-only unique index
--   2. Add new UNIQUE on (province_name, district_name, subdistrict_name)
--      to allow multiple rows per province at different levels
--   3. Backfill empty district_name / subdistrict_name to '' (not NULL)
--      so the new unique constraint works (NULL != NULL in SQL)

-- Step 1: normalise NULLs → '' so the composite unique index is consistent
UPDATE dim_geography SET district_name    = '' WHERE district_name    IS NULL;
UPDATE dim_geography SET subdistrict_name = '' WHERE subdistrict_name IS NULL;
UPDATE dim_geography SET district_code    = '' WHERE district_code    IS NULL;
UPDATE dim_geography SET subdistrict_code = '' WHERE subdistrict_code IS NULL;

-- Step 2: drop old province-only unique index
DROP INDEX IF EXISTS idx_geography_province_unique;

-- Step 3: add composite unique index
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_geography_province_district_sub
    ON dim_geography (province_name, district_name, subdistrict_name)
    WHERE province_name IS NOT NULL;
