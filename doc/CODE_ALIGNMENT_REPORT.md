# Code ↔ Documentation Alignment Report

> Generated: 2026-04-16
> Source of truth: **Actual source code** in `src/`

---

## 1. Agent Pipeline — Chat (Actual: 9 agents + Router)

| # | Agent | Role | Tools (Actual) | LLM Tier | File |
|---|-------|------|----------------|----------|------|
| 0 | Request Router | Pipeline routing (runs before crew) | 0 | fast | `request_router.py` |
| 1 | Request Interpreter | Parse intent → structured params | 0 | fast | `request_interpreter.py` |
| 2 | Data Retrieval Specialist | Fetch from Doc RAG + DB RAG + ThaiJO | **11** | fast | `retrieval.py` |
| 3 | SQL Specialist | Custom SQL queries | **3** | fast | `sql_specialist.py` |
| 4 | Citation & Evidence | Normalize evidence, APA citations | **4** | fast | `citation_evidence.py` |
| 5 | Accident Analyst | Domain analysis, Haddon Matrix | 0 | pro | `analyst_accident.py` |
| 6 | Chart Builder | Chart.js spec generation | **7** | pro | `chart_builder.py` |
| 7 | Research Synthesizer | Narrative prose blocks (1200-2000 words) | 0 | pro | `research_synthesizer.py` |
| 8 | Deep Analyst | Root cause, policy gaps (1000-1500 words) | 0 | pro | `deep_analyst.py` |
| 9 | Report Composer | Final Thai report (2000-4000 words) | 0 | pro | `report_writer.py` |

### Documentation Errors Found

| Document | Says | Actual |
|----------|------|--------|
| `PROJECT_DOCUMENTATION.md` | "6 agents" | **9 agents + Router = 10** |
| `ARCHITECTURE.md` | "6 agents" | **9 agents + Router = 10** |
| `AGENT_WORKFLOW.md` | "7 agents" | **9 agents + Router = 10** |
| `AGENT_WORKFLOW.md` | Missing agents | Research Synthesizer, Deep Analyst not listed |

---

## 2. Agent Pipeline — Policy Brief (Actual: 9 agents)

| # | Agent | Role | Tools | LLM Tier | File |
|---|-------|------|-------|----------|------|
| 0 | Request Router | Pipeline routing | 0 | fast | `request_router.py` |
| 1 | Request Interpreter | Parse intent | 0 | fast | `request_interpreter.py` |
| 2 | Data Retrieval + NLM | Fetch data + NotebookLM | 11 + 2 NLM | fast | `retrieval.py` |
| 3 | SQL Specialist | Custom SQL | 3 | fast | `sql_specialist.py` |
| 4 | Citation & Evidence | APA citations | 4 | fast | `citation_evidence.py` |
| 5 | RTI Analyst | Road traffic injury analysis | 3 | pro | `policy_rti.py` |
| 6 | Mental Health Analyst | Suicide prevention analysis | 0 | pro | `policy_mental.py` |
| 7 | NCD Analyst | Nutrition/chronic disease | 0 | pro | `policy_ncd.py` |
| 8 | Policy Report Writer | Synthesize 3-domain brief | 0 | pro | `policy_report_writer.py` |

---

## 3. Tool Inventory — Actual vs Documented

### Agent 2: Retrieval — 11 tools (docs say 10)

| Tool Name (Actual) | Source File | Documented? |
|---------------------|-----------|-------------|
| `search_documents` | `tools/common.py` | Yes |
| `get_indicator_catalog` | `tools/common.py` | Yes |
| `get_geography_profile` | `tools/common.py` | Yes |
| `get_province_year_summary` | `tools/accident.py` | Yes |
| `get_province_roads` | `tools/accident.py` | Yes |
| `get_all_provinces_ranking` | `tools/accident.py` | Yes |
| `get_accident_summary` | `tools/accident.py` | Yes |
| `get_accident_hotspots` | `tools/accident.py` | Yes |
| `get_accident_time_distribution` | `tools/accident.py` | Yes |
| `get_road_condition_risk` | `tools/accident.py` | Yes |
| **`search_thaijo`** | **`tools/thaijo.py`** | **Missing from AGENT_WORKFLOW, PROJECT_DOCUMENTATION** |

### Agent 3: SQL Specialist — 3 tools (docs say 1 or 2)

