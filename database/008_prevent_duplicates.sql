-- Migration 008: Prevent duplicate records in fact and dimension tables
-- Purpose: Add UNIQUE constraints to prevent data duplication during CSV imports
-- Date: 2026-04-06

-- ══════════════════════════════════════════════════════════════════════════════
-- 1. fact_accident_event: Prevent duplicate accident events
-- ══════════════════════════════════════════════════════════════════════════════
-- Uniqueness definition: Same time + location + road + source year = same accident
-- This allows the import script to be idempotent (safe to run multiple times)

-- First, remove any existing duplicates before adding constraint
-- Keep only the first occurrence (lowest accident_id) of each duplicate group
DELETE FROM fact_accident_event
WHERE accident_id NOT IN (
    SELECT MIN(accident_id)
    FROM fact_accident_event
    WHERE event_datetime IS NOT NULL
      AND geography_id IS NOT NULL
      AND road_segment_id IS NOT NULL
      AND csv_year IS NOT NULL
    GROUP BY event_datetime, geography_id, road_segment_id, csv_year
);

-- Add unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_accident_event_unique
    ON fact_accident_event(event_datetime, geography_id, road_segment_id, csv_year)
    WHERE event_datetime IS NOT NULL 
      AND geography_id IS NOT NULL 
      AND road_segment_id IS NOT NULL
      AND csv_year IS NOT NULL;

COMMENT ON INDEX idx_accident_event_unique IS 
    'Prevents duplicate accident events: same time + location + road + year = same accident';

-- ══════════════════════════════════════════════════════════════════════════════
-- 2. dim_road_segment: Prevent duplicate road segments
-- ══════════════════════════════════════════════════════════════════════════════
-- Uniqueness definition: Same road_code + province = same road segment
-- If road_code is NULL, use road_name + province

-- Remove duplicates: keep first occurrence
DELETE FROM dim_road_segment
WHERE road_segment_id NOT IN (
    SELECT MIN(road_segment_id)
    FROM dim_road_segment
    WHERE geography_id IS NOT NULL
    GROUP BY 
        COALESCE(road_code, road_name),
        geography_id
);

-- Add unique constraint for road_code + geography
CREATE UNIQUE INDEX IF NOT EXISTS idx_road_segment_unique
    ON dim_road_segment(road_code, geography_id)
    WHERE road_code IS NOT NULL 
      AND geography_id IS NOT NULL;

-- Add unique constraint for road_name + geography (when road_code is NULL)
CREATE UNIQUE INDEX IF NOT EXISTS idx_road_segment_name_unique
    ON dim_road_segment(road_name, geography_id)
    WHERE road_code IS NULL 
      AND road_name IS NOT NULL
      AND geography_id IS NOT NULL;

COMMENT ON INDEX idx_road_segment_unique IS 
    'Prevents duplicate roads: same road_code + province = same road';
COMMENT ON INDEX idx_road_segment_name_unique IS 
    'Prevents duplicate roads when road_code is NULL: same road_name + province = same road';

-- ══════════════════════════════════════════════════════════════════════════════
-- 3. dim_geography: Prevent duplicate provinces
-- ══════════════════════════════════════════════════════════════════════════════
-- Uniqueness definition: Same province_name = same geography

-- Remove duplicates: keep first occurrence (with coordinates if available)
DELETE FROM dim_geography
WHERE geography_id NOT IN (
    SELECT MIN(geography_id)
    FROM dim_geography
    WHERE province_name IS NOT NULL
    GROUP BY province_name
);

-- Add unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_geography_province_unique
    ON dim_geography(province_name)
    WHERE province_name IS NOT NULL;

COMMENT ON INDEX idx_geography_province_unique IS 
    'Prevents duplicate provinces: same province_name = same geography';

-- ══════════════════════════════════════════════════════════════════════════════
-- 4. Verification queries (for testing)
-- ══════════════════════════════════════════════════════════════════════════════

-- Check for remaining duplicates in fact_accident_event
-- (Should return 0 rows after migration)
DO $$
DECLARE
    dup_count INT;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT event_datetime, geography_id, road_segment_id, csv_year, COUNT(*) as cnt
        FROM fact_accident_event
        WHERE event_datetime IS NOT NULL
          AND geography_id IS NOT NULL
          AND road_segment_id IS NOT NULL
          AND csv_year IS NOT NULL
        GROUP BY event_datetime, geography_id, road_segment_id, csv_year
        HAVING COUNT(*) > 1
    ) duplicates;
    
    IF dup_count > 0 THEN
        RAISE WARNING 'Found % duplicate groups in fact_accident_event after cleanup', dup_count;
    ELSE
        RAISE NOTICE 'No duplicates found in fact_accident_event - migration successful';
    END IF;
END $$;

-- Check for remaining duplicates in dim_road_segment
DO $$
DECLARE
    dup_count INT;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT COALESCE(road_code, road_name) as road_key, geography_id, COUNT(*) as cnt
        FROM dim_road_segment
        WHERE geography_id IS NOT NULL
        GROUP BY COALESCE(road_code, road_name), geography_id
        HAVING COUNT(*) > 1
    ) duplicates;
    
    IF dup_count > 0 THEN
        RAISE WARNING 'Found % duplicate groups in dim_road_segment after cleanup', dup_count;
    ELSE
        RAISE NOTICE 'No duplicates found in dim_road_segment - migration successful';
    END IF;
END $$;

-- Check for remaining duplicates in dim_geography
DO $$
DECLARE
    dup_count INT;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT province_name, COUNT(*) as cnt
        FROM dim_geography
        WHERE province_name IS NOT NULL
        GROUP BY province_name
        HAVING COUNT(*) > 1
    ) duplicates;
    
    IF dup_count > 0 THEN
        RAISE WARNING 'Found % duplicate groups in dim_geography after cleanup', dup_count;
    ELSE
        RAISE NOTICE 'No duplicates found in dim_geography - migration successful';
    END IF;
END $$;

-- ══════════════════════════════════════════════════════════════════════════════
-- Migration complete
-- ══════════════════════════════════════════════════════════════════════════════
