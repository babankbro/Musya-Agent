# Database API Architecture - Agent Project

## Overview

The Agent project uses a **PostgreSQL database** with a multi-layered architecture designed for accident data analytics and RAG (Retrieval-Augmented Generation). Vector search is handled natively via the **pgvector** extension (replaces standalone ChromaDB), keeping all data in a single PostgreSQL instance. The database supports both async (FastAPI endpoints) and sync (CrewAI tools) access patterns.

---

## Database Connection Architecture

### Connection Pools (`src/db/pool.py`)

The system maintains **two separate connection pools**:

#### 1. **Async Pool** (for FastAPI endpoints)
- **Library**: `asyncpg`
- **Pool Size**: 2-10 connections
- **Usage**: API endpoints, async operations
- **Lifecycle**: Created on app startup, closed on shutdown

```python
async def get_async_pool() -> asyncpg.Pool:
    # Returns singleton async connection pool
    # Config: host, port, database, user, password from settings
```

#### 2. **Sync Pool** (for CrewAI tools)
- **Library**: `psycopg2.pool.ThreadedConnectionPool`
- **Pool Size**: 1-5 connections
- **Usage**: Agent tools, synchronous queries
- **Thread-safe**: Yes (ThreadedConnectionPool)

```python
def get_sync_pool() -> psycopg2.pool.ThreadedConnectionPool:
    # Returns singleton sync connection pool
    # Used by all agent tools for database queries
```

### Query Helper Function

```python
def query_db(sql: str, params: tuple | None = None) -> list[dict]:
    """
    Execute read-only SQL query and return results as list of dicts.
    
    - Automatically manages connection from pool
    - Converts rows to dictionaries with column names as keys
    - Used by all agent tools (chart_builder, accident tools, etc.)
    """
```

---

## Database Schema Layers

### Layer 1: Shared Core Dimensions (`001_shared_core.sql`)

**Purpose**: Common dimension tables used across all domains

#### Tables:
1. **`dim_geography`** - Geographic hierarchy
   - Columns: `geography_id`, `province_name`, `district_name`, `subdistrict_name`, `latitude`, `longitude`
   - Indexes: `province_name`, `district_name`
   - **Usage**: Links all accident events to geographic locations

2. **`dim_time`** - Time dimension (2020-2030)
   - Columns: `time_id`, `full_date`, `day_of_week`, `month_no`, `year_no`, `hour_no`
   - Indexes: `full_date`, `(year_no, month_no)`
   - **Pre-populated**: All dates from 2020-01-01 to 2030-12-31

3. **`dim_population_group`** - Demographics
   - Age groups, sex, occupation, vulnerable groups

4. **`dim_facility`** - Health facilities
   - Linked to geography via `geography_id`

5. **`dim_source`** - Data source metadata
   - Tracks data quality, update frequency, owner organization

---

### Layer 2: Document RAG (`002_document_rag.sql`)

**Purpose**: Support document retrieval and indicator catalog

#### Tables:
1. **`document_registry`** - Document metadata
   - Tracks uploaded documents for RAG
   - Fields: `title`, `topic`, `document_type`, `effective_date`, `status`

2. **`document_chunks`** - Document chunks metadata (**legacy, currently empty**)
   - ⚠️ Not populated by the pgvector pipeline — chunk text and embeddings are stored in `document_embeddings`
   - Fields: `chunk_text`, `keywords`, `embedding_ref` (would reference `document_embeddings.id`), `page_ref`
   - **Current row count**: 0 (all RAG data is in `document_embeddings`)

3. **`indicator_catalog`** - KPI definitions
   - Pre-seeded with accident indicators (ACC-001 to ACC-006)
   - Fields: `indicator_code`, `indicator_name`, `definition`, `unit_name`, `preferred_chart`
   - **Used by**: Analyst agent to select relevant KPIs

### Layer 2b: Vector Embeddings (`011_pgvector.sql`) 🆕

**Purpose**: Native vector search inside PostgreSQL (replaces ChromaDB)

