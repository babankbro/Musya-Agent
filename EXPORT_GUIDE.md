# Project Export & Setup Guide

This guide covers everything needed to move the project to a new machine, restore the database, and run tests.

---

## 1. What to Export

### Files to copy

```
Agent/
├── src/                        # all source code
├── tests/                      # all test files
├── static/                     # HTML UI pages
├── database/                   # SQL migrations + CSV data
│   ├── 001_shared_core.sql … 021_evidence_registry_apa_thaijo.sql
│   └── accident*.csv           # raw accident CSV files
├── tasks/                      # plan + todo
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example                # copy and fill in as .env
└── EXPORT_GUIDE.md             # this file
```

### Files to NOT copy

```
.venv/              ← rebuild on target machine
chroma_data/        ← rebuild by re-ingesting docs (optional)
__pycache__/        ← auto-generated
musya_agent.egg-info/
```

### Quick archive (PowerShell)

```powershell
# Run from one level above Agent/
tar -czf musya_agent_export.tar.gz `
  --exclude="Agent/.venv" `
  --exclude="Agent/chroma_data" `
  --exclude="Agent/__pycache__" `
  --exclude="Agent/**/__pycache__" `
  Agent/
```

---

## 2. Database Dump (while Docker is running)

The PostgreSQL container is `chatv1_postgres` using the `pgvector/pgvector:pg16` image.
Data lives in the named volume `chatv1_pgdata`.

### Full schema + data dump

```powershell
# Dump everything to a single file
docker exec chatv1_postgres pg_dump `
  -U postgres `
  -d "chat-aio" `
  --no-owner `
  --no-acl `
  -F c `
  -f /tmp/musya_full.dump

# Copy the dump out of the container
docker cp chatv1_postgres:/tmp/musya_full.dump ./musya_full.dump
```

The `-F c` flag uses PostgreSQL's custom binary format — smaller and faster to restore than plain SQL.

### Dump only accident/policy tables (smaller file)

```powershell
docker exec chatv1_postgres pg_dump `
  -U postgres `
  -d "chat-aio" `
  --no-owner `
  --no-acl `
  -F c `
  -t fact_accident_event `
  -t fact_accident_person `
  -t dim_geography `
  -t mart_province_road `
  -t mart_province_year `
  -t mart_accident_summary `
  -f /tmp/musya_accident.dump

docker cp chatv1_postgres:/tmp/musya_accident.dump ./musya_accident.dump
```

### Dump schema only (no data — for fresh migrations)

```powershell
docker exec chatv1_postgres pg_dump `
  -U postgres `
  -d "chat-aio" `
  --no-owner --no-acl `
  -s `
  > ./musya_schema_only.sql
```

---

## 3. Setup on a New Machine

### Prerequisites

- Docker Desktop installed and running
- Python 3.11–3.13
- Git (optional)

### Step 1 — Copy `.env`

```powershell
Copy-Item .env.example .env
# Then edit .env and set GEMINI_API_KEY to your actual key
```

Minimum required keys in `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chat-aio
DB_USER=postgres
DB_PASSWORD=1234
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash
GEMINI_MODEL_PRO=gemini-2.5-pro
MINIO_ENDPOINT=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=uploads
MINIO_USE_SSL=false
```

### Step 2 — Create Docker volumes (first time only)

The `docker-compose.yml` references external named volumes. Create them once:

```powershell
docker volume create chatv1_pgdata
docker volume create chatv1_minio_data
```

### Step 3 — Start infrastructure

```powershell
# Start PostgreSQL + MinIO only (no agent container yet)
docker compose up -d postgres minio

# Wait until PostgreSQL is healthy
docker compose ps
```

Expected: both services show `healthy`.

### Step 4 — Restore the database dump

#### Option A — Restore full dump (recommended)

```powershell
# Copy the dump into the container
docker cp musya_full.dump chatv1_postgres:/tmp/musya_full.dump

# Restore
docker exec chatv1_postgres pg_restore `
  -U postgres `
  -d "chat-aio" `
  --no-owner `
  --no-acl `
  -F c `
  /tmp/musya_full.dump
```

