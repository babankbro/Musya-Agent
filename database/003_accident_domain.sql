-- Accident Domain Schema: fact tables, dimension tables, and analytic marts

-- Road segment dimension
CREATE TABLE IF NOT EXISTS dim_road_segment (
    road_segment_id BIGSERIAL PRIMARY KEY,
    road_name VARCHAR(255),
    road_type VARCHAR(100),
    lane_count INT,
    curvature_type VARCHAR(100),
    slope_type VARCHAR(100),
    speed_limit INT,
    surface_type VARCHAR(100),
    risk_flag BOOLEAN DEFAULT FALSE
);

-- Accident event fact table
CREATE TABLE IF NOT EXISTS fact_accident_event (
    accident_id BIGSERIAL PRIMARY KEY,
    event_datetime TIMESTAMP,
    geography_id BIGINT REFERENCES dim_geography(geography_id),
    road_segment_id BIGINT REFERENCES dim_road_segment(road_segment_id),
    weather_condition VARCHAR(100),
    road_condition VARCHAR(100),
    light_condition VARCHAR(100),
    accident_type VARCHAR(100),
    severity_level VARCHAR(50),
    vehicle_type VARCHAR(100),
    injured_count INT DEFAULT 0,
    death_count INT DEFAULT 0,
    source_id BIGINT REFERENCES dim_source(source_id)
);

CREATE INDEX IF NOT EXISTS idx_accident_datetime ON fact_accident_event(event_datetime);
CREATE INDEX IF NOT EXISTS idx_accident_geo ON fact_accident_event(geography_id);
CREATE INDEX IF NOT EXISTS idx_accident_severity ON fact_accident_event(severity_level);

-- Accident person fact table
CREATE TABLE IF NOT EXISTS fact_accident_person (
    person_event_id BIGSERIAL PRIMARY KEY,
    accident_id BIGINT REFERENCES fact_accident_event(accident_id),
    age INT,
    sex VARCHAR(20),
    role_in_event VARCHAR(100),
    injury_level VARCHAR(100),
    helmet_used BOOLEAN,
    seatbelt_used BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_acc_person_accident ON fact_accident_person(accident_id);

-- Analytic mart: accident summary by month and geography
CREATE TABLE IF NOT EXISTS mart_accident_summary (
    id BIGSERIAL PRIMARY KEY,
    year_no INT NOT NULL,
    month_no INT NOT NULL,
    geography_id BIGINT REFERENCES dim_geography(geography_id),
    accident_count INT DEFAULT 0,
    injured_count INT DEFAULT 0,
    death_count INT DEFAULT 0,
    high_risk_timeband VARCHAR(100),
    dominant_road_cond VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_mart_acc_ym ON mart_accident_summary(year_no, month_no);
CREATE INDEX IF NOT EXISTS idx_mart_acc_geo ON mart_accident_summary(geography_id);

-- Analytic mart: accident hotspots
CREATE TABLE IF NOT EXISTS mart_accident_hotspot (
    hotspot_id BIGSERIAL PRIMARY KEY,
    geography_id BIGINT REFERENCES dim_geography(geography_id),
    road_segment_id BIGINT REFERENCES dim_road_segment(road_segment_id),
    accident_count INT DEFAULT 0,
    injured_count INT DEFAULT 0,
    death_count INT DEFAULT 0,
    hotspot_score DECIMAL(10,2) DEFAULT 0,
    dominant_timeband VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_hotspot_score ON mart_accident_hotspot(hotspot_score DESC);
