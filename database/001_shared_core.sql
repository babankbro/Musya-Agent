-- Shared Core Schema: dimension tables used across all domains
-- Run against the existing chat-aio database

-- Geography dimension
CREATE TABLE IF NOT EXISTS dim_geography (
    geography_id BIGSERIAL PRIMARY KEY,
    country_code VARCHAR(10) DEFAULT 'TH',
    province_code VARCHAR(20),
    province_name VARCHAR(255),
    district_code VARCHAR(20),
    district_name VARCHAR(255),
    subdistrict_code VARCHAR(20),
    subdistrict_name VARCHAR(255),
    latitude DECIMAL(10,6),
    longitude DECIMAL(10,6)
);

CREATE INDEX IF NOT EXISTS idx_geo_province ON dim_geography(province_name);
CREATE INDEX IF NOT EXISTS idx_geo_district ON dim_geography(district_name);

-- Time dimension
CREATE TABLE IF NOT EXISTS dim_time (
    time_id BIGSERIAL PRIMARY KEY,
    full_date DATE UNIQUE,
    day_of_week VARCHAR(20),
    week_no INT,
    month_no INT,
    month_name VARCHAR(20),
    quarter_no INT,
    year_no INT,
    hour_no INT
);

CREATE INDEX IF NOT EXISTS idx_time_date ON dim_time(full_date);
CREATE INDEX IF NOT EXISTS idx_time_year_month ON dim_time(year_no, month_no);

-- Population group dimension
CREATE TABLE IF NOT EXISTS dim_population_group (
    group_id BIGSERIAL PRIMARY KEY,
    age_group VARCHAR(100),
    sex VARCHAR(20),
    occupation_group VARCHAR(100),
    vulnerable_group VARCHAR(255)
);

-- Facility dimension
CREATE TABLE IF NOT EXISTS dim_facility (
    facility_id BIGSERIAL PRIMARY KEY,
    facility_code VARCHAR(50),
    facility_name VARCHAR(255),
    facility_type VARCHAR(100),
    geography_id BIGINT REFERENCES dim_geography(geography_id),
    service_level VARCHAR(100)
);

-- Data source dimension
CREATE TABLE IF NOT EXISTS dim_source (
    source_id BIGSERIAL PRIMARY KEY,
    source_name VARCHAR(255),
    source_type VARCHAR(100),
    owner_org VARCHAR(255),
    update_frequency VARCHAR(50),
    quality_level VARCHAR(50)
);

-- Populate time dimension for 2020-2030
INSERT INTO dim_time (full_date, day_of_week, week_no, month_no, month_name, quarter_no, year_no, hour_no)
SELECT
    d::DATE,
    TO_CHAR(d, 'Day'),
    EXTRACT(WEEK FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    TO_CHAR(d, 'Month'),
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(YEAR FROM d)::INT,
    0
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) AS d
ON CONFLICT (full_date) DO NOTHING;
