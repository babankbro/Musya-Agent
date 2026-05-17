# Citation & Evidence Agent Testing Guide

## Overview

This guide provides step-by-step instructions for testing the newly implemented Citation & Evidence Agent, including database setup, sample document preparation, and full pipeline testing.

## Prerequisites

- Python 3.12+ virtual environment activated
- PostgreSQL database running
- MinIO server running
- pgvector extension active in PostgreSQL (enabled via `011_pgvector.sql`)
- All dependencies installed (`pip install -r requirements.txt`)

## Testing Steps

### Step 1: Run Database Migration and Verification

The Citation & Evidence Agent requires migration 010 which creates two new tables:
- `evidence_registry`: Stores normalized evidence items
- `claim_evidence_link`: Links claims to supporting evidence

**Run the test script:**

```powershell
# From Agent directory
python scripts/test_citation_setup.py
```

**What this script does:**
1. ✅ Runs migration 010 (creates evidence tables)
2. ✅ Verifies tables exist and are accessible
3. ✅ Tests evidence insertion and retrieval
4. ✅ Tests claim-evidence linking
5. ✅ Verifies MinIO connection
6. ✅ Verifies pgvector connection (`document_embeddings` table)
7. ✅ Checks enhanced metadata columns

**Expected output:**
```
🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍
Citation & Evidence Agent Setup Verification
🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍

============================================================
STEP 1: Running Migration 010
============================================================
✅ Migration 010 executed successfully

============================================================
STEP 2: Verifying Database Tables
============================================================
✅ Table 'evidence_registry' exists (1 rows)
✅ Table 'claim_evidence_link' exists (1 rows)

... (more steps)

============================================================
SUMMARY
============================================================
✅ PASS - migration
✅ PASS - tables
✅ PASS - evidence_insert
✅ PASS - claim_link
✅ PASS - minio
✅ PASS - pgvector
✅ PASS - metadata

🎉 All tests passed! Citation & Evidence Agent is ready.
```

### Step 2: Prepare Sample Documents in MinIO

For comprehensive testing, you need sample documents in MinIO with proper metadata.

**Option A: Use existing documents**

If you already have documents in MinIO, re-ingest them with enhanced metadata:

```powershell
# Start the server first
python -m uvicorn src.main:app --reload

# In another terminal, trigger ingestion
curl -X POST http://localhost:8000/api/ingest
```

**Option B: Upload new sample documents**

1. **Create sample documents** (PDF or DOCX) with:
   - Clear section headings
   - Page numbers
   - Relevant content (accident statistics, policies, etc.)

2. **Upload to MinIO:**

```python
# Quick upload script
from src.db.minio_client import get_minio_client
from src.config import get_settings

settings = get_settings()
client = get_minio_client()

# Upload a file
with open("sample_document.pdf", "rb") as f:
    client.put_object(
        settings.minio_bucket,
        "accident/sample_document.pdf",
        f,
        length=-1,
        part_size=10*1024*1024
    )
```

3. **Ingest into RAG:**

```bash
curl -X POST http://localhost:8000/api/ingest
```

**Recommended sample documents:**
- `accident/road_safety_policy_2025.pdf` - Road safety policy document
- `accident/accident_statistics_2024.pdf` - Statistical report
- `mental_health/mental_health_guidelines.pdf` - Mental health guidelines
- `nutrition/nutrition_standards.pdf` - Nutrition standards

### Step 3: Start the Agent Server

```powershell
# From Agent directory
python -m uvicorn src.main:app --reload --port 8000
```

**Verify server is running:**
```bash
curl http://localhost:8000/api/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "postgresql": true,
  "minio": true,
  "pgvector": true,
  "timestamp": "2025-01-27T10:30:00"
}
```

### Step 4: Open the Test UI

Open your browser and navigate to:

```
http://localhost:8000/static/citation_test_ui.html
```

The test UI has 4 tabs:

#### Tab 1: 💬 Chat Test
Test the full 7-agent pipeline with citation generation.

**Sample test messages:**
```
สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025
แนวโน้มอุบัติเหตุทางถนนในภาคเหนือ
นโยบายความปลอดภัยทางถนนล่าสุด
เปรียบเทียบอัตราการเสียชีวิตจากอุบัติเหตุระหว่างปี 2023-2025
```

**What to verify:**
- ✅ Response includes citations (e.g., C-001, C-002)
- ✅ Citations have proper source references
- ✅ Evidence count > 0
- ✅ Coverage score > 0
- ✅ Charts include source notes
- ✅ Response time reasonable (<30s)

#### Tab 2: 📚 Evidence API
Test individual evidence and citation endpoints.

**Tests:**
1. **Get Evidence by ID:**
   - Input: `EV-001` (or any evidence ID from chat response)
   - Verify: Returns evidence item with metadata

2. **Get Session Evidence:**
   - Input: Session ID from chat response
   - Verify: Returns all evidence for that session

3. **Get Coverage Report:**
   - Input: Same session ID
   - Verify: Returns coverage statistics

4. **Open Document:**
   - Input: Document ID (e.g., `1`)
   - Optional: Page number (e.g., `12`)
   - Verify: Opens document in new tab

#### Tab 3: 📄 Documents
Test document ingestion and search.

**Tests:**
1. **Ingest Documents:**
   - Click "Start Ingestion"
   - Verify: Returns chunk count and success message

2. **Search Documents:**
   - Select topic (e.g., "accident")
   - Enter keywords (e.g., "อุบัติเหตุทางถนน")
   - Verify: Returns relevant results with metadata

#### Tab 4: 🏥 Health Check
Verify all system components are connected.

**Expected:**
- ✅ PostgreSQL: Connected
- ✅ MinIO: Connected
- ✅ pgvector: Connected

### Step 5: Test the Full Pipeline

**Test Case 1: Basic Citation Generation**

1. Go to Chat Test tab
2. Enter: `สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025`
3. Click "Send to Agent Pipeline"

**Expected output structure:**
```json
{
  "content": "...",
  "topic": "accident",
  "charts": [...],
  "citations": [
    {
      "citation_code": "C-001",
      "source_type": "document",
      "source_ref": "road_safety_2025.pdf",
      "citation_text": "นโยบายความปลอดภัยทางถนน 2025, หน้า 12, มาตรา 3.2",
      "evidence_id": "EV-001",
      "open_url": "/api/documents/open/1?page=12"
    }
  ],
  "metadata": {
    "pipeline": "phase1_accident_with_citation",
    "agent_count": 7,
    "total_evidence": 5,
    "coverage_score": 0.85,
    "elapsed_seconds": 12.3
  }
}
```

**Test Case 2: Multi-Source Evidence**

1. Enter: `เปรียบเทียบอัตราการเสียชีวิตจากอุบัติเหตุระหว่างปี 2023-2025`
2. Verify:
   - Multiple citations (C-001, C-002, C-003, etc.)
   - Mix of document and database sources
   - Charts have source notes
   - Coverage score > 0.7

**Test Case 3: Evidence API Integration**

1. From the chat response, copy a citation's `evidence_id`
2. Go to Evidence API tab
3. Enter the evidence ID
4. Click "Get Evidence"
5. Verify:
   - Returns full evidence details
   - Has `open_url` for document access
   - Trust level is set (high/medium/low)
   - Metadata includes page_ref and section_label

**Test Case 4: Document Opening**

1. From evidence details, note the document ID
2. Click on the `open_url` link
3. Verify:
   - Document opens in new tab
   - If page specified, opens to that page (PDF viewers)

### Step 6: Run Automated Tests

Run the comprehensive test suite:

```powershell
# From Agent directory
.\.venv\Scripts\python.exe -m pytest tests/test_citation_evidence.py -v
```

**Expected: 44 tests should pass**

