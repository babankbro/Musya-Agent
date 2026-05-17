-- Migration 024: Drop road_condition and light_condition from fact_accident_event
-- These columns were always NULL (not present in CSV source data)

ALTER TABLE fact_accident_event
    DROP COLUMN IF EXISTS road_condition,
    DROP COLUMN IF EXISTS light_condition;
