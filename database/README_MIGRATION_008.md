# Migration 008: Prevent Data Duplication

## Overview

This migration adds UNIQUE constraints to prevent duplicate records in the accident database. It ensures data integrity and makes the CSV import process idempotent (safe to run multiple times).

## Problem Solved

**Before Migration 008:**
- No uniqueness constraints on `fact_accident_event`
- Running import script multiple times created duplicate records
- Mart table counts didn't match fact table counts
- Charts showed incorrect data due to duplicate counting

**After Migration 008:**
- UNIQUE constraints prevent duplicates at database level
- Import script uses `ON CONFLICT DO NOTHING` for idempotent imports
- Duplicate detection within CSV files
- Automatic verification of fact vs mart counts

## Files Changed

### 1. New Migration File
**`008_prevent_duplicates.sql`**
- Removes existing duplicates (keeps first occurrence)
- Adds UNIQUE constraint on `fact_accident_event(event_datetime, geography_id, road_segment_id, csv_year)`
- Adds UNIQUE constraint on `dim_geography(province_name)`
- Adds UNIQUE constraint on `dim_road_segment(road_code, geography_id)`
- Adds UNIQUE constraint on `dim_road_segment(road_name, geography_id)` when road_code is NULL
- Includes verification queries to check for remaining duplicates

### 2. Updated Import Script
**`import_csv_all_years.py`**

**Changes:**
- `dim_geography`: Changed to `ON CONFLICT (province_name) DO UPDATE` to update coordinates
- `dim_road_segment`: Changed to `ON CONFLICT ... DO UPDATE` with separate logic for road_code vs road_name
- `fact_accident_event`: Changed to `ON CONFLICT ... DO NOTHING` to skip duplicates
- Added duplicate detection within CSV files using `seen_in_csv` set
- Added tracking of skipped duplicates (`total_skipped`)
- Added verification step comparing fact vs mart counts
- Added sample verification for เชียงใหม่ province

### 3. Updated SQL Specialist
**`src/agents/sql_specialist.py`**
- Documented UNIQUE constraints in schema description
- Added "Data Quality" section noting no duplicates guarantee
- Updated best practices to reflect idempotent imports

## How to Run

### Step 1: Run Migration (First Time Only)

```bash
# From Agent project root
cd d:\work\musya\Agent

# Connect to PostgreSQL and run migration
psql -h localhost -p 5432 -U postgres -d chat-aio -f database/008_prevent_duplicates.sql
```

**Expected Output:**
```
DELETE 0  (or number of duplicates removed)
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE INDEX
NOTICE: No duplicates found in fact_accident_event - migration successful
NOTICE: No duplicates found in dim_road_segment - migration successful
NOTICE: No duplicates found in dim_geography - migration successful
```

### Step 2: Run Import Script

```bash
# Activate Python virtual environment
# Windows:
.venv\Scripts\activate

# Run import script
python database/import_csv_all_years.py
```

**Expected Output:**
```
======================================================================
  Musya Agent — Import ALL Accident CSV Data (2020–2026)
======================================================================

[1/6] Truncating existing data...
      Done.

[2/6] Upserting dim_source (one per CSV year)...
      source_ids: {2020: 1, 2021: 2, ...}

[3/6] Building dim_geography from all CSV provinces...
      77 provinces in dim_geography.

[4/6] Building dim_road_segment (road_code + geography_id)...
      1234 road segments in dim_road_segment.

[5/6] Inserting fact_accident_event for all years...
      2020:   12345 rows inserted.
      2021:   13456 rows inserted.
      ...
      ── Total: 123456 rows inserted.
      ── Skipped: 0 duplicate rows found in CSV files.

[6/6] Rebuilding mart tables...
      mart_accident_summary: 1234 rows
      mart_province_year:    539 rows
      mart_province_road:    5678 rows
      mart_accident_hotspot: 2345 rows

======================================================================
  Final Row Counts:
    dim_geography                        77 rows
    dim_road_segment                   1234 rows
    fact_accident_event              123456 rows
    mart_province_year                  539 rows
    ...

======================================================================
  Data Verification: Fact vs Mart Counts
======================================================================
  fact_accident_event total:    123456 rows
  mart_province_year total:     123456 accidents
  ✓ PASS: Fact and mart counts match (no duplicates)

  Sample: เชียงใหม่ yearly breakdown
    2020: fact= 1234, mart= 1234 ✓
    2021: fact= 1345, mart= 1345 ✓
    ...
  ✓ PASS: All years match for เชียงใหม่
======================================================================

  Total time: 45.2s
```

### Step 3: Verify (Optional)

