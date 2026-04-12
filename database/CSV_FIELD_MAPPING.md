# CSV Field Mapping: Thai to English

## Overview
This document maps Thai column names from accident CSV files (2020-2026) to English database field names for the Agent project.

---

## CSV Column Structure (38 columns)

### 1. Date/Time Fields

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 1 | ปีที่เกิดเหตุ | accident_year | INT | Year of accident occurrence |
| 2 | วันที่เกิดเหตุ | accident_date | DATE/SERIAL | Date of accident (M/D/YYYY or Excel serial) |
| 3 | เวลา | accident_time | TIME | Time of accident (HH:MM) |
| 4 | วันที่รายงาน | report_date | DATE | Date reported |
| 5 | เวลาที่รายงาน | report_time | TIME | Time reported |

**Combined**: `accident_date` + `accident_time` → `event_datetime` (TIMESTAMP)

---

### 2. Identification & Agency Fields

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 6 | ACC_CODE | accident_code | VARCHAR(50) | Accident reference code |
| 7 | หน่วยงาน | agency | VARCHAR(255) | Reporting agency |
| 8 | สายทางหน่วยงาน | agency_route | VARCHAR(255) | Agency route classification |

**Note**: 2026 CSV is missing `ACC_CODE` column, causing all subsequent columns to shift left.

---

### 3. Location Fields

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 9 | รหัสสายทาง | road_code | VARCHAR(50) | Road code identifier |
| 10 | สายทาง | road_name | VARCHAR(255) | Road name |
| 11 | KM | kilometer_marker | DECIMAL(10,2) | Kilometer marker on road |
| 12 | จังหวัด | province | VARCHAR(255) | Province name |
| 18 | LATITUDE | latitude | DECIMAL(10,6) | GPS latitude |
| 19 | LONGITUDE | longitude | DECIMAL(10,6) | GPS longitude |

**Mapping to Database**:
- `province` → `dim_geography.province_name`
- `road_name` + `road_code` → `dim_road_segment.road_name`, `road_code`
- `latitude`, `longitude` → `dim_geography.latitude`, `longitude`
- `kilometer_marker` → `dim_road_segment.km_marker`

---

### 4. Accident Details Fields

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 13 | รถคันที่1 | primary_vehicle | VARCHAR(100) | Primary vehicle involved |
| 14 | บริเวณที่เกิดเหตุ | accident_location_desc | TEXT | Location description |
| 15 | มูลเหตุสันนิษฐาน | presumed_cause | VARCHAR(255) | Presumed cause of accident |
| 16 | ลักษณะการเกิดเหตุ | accident_type | VARCHAR(100) | Type/nature of accident |
| 17 | สภาพอากาศ | weather_condition | VARCHAR(100) | Weather condition |

**Mapping to Database**:
- `primary_vehicle` → `fact_accident_event.vehicle_type`
- `presumed_cause` → Used in mart aggregations as `dominant_cause`
- `accident_type` → `fact_accident_event.accident_type`
- `weather_condition` → `fact_accident_event.weather_condition`

---

### 5. Vehicle Count Fields (Columns 20-34)

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 20 | รถที่เกิดเหตุ | total_vehicles | INT | Total vehicles involved |
| 21 | รถและคนที่เกิดเหตุ | total_vehicles_and_people | INT | Total vehicles + people |
| 22 | รถจักรยานยนต์ | motorcycle_count | INT | Motorcycles |
| 23 | รถสามล้อเครื่อง | tricycle_count | INT | Motorized tricycles |
| 24 | รถยนต์นั่งส่วนบุคคล | private_car_count | INT | Private cars |
| 25 | รถตู้ | van_count | INT | Vans |
| 26 | รถปิคอัพโดยสาร | pickup_passenger_count | INT | Passenger pickups |
| 27 | รถโดยสารมากกว่า4ล้อ | bus_count | INT | Buses (>4 wheels) |
| 28 | รถปิคอัพบรรทุก4ล้อ | pickup_truck_4w_count | INT | 4-wheel pickup trucks |
| 29 | รถบรรทุก6ล้อ | truck_6w_count | INT | 6-wheel trucks |
| 30 | รถบรรทุกไม่เกิน10ล้อ | truck_up_to_10w_count | INT | Trucks ≤10 wheels |
| 31 | รถบรรทุกมากกว่า10ล้อ | truck_over_10w_count | INT | Trucks >10 wheels |
| 32 | รถอีแต๋น | etaen_count | INT | E-taen vehicles |
| 33 | รถอื่นๆ | other_vehicle_count | INT | Other vehicles |
| 34 | คนเดินเท้า | pedestrian_count | INT | Pedestrians |