#### Option B — Run migrations from scratch (no dump)

```powershell
# Apply migrations in order
Get-ChildItem database/*.sql | Sort-Object Name | ForEach-Object {
    Write-Host "Applying $($_.Name)..."
    Get-Content $_.FullName | docker exec -i chatv1_postgres psql -U postgres -d "chat-aio"
}

# Then import CSV data
docker exec -i chatv1_postgres psql -U postgres -d "chat-aio" -c "\copy fact_accident_event FROM STDIN CSV HEADER" < database/accident_all_with_subdistrict.csv
```

### Step 5 — Set up Python environment

```powershell
# Create virtualenv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies (editable install)
pip install -e .
```

### Step 6 — Verify DB connection

```powershell
python -c "from src.db.pool import query_db; print(query_db('SELECT count(*) FROM fact_accident_event')[0])"
```

Expected: a row count like `(54321,)`.

---

## 4. Run Tests

All tests require a live PostgreSQL connection. Start Docker first (Step 3 above).

### Zone 10 SQL tools (28 tests, ~4s, no LLM)

```powershell
pytest tests/test_zone10_tools.py -v
```

### API integration tests (14 tests, no slow LLM)

```powershell
pytest tests/test_accident_policy_api.py -v -m "not slow"
```

### Full non-slow suite (~384 tests)

```powershell
pytest tests/ -v -m "not slow"
```

### Known pre-existing failures (not from this feature)

These 6 tests fail due to unrelated issues — ignore them:

```
tests/test_citation_evidence.py::TestOrchestratorCitationIntegration
tests/test_policy_brief.py::TestEnrichCitationsFromDb
tests/test_thaijo_tool.py (3 tests)
tests/test_tools.py::TestAccidentTools::test_get_accident_time_distribution
```

To exclude them explicitly:

```powershell
pytest tests/ -v -m "not slow" `
  --ignore=tests/test_citation_evidence.py `
  --ignore=tests/test_thaijo_tool.py
```

### Full LLM pipeline smoke test (slow, costs API credits)

```powershell
pytest tests/test_accident_policy_api.py -v -m slow
```

---

## 5. Run the Agent Server

### Locally (recommended for development)

```powershell
uvicorn src.main:app --reload --port 8000
```

Open: `http://localhost:8000/accident-policy`

### In Docker (production-like)

```powershell
docker compose up --build agent
```

The `agent` service in `docker-compose.yml` connects to `postgres` via internal Docker network.

---

## 6. Verify the Accident Policy Feature

With the server running, confirm these three work:

```powershell
# 1. Data endpoint (fast, no LLM, ~2s)
Invoke-RestMethod "http://localhost:8000/api/accident-policy/zone10/data" | ConvertTo-Json -Depth 3

# 2. UI page loads
Invoke-WebRequest "http://localhost:8000/accident-policy" | Select-Object StatusCode, @{n="size";e={$_.Content.Length}}

# 3. Province filter
Invoke-RestMethod "http://localhost:8000/api/accident-policy/zone10/data?provinces=ยโสธร" | Select-Object provinces
```

---

## 7. Database Backup Schedule (ongoing)

To keep backups while the container is running, create a simple script:

```powershell
# backup_db.ps1
$stamp = Get-Date -Format "yyyyMMdd_HHmm"
docker exec chatv1_postgres pg_dump `
  -U postgres -d "chat-aio" --no-owner --no-acl -F c `
  -f "/tmp/musya_$stamp.dump"
docker cp "chatv1_postgres:/tmp/musya_$stamp.dump" ".\backups\musya_$stamp.dump"
Write-Host "Backup saved: backups\musya_$stamp.dump"
```

Run it:

```powershell
New-Item -ItemType Directory -Force backups
.\backup_db.ps1
```

To restore any backup later, use the same `pg_restore` command from Step 4.