```bash
# Connect to database
psql -h localhost -p 5432 -U postgres -d chat-aio

# Check for duplicates in fact table (should return 0)
SELECT event_datetime, geography_id, road_segment_id, csv_year, COUNT(*) as cnt
FROM fact_accident_event
WHERE event_datetime IS NOT NULL
  AND geography_id IS NOT NULL
  AND road_segment_id IS NOT NULL
  AND csv_year IS NOT NULL
GROUP BY event_datetime, geography_id, road_segment_id, csv_year
HAVING COUNT(*) > 1;

# Compare fact vs mart counts
SELECT 
    (SELECT COUNT(*) FROM fact_accident_event) as fact_count,
    (SELECT SUM(accident_count) FROM mart_province_year) as mart_count;

# Should show: fact_count = mart_count
```

## Testing Import Idempotency

Run the import script **twice** to verify it's idempotent:

```bash
# First run
python database/import_csv_all_years.py

# Note the row counts, then run again
python database/import_csv_all_years.py

# Row counts should be IDENTICAL
# Verification should still show ✓ PASS
```

## Uniqueness Definitions

### fact_accident_event
**Key**: `(event_datetime, geography_id, road_segment_id, csv_year)`

**Logic**: Same time + same location + same road + same source year = same accident

**Example**:
- Event 1: 2023-01-15 14:30, เชียงใหม่, ทล.118, year=2023
- Event 2: 2023-01-15 14:30, เชียงใหม่, ทล.118, year=2023
- **Result**: Event 2 is skipped (duplicate)

### dim_geography
**Key**: `province_name`

**Logic**: Same province name = same geography

**Example**:
- Geography 1: province_name = "เชียงใหม่"
- Geography 2: province_name = "เชียงใหม่"
- **Result**: Geography 2 updates coordinates of Geography 1

### dim_road_segment
**Key**: `(road_code, geography_id)` OR `(road_name, geography_id)`

**Logic**: Same road code + province = same road (or same road name + province if no code)

**Example**:
- Road 1: road_code = "118", geography_id = 50 (เชียงใหม่)
- Road 2: road_code = "118", geography_id = 50 (เชียงใหม่)
- **Result**: Road 2 updates attributes of Road 1

## Troubleshooting

### Issue: Migration fails with "duplicate key value violates unique constraint"

**Cause**: Existing duplicates in database

**Solution**: The migration automatically removes duplicates before adding constraints. If it still fails, manually check:

```sql
-- Find duplicates
SELECT event_datetime, geography_id, road_segment_id, csv_year, COUNT(*) as cnt
FROM fact_accident_event
GROUP BY event_datetime, geography_id, road_segment_id, csv_year
HAVING COUNT(*) > 1;

-- Delete duplicates (keep lowest accident_id)
DELETE FROM fact_accident_event
WHERE accident_id NOT IN (
    SELECT MIN(accident_id)
    FROM fact_accident_event
    GROUP BY event_datetime, geography_id, road_segment_id, csv_year
);
```

### Issue: Verification shows fact ≠ mart counts

**Cause**: Mart tables not rebuilt after migration

**Solution**: Rebuild mart tables:

```bash
python database/rebuild_province_marts.py
```

Or re-run the import script which rebuilds marts automatically.

### Issue: CSV duplicates detected

**Cause**: Source CSV files contain duplicate rows

**Solution**: This is normal and handled automatically. The import script will:
1. Detect duplicates within each CSV file
2. Skip duplicate rows
3. Report count in output: `(X CSV duplicates skipped)`

If you want to investigate:
```bash
# Check for duplicates in CSV
python -c "
import csv
from collections import Counter
with open('database/accident2023.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
    keys = [(r['วันที่เกิดเหตุ'], r['เวลา'], r['จังหวัด'], r['สายทาง']) for r in rows]
    dups = [k for k, cnt in Counter(keys).items() if cnt > 1]
    print(f'Found {len(dups)} duplicate keys')
"
```

## Benefits

1. **Data Integrity**: No duplicate accidents in database
2. **Idempotent Imports**: Safe to run import script multiple times
3. **Accurate Charts**: Chart data reflects true accident counts
4. **Consistent Queries**: Fact table and mart tables always match
5. **Performance**: Unique indexes improve query performance
6. **Debugging**: Verification step catches data quality issues early

## Related Files

- Migration: `database/008_prevent_duplicates.sql`
- Import Script: `database/import_csv_all_years.py`
- SQL Specialist: `src/agents/sql_specialist.py`
- Field Mapping: `database/CSV_FIELD_MAPPING.md`
- Database Docs: `doc/DATABASE_API_ARCHITECTURE.md`