**Note**: These vehicle counts are currently **NOT stored** in the database. They exist in CSV but are not imported.

---

### 6. Casualty Fields

| # | Thai Column | English Field | Data Type | Description |
|---|-------------|---------------|-----------|-------------|
| 35 | ผู้เสียชีวิต | death_count | INT | Number of deaths |
| 36 | ผู้บาดเจ็บสาหัส | serious_injured | INT | Seriously injured |
| 37 | ผู้บาดเจ็บเล็กน้อย | minor_injured | INT | Minor injuries |
| 38 | รวมจำนวนผู้บาดเจ็บ | total_injured | INT | Total injured |

**Mapping to Database**:
- `death_count` → `fact_accident_event.death_count`
- `serious_injured` → `fact_accident_event.serious_injured` (added in migration 007)
- `total_injured` → `fact_accident_event.injured_count`
- `minor_injured` → **NOT stored** (can be calculated: `total_injured - serious_injured`)

---

## Current Database Schema Mapping

### fact_accident_event (Main Fact Table)

| Database Column | CSV Source | Transformation |
|----------------|------------|----------------|
| `accident_id` | AUTO | BIGSERIAL PRIMARY KEY |
| `event_datetime` | `วันที่เกิดเหตุ` + `เวลา` | Combined, handles Excel serial dates |
| `geography_id` | `จังหวัด` | FK to `dim_geography` (upserted by province name) |
| `road_segment_id` | `สายทาง` + `รหัสสายทาง` | FK to `dim_road_segment` |
| `weather_condition` | `สภาพอากาศ` | Direct mapping |
| `road_condition` | N/A | **NOT in CSV** (always NULL) |
| `light_condition` | N/A | **NOT in CSV** (always NULL) |
| `accident_type` | `ลักษณะการเกิดเหตุ` | Direct mapping |
| `severity_level` | Calculated | Based on `death_count` > 0 → "เสียชีวิต", else "บาดเจ็บ" |
| `vehicle_type` | `รถคันที่1` | Primary vehicle type |
| `injured_count` | `รวมจำนวนผู้บาดเจ็บ` | Direct mapping |
| `death_count` | `ผู้เสียชีวิต` | Direct mapping |
| `serious_injured` | `ผู้บาดเจ็บสาหัส` | Added in migration 007 |
| `csv_year` | `ปีที่เกิดเหตุ` | Source CSV year (2020-2026) |
| `source_id` | Derived | FK to `dim_source` (one per CSV file) |

---

### dim_geography (Geography Dimension)

| Database Column | CSV Source | Notes |
|----------------|------------|-------|
| `geography_id` | AUTO | BIGSERIAL PRIMARY KEY |
| `country_code` | Fixed | Always 'TH' |
| `province_code` | N/A | NULL (not in CSV) |
| `province_name` | `จังหวัด` | Normalized, trimmed |
| `district_code` | N/A | NULL (not in CSV) |
| `district_name` | N/A | NULL (not in CSV) |
| `subdistrict_code` | N/A | NULL (not in CSV) |
| `subdistrict_name` | N/A | NULL (not in CSV) |
| `latitude` | `LATITUDE` | First non-zero value per province |
| `longitude` | `LONGITUDE` | First non-zero value per province |

---

### dim_road_segment (Road Dimension)

| Database Column | CSV Source | Notes |
|----------------|------------|-------|
| `road_segment_id` | AUTO | BIGSERIAL PRIMARY KEY |
| `road_name` | `สายทาง` | Normalized, trimmed |
| `road_code` | `รหัสสายทาง` | Added in migration 005 |
| `geography_id` | `จังหวัด` | Linked via province, added in migration 005 |
| `km_marker` | `KM` | Added in migration 005 |
| `road_type` | N/A | NULL (not in CSV) |
| `lane_count` | N/A | NULL (not in CSV) |
| `curvature_type` | N/A | NULL (not in CSV) |
| `slope_type` | N/A | NULL (not in CSV) |
| `speed_limit` | N/A | NULL (not in CSV) |
| `surface_type` | N/A | NULL (not in CSV) |
| `risk_flag` | N/A | FALSE (default) |

