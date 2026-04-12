-- Migration 009: Add LATITUDE and LONGITUDE to fact_accident_event
-- Purpose: Store exact accident location coordinates for mapping and spatial analysis
-- Date: 2026-04-06

-- Add latitude and longitude columns to fact_accident_event
ALTER TABLE fact_accident_event
    ADD COLUMN IF NOT EXISTS latitude  DECIMAL(10, 7),
    ADD COLUMN IF NOT EXISTS longitude DECIMAL(10, 7);

-- Add index for spatial queries
CREATE INDEX IF NOT EXISTS idx_accident_coordinates 
    ON fact_accident_event(latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Add comment
COMMENT ON COLUMN fact_accident_event.latitude IS 
    'Latitude coordinate of accident location (from CSV LATITUDE column)';
COMMENT ON COLUMN fact_accident_event.longitude IS 
    'Longitude coordinate of accident location (from CSV LONGITUDE column)';

-- Verify columns were added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'fact_accident_event' 
        AND column_name IN ('latitude', 'longitude')
    ) THEN
        RAISE NOTICE 'Migration 009 complete: latitude and longitude columns added to fact_accident_event';
    ELSE
        RAISE WARNING 'Migration 009 failed: columns not found';
    END IF;
END $$;