#### Tables:
1. **`document_embeddings`** - Chunk text + 3072-dim vector embeddings
   - Fields: `id` (MD5 hash of `source::chunk_index`), `collection`, `document`, `embedding` (vector(3072)), `source`, `title`, `topic`, `chunk_index`, `total_chunks`, `page_ref`, `section_label`, `total_pages`, `created_at`
   - **Embedding Model**: Google Gemini `gemini-embedding-001` (3072-dim, API-based — no local model download)
   - **SDK**: `google-genai` v1.65.0 — `from google import genai`
   - **Vector Index**: None (pgvector HNSW/IVFFlat max 2000-dim; exact cosine search used via sequential scan — sufficient for <50K chunks)
   - **Search operator**: `<=>` cosine distance (`ORDER BY embedding <=> query_vec`)
   - **Upsert**: `ON CONFLICT (id) DO UPDATE` — safe to re-ingest
   - **View in DBeaver/pgAdmin**: Same connection as all other tables — no separate tool needed
   - **Current row count**: 6 chunks (4 documents from MinIO)

---

### Layer 3: Accident Domain (`003_accident_domain.sql`)

**Purpose**: Core accident data model

#### Dimension Tables:
1. **`dim_road_segment`**
   - Road characteristics: `road_name`, `road_type`, `lane_count`, `speed_limit`, `surface_type`
   - Enhanced in migration 005 with: `road_code`, `geography_id`, `km_marker`

#### Fact Tables:
1. **`fact_accident_event`** - Main accident events
   - **Primary Key**: `accident_id`
   - **Foreign Keys**: `geography_id`, `road_segment_id`, `source_id`
   - **Core Fields**:
     - `event_datetime` - When accident occurred
     - `weather_condition`, `road_condition`, `light_condition`
     - `accident_type`, `severity_level`, `vehicle_type`
     - `injured_count`, `death_count`
   - **Enhanced in migration 007**:
     - `serious_injured` - Count of seriously injured
     - `csv_year` - Source CSV year (2020-2026)
   - **Indexes**: `event_datetime`, `geography_id`, `severity_level`, `csv_year`

2. **`fact_accident_person`** - Person-level details
   - Links to `accident_id`
   - Fields: `age`, `sex`, `role_in_event`, `injury_level`, `helmet_used`, `seatbelt_used`

---

### Layer 4: Analytic Marts (Migrations 003, 006, 007)

**Purpose**: Pre-aggregated data for fast queries

#### Mart Tables:

1. **`mart_accident_summary`** - Monthly accident aggregates
   - **Grain**: One row per (year, month, geography)
   - **Columns**: `accident_count`, `injured_count`, `death_count`, `high_risk_timeband`, `dominant_road_cond`
   - **Enhanced in 007**: `province_name` denormalized for faster province queries
   - **Used by**: `build_accident_trend_chart`, `build_monthly_death_bar_chart`

2. **`mart_accident_hotspot`** - High-risk locations
   - **Grain**: One row per (geography, road_segment)
   - **Columns**: `accident_count`, `injured_count`, `death_count`, `hotspot_score`, `dominant_timeband`
   - **Sorted by**: `hotspot_score DESC`
   - **Used by**: `build_hotspot_bar_chart`, `get_accident_hotspots`

3. **`mart_province_year`** (Migration 006) - Province yearly summary
   - **Grain**: One row per (province, year)
   - **Columns**: `province_name`, `year_no`, `accident_count`, `injured_count`, `serious_injured`, `death_count`, `road_count`, `top_vehicle`, `top_cause`, `top_timeband`, `top_weather`
   - **Used by**: `build_province_year_trend_chart`, `get_province_year_summary`

4. **`mart_province_road`** (Migration 006) - Province road breakdown
   - **Grain**: One row per (province, road, year)
   - **Columns**: `province_name`, `road_name`, `road_code`, `year_no`, `accident_count`, `injured_count`, `serious_injured`, `death_count`, `hotspot_score`, `dominant_cause`, `dominant_vehicle`
   - **Used by**: `build_province_roads_bar_chart`, `get_province_roads`

---

### Layer 5: Materialized Views (Migration 007)

**Purpose**: Fast province-level queries without JOINs

1. **`v_province_year_summary`**
   - Denormalized view of `mart_province_year` + `dim_geography`
   - Includes: `latitude`, `longitude` for mapping

2. **`v_province_road_year`**
   - Denormalized view of `mart_province_road`
   - Direct access to province road statistics

---

## Data Flow Architecture

### 1. Data Ingestion (CSV → Database)

**Script**: `database/import_subdistrict_csv.py`

