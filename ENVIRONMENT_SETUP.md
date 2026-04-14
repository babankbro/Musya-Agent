# Musya Agent - Environment Setup Guide

Complete guide to set up Python environment and connect to Docker database.

## 📋 Prerequisites

- **Anaconda or Miniconda** installed
- **Docker Desktop** installed and running
- **Git** (optional, for cloning)
- **PowerShell** (Windows) or **Bash** (Linux/Mac)

**Install Miniconda:**
- Download from: https://docs.conda.io/en/latest/miniconda.html
- Or use Anaconda: https://www.anaconda.com/download

## 🚀 Quick Start (5 Steps)

### Step 1: Clone/Navigate to Project

```powershell
cd d:\work\musya\Agent
```

### Step 2: Set Up Conda Environment

```powershell
# Run automated setup script
.\scripts\setup_python_env.ps1
```

**What this does:**
- ✅ Checks Conda installation
- ✅ Creates Conda environment `musya-agent` with Python 3.12
- ✅ Installs all dependencies from `environment.yml`
- ✅ Initializes Conda for PowerShell
- ✅ Verifies key packages (FastAPI, CrewAI, psycopg2, ChromaDB, MinIO)

### Step 3: Start Docker Database

```powershell
# Start PostgreSQL and MinIO containers
docker-compose up -d postgres minio
```

**Verify containers are running:**
```powershell
docker ps
```

**Expected output:**
```
CONTAINER ID   IMAGE            STATUS                    PORTS
abc123...      postgres:16      Up 10 seconds (healthy)   0.0.0.0:5432->5432/tcp
def456...      minio/minio      Up 10 seconds (healthy)   0.0.0.0:9000-9001->9000-9001/tcp
```

### Step 4: Check Database Connection

```powershell
# Activate Conda environment
conda activate musya-agent

# Check database connection
python scripts\check_database.py
```

**Expected output:**
```
✅ Connected to PostgreSQL
✅ Database 'chat-aio' exists
⚠️  Some tables missing (need migrations)
```

### Step 5: Run Database Migrations

```powershell
# Run all migrations
python scripts\run_migrations.py
```

**Expected output:**
```
✅ Migration 001 completed (shared_core)
✅ Migration 002 completed (document_rag)
✅ Migration 003 completed (accident_domain)
✅ Migration 010 completed (evidence_citation)
🎉 All migrations completed successfully!
```

---

## 📝 Detailed Setup Instructions

### 1. Conda Environment Setup

#### Option A: Automated Setup (Recommended)

```powershell
.\scripts\setup_python_env.ps1
```

#### Option B: Manual Setup

```powershell
# Create Conda environment from environment.yml
conda env create -f environment.yml

# Activate environment
conda activate musya-agent

# Verify installation
conda list
pip list
```

#### Update Existing Environment

```powershell
# Update environment with new dependencies
conda env update -f environment.yml --prune

# Or recreate from scratch
conda env remove -n musya-agent
conda env create -f environment.yml
```

**Key packages installed via Conda:**
- Python 3.12
- pip (for Python packages)

**Key packages installed via pip:**
- `fastapi>=0.135.3` - Web framework
- `crewai>=1.13.0` - Multi-agent orchestration
- `psycopg2-binary` - PostgreSQL adapter
- `asyncpg` - Async PostgreSQL
- `chromadb>=1.1.1` - Vector database
- `minio` - Object storage client
- `litellm` - LLM interface

### 2. Environment Configuration

Create `.env` file in the Agent directory:

```env
# Database (Docker PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chat-aio
DB_USER=postgres
DB_PASSWORD=1234

# MinIO (Docker)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=musya-documents
MINIO_USE_SSL=false

# ChromaDB (Local)
CHROMA_PERSIST_DIR=.chromadb
CHROMA_COLLECTION=musya_documents

# LLM API Keys
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000
```

**Important:** Replace `your_gemini_api_key_here` with your actual Gemini API key.

### 3. Docker Database Setup

#### Start Services

```powershell
# Start PostgreSQL and MinIO
docker-compose up -d postgres minio

# Check status
docker-compose ps

# View logs
docker-compose logs -f postgres
```

#### Verify PostgreSQL

```powershell
# Connect to PostgreSQL
docker exec -it chatv1_postgres psql -U postgres -d chat-aio

# Inside psql:
\l              # List databases
\dt             # List tables (after migrations)
\q              # Quit
```

#### Verify MinIO

Open browser: **http://localhost:9001**

- Username: `minioadmin`
- Password: `minioadmin`

Create bucket `musya-documents` if it doesn't exist.

### 4. Database Verification

Run the comprehensive database check:

```powershell
python scripts\check_database.py
```

**This script checks:**
1. ✅ Environment variables (.env file)
2. ✅ Database connection
3. ✅ Database exists
4. ✅ Migration history
5. ✅ Required tables

**Expected output:**
```
🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍
Musya Agent - Database Connection Check
🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍

============================================================
Step 1: Testing Database Connection
============================================================
Database Host: localhost
Database Port: 5432
Database Name: chat-aio
Database User: postgres
✅ Connected to PostgreSQL
   Version: PostgreSQL 16.x

============================================================
Step 2: Verifying Database Exists
============================================================
✅ Database 'chat-aio' exists

============================================================
Step 3: Checking Required Tables
============================================================
✅ dim_geography                (150 rows)
✅ dim_time                     (3,650 rows)
✅ document_registry            (0 rows)
✅ document_chunks              (0 rows)
✅ accident_fact                (0 rows)
✅ evidence_registry            (0 rows)
✅ claim_evidence_link          (0 rows)

Summary: 7/7 tables exist

============================================================
SUMMARY
============================================================
✅ PASS - env
✅ PASS - connection
✅ PASS - database
✅ PASS - migrations
✅ PASS - tables

🎉 Database is ready!
```