| Tool Name (Actual) | Documented In | Wrong Name In |
|---------------------|--------------|---------------|
| `execute_custom_sql` | `SQL_SPECIALIST_AGENT.md` ✓, `PROJECT_DOCUMENTATION.md` ✓ | `AGENT_WORKFLOW.md` calls it `execute_sql` |
| `explain_schema` | `SQL_SPECIALIST_AGENT.md` ✓, `PROJECT_DOCUMENTATION.md` ✓ | `AGENT_WORKFLOW.md` doesn't list it |
| `get_table_row_count` | `SQL_SPECIALIST_AGENT.md` ✓ | Missing from `AGENT_WORKFLOW.md`, `PROJECT_DOCUMENTATION.md` |

### Agent 4: Citation & Evidence — 4 tools (docs say 2 or 3)

| Tool Name (Actual Code) | Documented As |
|--------------------------|---------------|
| `list_all_documents_apa` | **Not documented anywhere** |
| `lookup_document_apa` | Not in AGENT_WORKFLOW (listed as `get_evidence_summary`) |
| `register_evidence` | `CITATION_EVIDENCE_GUIDE.md` ✓ | AGENT_WORKFLOW calls it `store_evidence` |
| `register_claim_links` | `CITATION_EVIDENCE_GUIDE.md` ✓ | AGENT_WORKFLOW calls it `link_claim_evidence` |

### Agent 6: Chart Builder — 7 tools (correct in docs)

All 7 chart tools documented correctly.

### RTI Analyst (Policy) — 3 tools (not fully documented)

| Tool Name (Actual) | Source |
|--------------------|--------|
| `get_accident_hotspots` | `tools/accident.py` |
| `get_province_year_summary` | `tools/accident.py` |
| `get_accident_time_distribution` | `tools/accident.py` |

### NLM Data Fetcher — 2 tools (documented)

| Tool Name (Actual) | Source |
|--------------------|--------|
| `nlm_ask` | `tools/notebooklm.py` |
| `get_supported_provinces` | `tools/notebooklm.py` |

---

## 4. Citation Code Ranges — Actual vs Documented

### Actual (from `citation_evidence.py` prompt):

| Range | Source Type | Trust Level |
|-------|-----------|-------------|
| C-001 to C-099 | Reports (notebooklm_pdf / document) | High |
| C-100 to C-199 | Database / dataset | High (mart) / Medium (fact) |
| C-200 to C-299 | **ThaiJO academic articles** | Medium |
| C-300+ | External sources | Variable |

### Documentation Errors:

| Document | Says C-200~C-299 is | Should Be |
|----------|---------------------|-----------|
| `CITATION_APA_FORMAT.md` | "External websites/articles" | **ThaiJO academic articles** |
| `CITATION_EVIDENCE_GUIDE.md` | Not specified per range | Should include ThaiJO range |
| `THAIJO_AGENT_IMPLEMENTATION.md` | "ThaiJO articles" ✓ | Correct |

---

## 5. API Endpoints — Actual vs Documented

### Actual Routers Registered (main.py): 10 routers

| Router | Prefix | Endpoints | Documented? |
|--------|--------|-----------|-------------|
| `health` | `/api/health` | 1 | Yes |
| `chat` | `/api/chat` | 3 (chat, unified, stream) | Partially |
| `ingest` | `/api/ingest` | 1 | Yes |
| `evidence` | `/api/documents/open`, `/api/evidence` | 6 | Partially |
| `upload` | `/api/documents/upload` | 2 | No |
| `documents` | `/api/documents` | 12 | No |
| `citation` | `/api/citations` | 2 | No |
| `policy_brief` | `/api/policy-brief` | 2 | Partially |
| `test_ui` | `/api/test` | 15 | No |
| **`thaijo`** | **`/api/thaijo`** | **2** | **No (except in THAIJO_AGENT_IMPLEMENTATION.md)** |