#### Process:
```
CSV Files (2021-2026)
    ↓
1. Parse & Clean Data
   - Handle Excel serial dates (datetime(1899, 12, 30) epoch)
   - Fix 2026 column shift issue
   - Normalize province names
    ↓
2. Upsert Dimensions
   - dim_geography (province, district, subdistrict)
   - dim_road_segment (road_name, road_code, geography_id)
    ↓
3. Bulk Insert Facts
   - fact_accident_event (with csv_year, serious_injured)
    ↓
4. Rebuild Marts
   - mart_accident_summary (monthly aggregates)
   - mart_accident_hotspot (risk scores)
   - mart_province_year (province yearly)
   - mart_province_road (province road yearly)
```

**Key Features**:
- **Batch processing**: 1000 rows per batch
- **Duplicate handling**: Upsert with ON CONFLICT
- **Data validation**: Skip invalid rows, log errors
- **Incremental**: Can re-run without duplicating data

---

### 2. Query Flow (API → Database)

#### A. **Agent Tools Query Flow**

```
User Query
    ↓
CrewAI Agent (chart_builder, retrieval, analyst)
    ↓
Agent Tool (e.g., build_province_year_trend_chart)
    ↓
query_db(sql, params)  [sync pool]
    ↓
PostgreSQL (mart tables)
    ↓
JSON Response (ChartSpec format)
    ↓
Frontend (ChartRenderer.tsx)
```

**Example Tool**: `build_province_year_trend_chart`
```python
@tool("build_province_year_trend_chart")
def build_province_year_trend_chart(province: str = "", top_n: int = 10) -> str:
    # Query mart_province_year
    sql = """
        SELECT year_no, accident_count, injured_count, death_count
        FROM mart_province_year
        WHERE province_name ILIKE %s
        ORDER BY year_no
    """
    rows = query_db(sql, (f"%{province}%",))
    
    # Transform to ChartSpec JSON
    return json.dumps({
        "type": "line",
        "title": f"แนวโน้มอุบัติเหตุจังหวัด{province} รายปี",
        "data": {
            "labels": [str(r["year_no"]) for r in rows],
            "datasets": [
                {"label": "อุบัติเหตุ", "data": [r["accident_count"] for r in rows]},
                {"label": "เสียชีวิต", "data": [r["death_count"] for r in rows]}
            ]
        },
        "source_note": "mart_province_year"
    })
```

#### B. **Test Endpoint Query Flow**

```
HTTP POST /api/test/chart/province_trend
    ↓
FastAPI Router (test_ui.py)
    ↓
Tool: build_province_year_trend_chart.run()
    ↓
query_db() [sync pool]
    ↓
PostgreSQL
    ↓
JSON Response {"tool": "...", "chart": {...}}
```

---

## Query Patterns & Performance

### 1. **Time-Series Queries** (Monthly trends)
```sql
-- Uses: mart_accident_summary
-- Index: idx_mart_acc_ym (year_no, month_no)
SELECT year_no, month_no, accident_count, injured_count, death_count
FROM mart_accident_summary
WHERE year_no >= 2023
ORDER BY year_no, month_no;
```
**Performance**: O(log n) index scan, ~10ms for 36 months

### 2. **Geographic Queries** (Province-level)
```sql
-- Uses: mart_province_year
-- Index: province_name (implicit from WHERE)
SELECT year_no, accident_count, death_count
FROM mart_province_year
WHERE province_name ILIKE '%เชียงใหม่%'
ORDER BY year_no;
```
**Performance**: Sequential scan on small mart, ~5ms

### 3. **Hotspot Queries** (Top-N dangerous locations)
```sql
-- Uses: mart_accident_hotspot
-- Index: idx_hotspot_score (hotspot_score DESC)
SELECT hotspot_id, hotspot_score, accident_count, death_count
FROM mart_accident_hotspot
ORDER BY hotspot_score DESC
LIMIT 10;
```
**Performance**: Index-only scan, ~2ms

### 4. **Aggregation Queries** (Hour-of-day distribution)
```sql
-- Uses: fact_accident_event
-- Index: idx_accident_datetime
SELECT EXTRACT(HOUR FROM event_datetime)::int AS hour_of_day,
       COUNT(*) AS accident_count
FROM fact_accident_event
GROUP BY hour_of_day
ORDER BY hour_of_day;
```
**Performance**: Full table scan with GROUP BY, ~50ms for 100K rows

---

## API Endpoints

### 1. **Chat Endpoint** (`POST /api/chat`)
- **Handler**: `src/routers/chat.py`
- **Flow**: User message → Orchestrator → CrewAI pipeline → AgentResponse
- **Database Access**: Via agent tools (sync pool)
- **Returns**: `{"content": "...", "charts": [...], "tables": [...], "citations": [...]}`