### 5. Run Migrations

If tables are missing, run migrations:

```powershell
python scripts\run_migrations.py
```

**Available migrations:**
- `001_shared_core.sql` - Core dimension tables
- `002_document_rag.sql` - Document RAG tables
- `003_accident_domain.sql` - Accident domain tables
- `010_evidence_citation.sql` - Citation & Evidence tables

**Migration process:**
1. Creates `migration_history` table
2. Checks which migrations are already applied
3. Runs pending migrations in order
4. Records each migration in history

---

## 🧪 Testing the Setup

### Test 1: Health Check

```powershell
# Start the server
python -m uvicorn src.main:app --reload

# In another terminal, check health
curl http://localhost:8000/api/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "postgresql": true,
  "minio": true,
  "chromadb": true,
  "timestamp": "2025-01-27T10:30:00"
}
```

### Test 2: Database Connection Test

```powershell
python scripts\check_database.py
```

All checks should pass ✅

### Test 3: Citation Setup Test

```powershell
python scripts\test_citation_setup.py
```

**Expected:** 7/7 tests pass

### Test 4: Upload Sample Documents

```powershell
python scripts\prepare_sample_documents.py
```

**Expected:** 4 documents uploaded to MinIO

### Test 5: Full Pipeline Test

```powershell
# Start server
python -m uvicorn src.main:app --reload

# Open test UI
# Browser: http://localhost:8000/static/citation_test_ui.html

# Test chat with: สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025
```

---

## 🔧 Troubleshooting

### Issue: Python not found

```powershell
# Check Python installation
python --version

# If not found, download from python.org
# Install Python 3.12+
```

### Issue: Conda not found

```powershell
# Install Miniconda
# Download from: https://docs.conda.io/en/latest/miniconda.html

# After installation, restart PowerShell
# Verify installation
conda --version

# Initialize conda for PowerShell
conda init powershell
```

### Issue: Conda environment activation fails

```powershell
# Initialize conda for PowerShell
conda init powershell

# Restart PowerShell
# Then activate
conda activate musya-agent
```

### Issue: Docker containers won't start

```powershell
# Check Docker Desktop is running
docker --version

# Check if ports are in use
netstat -ano | findstr :5432
netstat -ano | findstr :9000

# Stop conflicting services or change ports in docker-compose.yml
```

### Issue: Database connection refused

**Check:**
1. Docker container is running: `docker ps`
2. PostgreSQL is healthy: `docker-compose ps`
3. Correct host/port in `.env`: `DB_HOST=localhost`, `DB_PORT=5432`

**Fix:**
```powershell
# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Issue: Database does not exist

```powershell
# Connect to PostgreSQL
docker exec -it chatv1_postgres psql -U postgres

# Create database
CREATE DATABASE chat-aio;

# Or use the database name from docker-compose.yml
```

### Issue: Tables missing

```powershell
# Run migrations
python scripts\run_migrations.py

# Verify
python scripts\check_database.py
```

### Issue: MinIO connection fails

**Check:**
1. MinIO container running: `docker ps | findstr minio`
2. Access MinIO console: http://localhost:9001
3. Bucket exists: `musya-documents`

**Fix:**
```powershell
# Restart MinIO
docker-compose restart minio

# Create bucket via console or API
```

### Issue: Package installation fails

```powershell
# Update conda environment
conda env update -f environment.yml --prune

# Or install specific package
conda activate musya-agent
pip install package-name

# For psycopg2 issues on Windows, use binary version (already in environment.yml)
pip install psycopg2-binary

# Check what's installed
conda list
```

---

## 📊 Verification Checklist

Before running the Agent, verify:

- [ ] Conda (Anaconda or Miniconda) installed
- [ ] Conda environment `musya-agent` created
- [ ] Environment activated (`conda activate musya-agent`)
- [ ] All dependencies installed (`conda list` shows key packages)
- [ ] `.env` file exists with correct values
- [ ] Docker Desktop running
- [ ] PostgreSQL container healthy (`docker ps`)
- [ ] MinIO container healthy (`docker ps`)
- [ ] Database connection successful (`check_database.py`)
- [ ] All tables exist (migrations run)
- [ ] MinIO bucket created (`musya-documents`)
- [ ] Gemini API key configured

---

## 🎯 Next Steps

After successful setup:

1. **Upload Sample Documents**
   ```powershell
   python scripts\prepare_sample_documents.py
   ```

2. **Run Citation Setup Test**
   ```powershell
   python scripts\test_citation_setup.py
   ```

3. **Start the Server**
   ```powershell
   python -m uvicorn src.main:app --reload
   ```

4. **Open Test UI**
   ```
   http://localhost:8000/static/citation_test_ui.html
   ```

5. **Test the Pipeline**
   - Send a chat message in Thai
   - Verify citations are generated
   - Check evidence items
   - Test document opening

---

## 📚 Additional Resources

- **Quick Start Guide:** `QUICKSTART_CITATION_TESTING.md`
- **Testing Guide:** `doc/CITATION_TESTING_GUIDE.md`
- **Architecture:** `doc/CITATION_EVIDENCE_AGENT.md`
- **Database Schema:** `doc/DATABASE_API_REFERENCE.md`

---

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Run database check: `python scripts\check_database.py`
3. Verify `.env` file has correct values
4. Check Docker containers: `docker ps`
5. Review error messages carefully

---

**Last Updated:** 2025-01-27  
**Version:** 1.0  
**Estimated Setup Time:** 10-15 minutes