### Missing from all docs:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/chat/unified` | POST | Auto-route to chat or policy pipeline |
| `POST /api/chat/stream` | POST | SSE streaming with progress |
| `POST /api/documents/upload` | POST | Direct file upload |
| `POST /api/documents/upload-url` | POST | Upload from URL |
| `GET /api/documents` | GET | Paginated document list |
| `GET /api/documents/registry` | GET | All document registry |
| `GET /api/documents/{id}` | GET | Document detail |
| `PATCH /api/documents/{id}` | PATCH | Update document metadata |
| `DELETE /api/documents/{id}` | DELETE | Delete document |
| `POST /api/documents/{id}/reingest` | POST | Reingest document |
| `GET /api/documents/minio/tree` | GET | MinIO folder tree |
| `GET /api/documents/minio/browse` | GET | Browse MinIO prefix |
| `GET /api/documents/minio/read` | GET | Read file text preview |
| `POST /api/documents/minio/apa-draft` | POST | AI-generated APA draft |
| `POST /api/documents/minio/approve` | POST | Approve & ingest document |
| `POST /api/documents/analyze-upload` | POST | Analyze uploaded file for APA |
| `GET /api/citations/session/{id}` | GET | Session citations |
| `GET /api/citations/document/{id}` | GET | Document APA |
| `GET /api/evidence/{id}` | GET | Single evidence item |
| `GET /api/evidence/{id}/query` | GET | Evidence query details |
| `GET /api/evidence/session/{id}` | GET | Session evidence |
| `GET /api/evidence/session/{id}/coverage` | GET | Coverage report |
| `POST /api/thaijo/search` | POST | ThaiJO article search |
| `GET /api/thaijo/status` | GET | ThaiJO service status |

---

## 6. Configuration Settings — Actual vs Documented

### Settings in code but not in docs:

| Setting | Default | Missing From |
|---------|---------|-------------|
| `REPORT_MAX_TOKENS` | 8192 | All docs |
| `ALLOW_EXTERNAL_URL_IMPORT` | True | All docs |
| `EXTERNAL_URL_TIMEOUT` | 30 | All docs |
| `THAIJO_API_URL` | `http://72.61.120.205:8505/api/v1/thaijo` | ARCHITECTURE.md |
| `THAIJO_TIMEOUT` | 120 | ARCHITECTURE.md |
| `THAIJO_DEFAULT_SIZE` | 5 | ARCHITECTURE.md |
| `THAIJO_MAX_SIZE` | 10 | ARCHITECTURE.md |
| `THAIJO_ENABLED` | True | ARCHITECTURE.md |

---

## 7. Database Migrations — Actual vs Documented

### All 15 Migrations (Actual):

| # | File | Tables | Documented? |
|---|------|--------|-------------|
| 001 | shared_core.sql | dim_geography, dim_time, dim_population_group, dim_facility, dim_source | Yes |
| 002 | document_rag.sql | document_registry, indicator_catalog | Yes |
| 003 | accident_domain.sql | dim_road_segment, fact_accident_event, fact_accident_person, mart_accident_summary, mart_accident_hotspot | Yes |
| 004 | seed_accident_mockup.sql | Seed data | Partially |
| 005 | enhance_road_geo.sql | Alters dim_road_segment | Partially |
| 006 | province_marts.sql | mart_province_year, mart_province_road | Yes |
| 007 | all_years_province.sql | Adds csv_year, serious_injured, views | Partially |
| 008 | prevent_duplicates.sql | UNIQUE constraints | Partially |
| 009 | add_coordinates.sql | Adds lat/lon to events | Partially |
| 010 | evidence_citation.sql | evidence_registry, claim_evidence_link | Yes |
| 011 | pgvector.sql | document_embeddings (3072-dim) | Yes |
| 012 | document_upload_enhanced.sql | Alters document_registry (upload + APA) | Partially |
| 013 | apa_approval_status.sql | Adds apa_approval_status | No |
| 014 | populate_document_chunks.sql | Drops old document_chunks | No |
| **015** | **thaijo_evidence.sql** | **Adds thaijo_* columns to evidence_registry** | **Only in THAIJO_AGENT_IMPLEMENTATION.md** |

### Schema Issue: evidence_type CHECK constraint

Migration 010 creates:
```sql
CHECK (evidence_type IN ('document', 'database', 'api'))
```

But code uses `'thaijo_article'` and `'notebooklm_pdf'` as evidence types.

**Action needed:** Migration to ALTER the CHECK constraint:
```sql
ALTER TABLE evidence_registry DROP CONSTRAINT IF EXISTS evidence_registry_evidence_type_check;
ALTER TABLE evidence_registry ADD CONSTRAINT evidence_registry_evidence_type_check
  CHECK (evidence_type IN ('document', 'database', 'api', 'thaijo_article', 'notebooklm_pdf'));
```

---

## 8. ThaiJO Implementation Status