### 2. **Test Endpoints** (`POST /api/test/*`)
- **Handler**: `src/routers/test_ui.py`
- **Purpose**: Direct tool testing without full agent pipeline

#### Chart Tool Endpoints:
- `/api/test/chart/accident_trend` → `build_accident_trend_chart`
- `/api/test/chart/hotspot` → `build_hotspot_bar_chart`
- `/api/test/chart/province_trend` → `build_province_year_trend_chart`
- `/api/test/chart/province_roads` → `build_province_roads_bar_chart`
- `/api/test/chart/time_dist` → `build_time_distribution_chart`
- `/api/test/chart/road_condition` → `build_road_condition_pie_chart`
- `/api/test/chart/monthly_death` → `build_monthly_death_bar_chart`

#### Data Tool Endpoints:
- `/api/test/tool/accident_summary` → `get_accident_summary`
- `/api/test/tool/hotspots` → `get_accident_hotspots`
- `/api/test/tool/geography` → `get_geography_profile`

#### SQL Query Endpoint:
- `/api/test/query` - Execute read-only SQL (SELECT/WITH only)

### 3. **Health Check** (`GET /api/health`)
- **Checks**: PostgreSQL connection, MinIO, pgvector
- **Returns**: `{"status": "ok", "services": {"postgres": "ok", "minio": "ok", "pgvector": "ok"}}`

---

## Data Storage Strategy

### Fact Tables (Raw Data)
- **Storage**: Row-oriented (PostgreSQL default)
- **Retention**: All historical data (2020-2026+)
- **Updates**: Append-only (no updates to historical facts)
- **Partitioning**: None (future: partition by year for >1M rows)

### Mart Tables (Aggregated Data)
- **Storage**: Row-oriented with indexes
- **Refresh**: Rebuilt on CSV import
- **Strategy**: Materialized aggregates (not views)
- **Reason**: Fast query performance for agent tools

### Vector Embeddings (`document_embeddings`)
- **Storage**: PostgreSQL `vector(768)` column (pgvector)
- **Index**: HNSW for approximate nearest-neighbor (ANN) search — fast at scale
- **Similarity**: Cosine distance via `<=>` operator
- **Upsert**: `ON CONFLICT DO UPDATE` — idempotent re-ingestion
- **Advantage**: Single platform — view in DBeaver/pgAdmin alongside all other tables

### Indexes Strategy
- **Time-based**: `(year_no, month_no)` for time-series
- **Geographic**: `province_name`, `geography_id` for location queries
- **Scoring**: `hotspot_score DESC` for top-N queries
- **Vector**: HNSW cosine on `document_embeddings.embedding`
- **Foreign Keys**: All FK columns indexed automatically

---

## Configuration

