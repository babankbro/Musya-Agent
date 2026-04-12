-- Migration: Add province-level analytic mart tables
-- mart_province_year  : yearly accident summary per province
-- mart_province_road  : roads per province with accident breakdown per year

-- Yearly accident summary by province
CREATE TABLE IF NOT EXISTS mart_province_year (
    id              BIGSERIAL PRIMARY KEY,
    year_no         INT NOT NULL,
    geography_id    BIGINT REFERENCES dim_geography(geography_id),
    province_name   VARCHAR(255),
    accident_count  INT DEFAULT 0,
    injured_count   INT DEFAULT 0,
    death_count     INT DEFAULT 0,
    serious_injured INT DEFAULT 0,
    road_count      INT DEFAULT 0,
    top_vehicle     VARCHAR(100),
    top_cause       VARCHAR(255),
    top_timeband    VARCHAR(100),
    top_weather     VARCHAR(100)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_province_year_uniq
    ON mart_province_year(year_no, geography_id);
CREATE INDEX IF NOT EXISTS idx_province_year_prov
    ON mart_province_year(province_name);
CREATE INDEX IF NOT EXISTS idx_province_year_yr
    ON mart_province_year(year_no);

-- Road accident breakdown per province per year
CREATE TABLE IF NOT EXISTS mart_province_road (
    id              BIGSERIAL PRIMARY KEY,
    year_no         INT NOT NULL,
    geography_id    BIGINT REFERENCES dim_geography(geography_id),
    province_name   VARCHAR(255),
    road_segment_id BIGINT REFERENCES dim_road_segment(road_segment_id),
    road_name       VARCHAR(255),
    road_code       VARCHAR(50),
    accident_count  INT DEFAULT 0,
    injured_count   INT DEFAULT 0,
    death_count     INT DEFAULT 0,
    hotspot_score   DECIMAL(12,2) DEFAULT 0,
    dominant_cause  VARCHAR(255),
    dominant_vehicle VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_prov_road_geo_yr
    ON mart_province_road(geography_id, year_no);
CREATE INDEX IF NOT EXISTS idx_prov_road_prov
    ON mart_province_road(province_name);
CREATE INDEX IF NOT EXISTS idx_prov_road_score
    ON mart_province_road(hotspot_score DESC);