---

## Derived/Calculated Fields

### Timeband Classification
**Source**: `event_datetime` (hour component)

| Hour Range | Thai Value | English Value |
|------------|-----------|---------------|
| 06:00-11:59 | เช้า (06-12) | Morning (06-12) |
| 12:00-17:59 | กลางวัน (12-18) | Afternoon (12-18) |
| 18:00-23:59 | เย็น/กลางคืน (18-24) | Evening/Night (18-24) |
| 00:00-05:59 | กลางคืน (00-06) | Night (00-06) |

**Used in**: `mart_accident_summary.high_risk_timeband`, `mart_accident_hotspot.dominant_timeband`, `mart_province_year.top_timeband`

---

### Severity Level Classification
**Source**: `death_count`, `injured_count`

| Condition | Thai Value | English Value |
|-----------|-----------|---------------|
| `death_count` > 0 | เสียชีวิต | Fatal |
| `injured_count` > 0 | บาดเจ็บ | Injury |
| Otherwise | รอดปลอดภัย | No Injury |

**Used in**: `fact_accident_event.severity_level`

---

## Fields NOT Currently Imported

The following CSV fields are **read but not stored** in the database:

1. **Report Date/Time**: `วันที่รายงาน`, `เวลาที่รายงาน`
2. **Accident Code**: `ACC_CODE`
3. **Agency Info**: `หน่วยงาน`, `สายทางหน่วยงาน`
4. **Location Description**: `บริเวณที่เกิดเหตุ`
5. **Presumed Cause**: `มูลเหตุสันนิษฐาน` (only used in aggregations, not stored raw)
6. **Vehicle Counts**: All 15 vehicle type count columns (22-34)
7. **Minor Injured**: `ผู้บาดเจ็บเล็กน้อย`
8. **Total Vehicles**: `รถที่เกิดเหตุ`, `รถและคนที่เกิดเหตุ`

---

## Data Quality Issues & Transformations

### 1. Excel Serial Date Handling
- **Years 2024-2026**: `วันที่เกิดเหตุ` is an Excel serial number (e.g., "45292")
- **Transformation**: `EXCEL_EPOCH (1899-12-30) + serial days`
- **Years 2020-2023**: Standard date strings "M/D/YYYY"

### 2. Column Shift in 2026
- **Issue**: `ACC_CODE` column missing in 2026 CSV
- **Detection**: Check if `ACC_CODE` contains Thai characters (should be numeric)
- **Fix**: Insert empty string at position 0, shift all values right

### 3. Province Name Normalization
- **Trimming**: Remove leading/trailing whitespace
- **Validation**: Skip if empty or > 50 characters
- **Deduplication**: Case-sensitive exact match

### 4. Coordinate Validation
- **Rule**: Skip if `LATITUDE` or `LONGITUDE` is 0.0 or empty
- **Strategy**: Use first valid coordinate per province

---

## Proposed English Field Names (for future migration)

### Option A: Minimal Renaming (Keep Current Structure)
Keep current English field names in `fact_accident_event`, only add comments:

```sql
COMMENT ON COLUMN fact_accident_event.event_datetime IS 'วันที่เกิดเหตุ + เวลา';
COMMENT ON COLUMN fact_accident_event.weather_condition IS 'สภาพอากาศ';
COMMENT ON COLUMN fact_accident_event.accident_type IS 'ลักษณะการเกิดเหตุ';
-- etc.
```

### Option B: Full Restructure (New Import Table)
Create a staging table with exact CSV column names:

```sql
CREATE TABLE staging_accident_csv (
    accident_year INT,              -- ปีที่เกิดเหตุ
    accident_date VARCHAR(50),      -- วันที่เกิดเหตุ
    accident_time VARCHAR(10),      -- เวลา
    report_date VARCHAR(50),        -- วันที่รายงาน
    report_time VARCHAR(10),        -- เวลาที่รายงาน
    accident_code VARCHAR(50),      -- ACC_CODE
    agency VARCHAR(255),            -- หน่วยงาน
    agency_route VARCHAR(255),      -- สายทางหน่วยงาน
    road_code VARCHAR(50),          -- รหัสสายทาง
    road_name VARCHAR(255),         -- สายทาง
    kilometer_marker DECIMAL(10,2), -- KM
    province VARCHAR(255),          -- จังหวัด
    primary_vehicle VARCHAR(100),   -- รถคันที่1
    location_desc TEXT,             -- บริเวณที่เกิดเหตุ
    presumed_cause VARCHAR(255),    -- มูลเหตุสันนิษฐาน
    accident_type VARCHAR(100),     -- ลักษณะการเกิดเหตุ
    weather_condition VARCHAR(100), -- สภาพอากาศ
    latitude DECIMAL(10,6),         -- LATITUDE
    longitude DECIMAL(10,6),        -- LONGITUDE
    total_vehicles INT,             -- รถที่เกิดเหตุ
    total_vehicles_people INT,      -- รถและคนที่เกิดเหตุ
    motorcycle_count INT,           -- รถจักรยานยนต์
    tricycle_count INT,             -- รถสามล้อเครื่อง
    private_car_count INT,          -- รถยนต์นั่งส่วนบุคคล
    van_count INT,                  -- รถตู้
    pickup_passenger_count INT,     -- รถปิคอัพโดยสาร
    bus_count INT,                  -- รถโดยสารมากกว่า4ล้อ
    pickup_truck_4w_count INT,      -- รถปิคอัพบรรทุก4ล้อ
    truck_6w_count INT,             -- รถบรรทุก6ล้อ
    truck_up_to_10w_count INT,      -- รถบรรทุกไม่เกิน10ล้อ
    truck_over_10w_count INT,       -- รถบรรทุกมากกว่า10ล้อ
    etaen_count INT,                -- รถอีแต๋น
    other_vehicle_count INT,        -- รถอื่นๆ
    pedestrian_count INT,           -- คนเดินเท้า
    death_count INT,                -- ผู้เสียชีวิต
    serious_injured INT,            -- ผู้บาดเจ็บสาหัส
    minor_injured INT,              -- ผู้บาดเจ็บเล็กน้อย
    total_injured INT               -- รวมจำนวนผู้บาดเจ็บ
);
```

Then transform via SQL:
```sql
INSERT INTO fact_accident_event (event_datetime, geography_id, ...)
SELECT 
    parse_datetime(accident_date, accident_time),
    (SELECT geography_id FROM dim_geography WHERE province_name = province),
    ...
FROM staging_accident_csv;
```

---

## Recommendations

### Short Term (Current Approach)
✅ **Keep current approach**: Direct Python transformation in `import_csv_all_years.py`
- Pros: Fast, flexible, handles data quirks well
- Cons: Logic scattered in Python code

### Medium Term (Add Documentation)
📝 **Add SQL comments** to existing tables documenting Thai field mappings
```sql
-- Migration 008: Add field documentation
COMMENT ON TABLE fact_accident_event IS 'Accident event facts from CSV files (2020-2026)';
COMMENT ON COLUMN fact_accident_event.event_datetime IS 'Combined from วันที่เกิดเหตุ + เวลา';
COMMENT ON COLUMN fact_accident_event.weather_condition IS 'สภาพอากาศ (Weather condition)';
-- etc.
```

### Long Term (If Needed)
🔄 **Create staging table** if:
- Need to preserve raw CSV data
- Want to re-process with different logic
- Need audit trail of transformations

---

## Quick Reference: Python → SQL Mapping

```python
# Current import logic (simplified)
row = {
    "วันที่เกิดเหตุ": "45292",
    "เวลา": "14:30",
    "จังหวัด": "เชียงใหม่",
    "สายทาง": "ทล.118",
    "รหัสสายทาง": "118",
    "ผู้เสียชีวิต": "1",
    "รวมจำนวนผู้บาดเจ็บ": "2",
    "ผู้บาดเจ็บสาหัส": "1",
    # ...
}

# Transforms to SQL INSERT:
INSERT INTO fact_accident_event (
    event_datetime,        -- parse_datetime(วันที่เกิดเหตุ, เวลา)
    geography_id,          -- lookup จังหวัด → dim_geography
    road_segment_id,       -- lookup สายทาง+รหัสสายทาง → dim_road_segment
    death_count,           -- ผู้เสียชีวิต
    injured_count,         -- รวมจำนวนผู้บาดเจ็บ
    serious_injured,       -- ผู้บาดเจ็บสาหัส
    csv_year               -- ปีที่เกิดเหตุ
) VALUES (
    '2024-01-15 14:30:00',
    123,  -- geography_id for เชียงใหม่
    456,  -- road_segment_id for ทล.118
    1,
    2,
    1,
    2024
);
```