Test coverage includes:
- ✅ Evidence schema validation (6 tests)
- ✅ Citation parsing (4 tests)
- ✅ Enhanced document ingestion (8 tests)
- ✅ search_documents tool (6 tests)
- ✅ Citation & Evidence Agent (8 tests)
- ✅ Orchestrator integration (6 tests)
- ✅ API endpoints (6 tests)

## Troubleshooting

### Issue: Migration fails with "relation already exists"

**Solution:** Tables already exist. This is OK. The script handles this gracefully.

### Issue: MinIO connection fails

**Check:**
```powershell
# Verify MinIO is running
curl http://localhost:9000/minio/health/live

# Check credentials in .env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=musya-documents
```

### Issue: pgvector connection fails

**Check:**
```powershell
# Verify pgvector extension is enabled in PostgreSQL
psql -U postgres -d chat-aio -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Re-run pgvector migration if needed
psql -U postgres -d chat-aio -f database/011_pgvector.sql

# Check PGVECTOR_COLLECTION in .env
PGVECTOR_COLLECTION=musya_documents
EMBEDDING_MODEL=models/gemini-embedding-001
```

### Issue: No documents found in search

**Solution:**
1. Verify documents are in MinIO: `curl http://localhost:9000/minio/musya-documents/`
2. Re-run ingestion: `curl -X POST http://localhost:8000/api/ingest`
3. Check pgvector row count: `psql -U postgres -d chat-aio -c "SELECT COUNT(*) FROM document_embeddings;"`

### Issue: Citations not appearing in response

**Check:**
1. Verify Citation & Evidence Agent is in pipeline (check logs)
2. Check that `_parse_crew_result` extracts citations
3. Verify evidence_registry has data: `SELECT COUNT(*) FROM evidence_registry;`

### Issue: Test UI shows CORS errors

**Solution:**
Add to `.env`:
```
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

## Performance Benchmarks

Expected performance metrics:

| Metric | Target | Acceptable |
|--------|--------|------------|
| Pipeline execution | <15s | <30s |
| Evidence extraction | <2s | <5s |
| Citation generation | <1s | <3s |
| Document search | <500ms | <2s |
| Coverage calculation | <500ms | <1s |

## Next Steps

After successful testing:

1. **Production Deployment:**
   - Review `doc/CITATION_EVIDENCE_AGENT.md` for architecture details
   - Configure production database
   - Set up MinIO with proper access controls
   - Configure LLM API keys

2. **Frontend Integration:**
   - Use the test UI as reference for frontend implementation
   - Implement citation display components
   - Add document viewer with page navigation
   - Show evidence trust indicators

3. **Monitoring:**
   - Track citation accuracy
   - Monitor coverage scores
   - Log evidence retrieval performance
   - Alert on low trust scores

4. **Expansion:**
   - Add more document sources
   - Implement citation styles (APA, MLA, etc.)
   - Add evidence conflict detection
   - Implement source credibility scoring

## API Reference

### Evidence Endpoints

```
GET  /api/evidence/{evidence_id}
GET  /api/evidence/session/{session_id}
GET  /api/evidence/session/{session_id}/coverage
GET  /api/documents/open/{document_id}?page={page_number}
```

### Chat Endpoint (with Citations)

```
POST /api/chat
Body: { "message": "your question" }
Response: {
  "content": "...",
  "citations": [...],
  "metadata": {
    "total_evidence": 5,
    "coverage_score": 0.85
  }
}
```

## Support

For issues or questions:
1. Check logs: `tail -f logs/agent.log`
2. Review test output: `pytest tests/test_citation_evidence.py -v`
3. Consult architecture docs: `doc/CITATION_EVIDENCE_AGENT.md`
4. Check database: `psql -d musya_agent -c "SELECT * FROM evidence_registry LIMIT 5;"`

---

**Last Updated:** 2025-01-27  
**Version:** 1.0  
**Status:** Ready for Testing