### Actual Code Status: **FULLY IMPLEMENTED**

| Component | File | Status |
|-----------|------|--------|
| Tool | `src/tools/thaijo.py` | ✅ Exists, `search_thaijo` @tool |
| Config | `src/config.py` | ✅ THAIJO_* settings (5 fields) |
| Router | `src/routers/thaijo.py` | ✅ `/api/thaijo/search`, `/api/thaijo/status` |
| Registration in main.py | `src/main.py` | ✅ `thaijo_router` registered |
| Registration in Retrieval | `src/agents/retrieval.py` | ✅ `search_thaijo` in tools list |
| Citation support | `src/agents/citation_evidence.py` | ✅ C-200~C-299 range in prompt |
| Migration | `database/015_thaijo_evidence.sql` | ✅ Adds thaijo_* columns |
| .env.example | `.env.example` | ⚠️ Not checked |

### Documentation Status:

| Document | Says | Should Say |
|----------|------|-----------|
| `THAIJO_AGENT_IMPLEMENTATION.md` | "Implementation Plan" (future) | **Implementation Complete** |
| `AGENT_WORKFLOW.md` | No ThaiJO mention | Should list search_thaijo as Agent 2 tool |
| `PROJECT_DOCUMENTATION.md` | No ThaiJO mention | Should list ThaiJO integration |

---

## 9. Embedding Dimension

| Source | Says |
|--------|------|
| `config.py` → EMBEDDING_MODEL | `models/gemini-embedding-001` |
| `database/011_pgvector.sql` | `vector(3072)` |
| `rag/vector_store.py` | Uses `genai.Client` with task_type |
| `ARCHITECTURE.md` | "3072-dim" ✓ |
| `DATABASE_API_ARCHITECTURE.md` | Some sections say "768-dim" |

**Actual:** Gemini embedding-001 outputs **3072-dim** vectors. Database stores `vector(3072)`.

---

## 10. Resolution Status (Updated 2026-04-16)

| # | Document | Issue | Status |
|---|----------|-------|--------|
| 1 | **AGENT_WORKFLOW.md** | Agent count wrong, tool names wrong, missing agents | ✅ **DELETED** — superseded by AGENT_WORKFLOW_UNIFIED.md |
| 2 | **PROJECT_DOCUMENTATION.md** | Agent count, missing ThaiJO, incomplete API | ✅ **FIXED** — updated to v0.2.0 with correct 10 agents + ThaiJO |
| 3 | **ARCHITECTURE.md** | Agent count, missing ThaiJO, incomplete config | ✅ **FIXED** — updated to v2.1, correct 10 agents + ThaiJO |
| 4 | **CITATION_EVIDENCE_GUIDE.md** | Tool names wrong (listed old names) | ✅ **FIXED** — correct 4 tools listed, link updated to AGENT_WORKFLOW_UNIFIED.md |
| 5 | **THAIJO_AGENT_IMPLEMENTATION.md** | Status should be COMPLETED not PLAN | ✅ **FIXED** — marked COMPLETED v1.1 |
| 6 | **DATABASE_API_REFERENCE.md** | Missing ~24 API endpoints | ✅ **FIXED** — v2.3 added ThaiJO, MinIO Browse, Document Mgmt, Citation endpoints |
| 7 | **CITATION_APA_FORMAT.md** | C-200 range wrong (websites, not ThaiJO) | ✅ **FIXED** — C-200=ThaiJO, C-300+=websites; added ThaiJO as section 2.3 |
| 8 | **DATABASE_API_ARCHITECTURE.md** | Missing migrations 013-015, embedding dimension | ⚠️ **PARTIAL** — dimension is correct (3072-dim confirmed); migrations 013-015 not yet fully documented |
| 9 | **SRS.md** | Critically outdated (said "6-agent pipeline") | ✅ **DELETED** — requirements covered by ARCHITECTURE.md + PROJECT_DOCUMENTATION.md |
| 10 | **system_overview.md** | Docx export artifact with broken image reference | ✅ **DELETED** — not a usable doc |

### Remaining Action Items

- `DATABASE_API_ARCHITECTURE.md`: Document migrations 013 (apa_approval_status), 014 (populate_document_chunks), 015 (thaijo_evidence columns)
- `evidence_registry` CHECK constraint: Migration needed to allow `thaijo_article` and `notebooklm_pdf` as evidence_type values (see Section 7 above)