### Database Settings (`src/config.py`)
```python
DB_HOST: str = "localhost"
DB_PORT: int = 5432
DB_NAME: str = "chat-aio"
DB_USER: str = "postgres"
DB_PASSWORD: str = "1234"

# pgvector / RAG
PGVECTOR_COLLECTION: str = "musya_documents"
EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### Connection String
```
postgresql://postgres:1234@localhost:5432/chat-aio
```

### Docker Image (PostgreSQL + pgvector)
```yaml
image: pgvector/pgvector:pg16   # Official pgvector image
```
> ⚠️ Plain `postgres:16` does NOT include pgvector — must use `pgvector/pgvector:pg16`

---

## Migration History

| Migration | Purpose | Key Changes |
|-----------|---------|-------------|
| 001 | Shared core | `dim_geography`, `dim_time`, `dim_source` |
| 002 | Document RAG | `document_registry`, `indicator_catalog` |
| 003 | Accident domain | `fact_accident_event`, `mart_accident_summary`, `mart_accident_hotspot` |
| 004 | Seed data | Mock accident data for testing |
| 005 | Road enhancement | Add `road_code`, `geography_id`, `km_marker` to `dim_road_segment` |
| 006 | Province marts | Add `mart_province_year`, `mart_province_road` |
| 007 | All years support | Add `serious_injured`, `csv_year`, province views |
| 008 | Duplicate prevention | UNIQUE constraints on fact tables |
| 009 | Coordinates | Add `latitude`, `longitude` to `fact_accident_event` |
| 010 | Evidence & Citations | `evidence_registry`, `claim_evidence_link` |
| **011** | **pgvector** | `CREATE EXTENSION vector` + `document_embeddings` table (`vector(3072)`) |
| **012** | **Document upload enhanced** | ALTER `document_registry` — add `upload_*`, `apa_*`, `ingest_*` columns for document management |
| **013** | **APA approval workflow** | ADD `apa_approval_status` to `document_registry` (`pending`/`approved`/`rejected`) |
| **014** | **Document chunks cleanup** | DROP legacy `document_chunks` table; consolidate into `document_embeddings` |
| **015** | **ThaiJO evidence** | ADD `thaijo_*` columns to `evidence_registry` (article_id, journal, authors, abstract, url) |


> **⚠️ evidence_type CHECK constraint:** Migration 010 restricts `evidence_type` to `('document', 'database', 'api')`.
> The code (added in Phase 3) also uses `'thaijo_article'` and `'notebooklm_pdf'`.
> If you encounter a constraint violation, run:
> ```sql
> ALTER TABLE evidence_registry DROP CONSTRAINT IF EXISTS evidence_registry_evidence_type_check;
> ALTER TABLE evidence_registry ADD CONSTRAINT evidence_registry_evidence_type_check
>   CHECK (evidence_type IN ('document', 'database', 'api', 'thaijo_article', 'notebooklm_pdf'));
> ```

---

## Best Practices

### For Agent Tool Developers:
1. **Always use `query_db()`** - Don't create new connections
2. **Query marts first** - Faster than fact tables
3. **Use parameterized queries** - Prevent SQL injection
4. **Return JSON strings** - Match ChartSpec/TableSpec format
5. **Handle empty results** - Return error JSON, not exceptions

### For Database Administrators:
1. **Run migrations in order** - 001 → 002 → 003 → ... → 015
2. **Use correct Docker image** - `pgvector/pgvector:pg16` (not plain `postgres:16`)
3. **Rebuild marts after CSV import** - Use `import_subdistrict_csv.py`
4. **Monitor connection pools** - Check pool exhaustion in logs
5. **Vacuum regularly** - `VACUUM ANALYZE` on fact tables monthly
6. **Backup before migrations** - `pg_dump chat-aio > backup.sql`

### For Performance Optimization:
1. **Use EXPLAIN ANALYZE** - Profile slow queries
2. **Add indexes selectively** - Based on actual query patterns
3. **Consider partitioning** - When fact tables exceed 1M rows
4. **Cache mart queries** - Redis for frequently accessed aggregates
5. **Batch inserts** - Use COPY or multi-row INSERT for bulk data

---

## Troubleshooting

### Common Issues:

**1. Connection Pool Exhausted**
```
Error: "connection pool exhausted"
Solution: Increase max_size in get_async_pool() or maxconn in get_sync_pool()
```

**2. Slow Province Queries**
```
Issue: Province queries taking >100ms
Solution: Ensure mart_province_year is rebuilt, check index on province_name
```

**3. Chart Data Empty**
```
Issue: Charts render but show no data
Solution: Check tool returns valid JSON, verify mart tables have data, run verify_province_data.py
```

**4. CSV Import Fails**
```
Issue: import_subdistrict_csv.py crashes
Solution: Check CSV encoding (UTF-8), verify column count matches expected schema, check for NULL geography_id
```

---

## Future Enhancements

1. **Read Replicas** - Separate read/write pools for scalability
2. **Partitioning** - Partition `fact_accident_event` by year
3. **Materialized Views** - Auto-refresh marts on schedule
4. **Query Caching** - Redis cache for common aggregations
5. **Time-Series DB** - Consider TimescaleDB extension for time-series data
6. **Full-Text Search** - Add `tsvector` columns for text search in documents
7. **pgvector IVFFlat** - Switch from HNSW to IVFFlat for very large embedding sets (>1M rows)

---

## Related Documentation

- **API Routes**: See `src/routers/chat.py`, `src/routers/test_ui.py`
- **Agent Tools**: See `src/tools/chart_builder.py`, `src/tools/accident.py`
- **Database Migrations**: See `database/001_*.sql` through `database/015_thaijo_evidence.sql`
- **Vector Store**: See `src/rag/vector_store.py` (pgvector implementation)
- **RAG Pipeline**: See `src/rag/document_rag.py` (MinIO → pgvector ingestion)
- **Data Import**: See `database/import_subdistrict_csv.py`
- **Schema Analysis**: See `database/analyze_schema.py`, `database/verify_province_data.py`
- **Full DB Reference**: See `doc/DATABASE_API_REFERENCE.md`
