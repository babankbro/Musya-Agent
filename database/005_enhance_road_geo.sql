-- Migration: Enhance dim_road_segment to link to geography (province)
-- and add road_code from CSV รหัสสายทาง column

ALTER TABLE dim_road_segment
    ADD COLUMN IF NOT EXISTS road_code    VARCHAR(50),
    ADD COLUMN IF NOT EXISTS geography_id BIGINT REFERENCES dim_geography(geography_id),
    ADD COLUMN IF NOT EXISTS km_marker    DECIMAL(10,3),
    ADD COLUMN IF NOT EXISTS cause_type   VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_road_seg_geo  ON dim_road_segment(geography_id);
CREATE INDEX IF NOT EXISTS idx_road_seg_code ON dim_road_segment(road_code);
