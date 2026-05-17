# Code ↔ Documentation Alignment Report

> Generated: 2026-05-16
> Source of truth: **Actual source code** in `Agent/src/` and `Agent/database/`

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

---

## 2. Agent Pipeline — Policy Brief (Actual: 8 agents + Router)

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

## 3. Agent Pipeline — Short Chat (Actual: 3 agents + Router)

| # | Agent | Role | Tools | LLM Tier | File |
|---|-------|------|-------|----------|------|
| 0 | Request Router | Pipeline routing (mode=short) | 0 | fast | `request_router.py` |
| 1 | Request Interpreter | Parse intent | 0 | fast | `request_interpreter.py` |
| 2 | Quick Retrieval | Fetch data quickly | 3 | fast | `shared_foundation.py` |
| 3 | Quick Answer Writer | 500-1000 words answer | 0 | pro | `quick_answer_writer.py` |

---

## 4. Agent Pipeline — ThaiJO Research Report (Actual: 6 agents + Router)

| # | Agent | Role | Tools | LLM Tier | File |
|---|-------|------|-------|----------|------|
| 0 | Request Router | Pipeline routing | 0 | fast | `request_router.py` |
| 1 | Research Topic Parser | Parse topic into search queries | 0 | fast | `thaijo_topic_parser.py` |
| 2 | ThaiJO Searcher | Execute multi-query search | 1 | fast | `thaijo_searcher.py` |
| 3 | Article Screener | Score relevance (0-10) and filter | 0 | fast | `thaijo_screener.py` |
| 4 | Citation Generator | Generate APA citations (C-200+) | 2 | fast | `citation_evidence.py` |
| 5 | Research Synthesizer| Thematic analysis | 0 | pro | `thaijo_research_synthesizer.py` |
| 6 | Report Composer | Lit review report (1500-3000 words) | 7 | pro | `thaijo_report_composer.py` |

---

## 5. Standalone Agents

| Agent | Role | Tools | LLM Tier | File |
|-------|------|-------|----------|------|
| ThaiJO Evidence Sync | Enrich cache fields and register evidence | 0 | fast (haiku) | `thaijo_evidence_sync.py` |

---

## 6. Tool Inventory — Actual

### Agent 2: Retrieval — 11 tools

| Tool Name (Actual) | Source File |
|---------------------|-----------|
| `search_documents` | `tools/common.py` |
| `get_indicator_catalog` | `tools/common.py` |
| `get_geography_profile` | `tools/common.py` |
| `get_province_year_summary` | `tools/accident.py` |
| `get_province_roads` | `tools/accident.py` |
| `get_all_provinces_ranking` | `tools/accident.py` |
| `get_accident_summary` | `tools/accident.py` |
| `get_accident_hotspots` | `tools/accident.py` |
| `get_accident_time_distribution` | `tools/accident.py` |
| `get_road_condition_risk` | `tools/accident.py` |
| `search_thaijo` | `tools/thaijo.py` |

### Agent 3: SQL Specialist — 3 tools

| Tool Name (Actual) | Source File |
|---------------------|-----------|
| `execute_custom_sql` | `tools/sql_tools.py` |
| `explain_schema` | `tools/sql_tools.py` |
| `get_table_row_count` | `tools/sql_tools.py` |

### Agent 4: Citation & Evidence — 4 tools

| Tool Name (Actual Code) | Source File |
|--------------------------|-----------|
| `list_all_documents_apa` | `agents/citation_evidence.py` |
| `lookup_document_apa` | `agents/citation_evidence.py` |
| `register_evidence` | `agents/citation_evidence.py` |
| `register_claim_links` | `agents/citation_evidence.py` |

### Agent 6: Chart Builder — 7 tools

| Tool Name (Actual Code) | Source File |
|--------------------------|-----------|
| `build_accident_trend_chart` | `tools/chart_builder.py` |
| `build_hotspot_bar_chart` | `tools/chart_builder.py` |
| `build_time_distribution_chart` | `tools/chart_builder.py` |
| `build_road_condition_pie_chart` | `tools/chart_builder.py` |
| `build_monthly_death_bar_chart` | `tools/chart_builder.py` |
| `build_province_year_trend_chart` | `tools/chart_builder.py` |
| `build_province_roads_bar_chart` | `tools/chart_builder.py` |

### NLM Data Fetcher — 2 tools

| Tool Name (Actual) | Source File |
|--------------------|--------|
| `nlm_ask` | `tools/notebooklm.py` |
| `get_supported_provinces` | `tools/notebooklm.py` |

---

## 7. Citation Code Ranges

| Range | Source Type | Trust Level |
|-------|-----------|-------------|
| C-001 to C-099 | Reports (notebooklm_pdf / document) | High |
| C-100 to C-199 | Database / dataset | High (mart) / Medium (fact) |
| C-200 to C-299 | ThaiJO academic articles | Medium |
| C-300+ | External sources | Variable |

---

## 8. API Endpoints — Actual (from `main.py` and routers)

### `chat.py`
- `POST /api/chat`
- `POST /api/chat/unified`
- `POST /api/chat/stream`
- `POST /api/chat/short`
- `POST /api/chat/short/stream`

### `policy_brief.py`
- `GET /api/policy-brief/provinces`
- `POST /api/policy-brief`

### `thaijo.py`
- `POST /api/thaijo/search`
- `POST /api/thaijo/multi-search`
- `GET /api/thaijo/status`
- `GET /api/thaijo/cache`
- `GET /api/thaijo/cache/stats`
- `GET /api/thaijo/cache/{key}`
- `DELETE /api/thaijo/cache/{key}`
- `DELETE /api/thaijo/cache`
- `POST /api/thaijo/sync-evidence`
- `GET /api/thaijo/evidence`
- `POST /api/thaijo/fix-evidence-urls`
- `POST /api/thaijo/evidence-sync`
- `GET /api/thaijo/evidence-audit`
- `POST /api/thaijo/research`
- `POST /api/thaijo/research/stream`

### `documents.py` & `upload.py` & `ingest.py`
- `GET /api/documents`
- `GET /api/documents/registry`
- `GET /api/documents/{document_id}`
- `PATCH /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`
- `POST /api/documents/{document_id}/reingest`
- `GET /api/documents/minio/tree`
- `GET /api/documents/minio/browse`
- `GET /api/documents/minio/read`
- `POST /api/documents/minio/apa-draft`
- `POST /api/documents/minio/approve`
- `POST /api/documents/analyze-upload`
- `POST /api/documents/upload`
- `POST /api/documents/upload-url`
- `POST /api/ingest`

### `evidence.py` & `citation.py`
- `GET /api/documents/open/{document_id}`
- `GET /api/documents/open/{document_id}/info`
- `GET /api/evidence/{evidence_id}`
- `GET /api/evidence/{evidence_id}/query`
- `GET /api/evidence/session/{session_id}`
- `GET /api/evidence/session/{session_id}/coverage`
- `GET /api/citations/session/{session_id}`
- `GET /api/citations/document/{document_id}`

### `health.py` & `test_ui.py`
- `GET /api/health`
- `GET /api/debug/patch-status`
- `POST /api/test/tool/*` (various tools)
- `POST /api/test/chart/*` (various charts)
- `POST /api/test/query`

---

## 9. Database Migrations — Actual (21 Migrations)

| # | File | Focus |
|---|------|-------|
| 001 | `001_shared_core.sql` | Dimensions |
| 002 | `002_document_rag.sql` | `document_registry`, `indicator_catalog` |
| 003 | `003_accident_domain.sql` | Fact/Mart tables |
| 004 | `004_seed_accident_mockup.sql` | Seed data |
| 005 | `005_enhance_road_geo.sql` | Alters `dim_road_segment` |
| 006 | `006_province_marts.sql` | `mart_province_year`, `mart_province_road` |
| 007 | `007_all_years_province.sql` | Adds `csv_year`, `serious_injured` |
| 008 | `008_prevent_duplicates.sql` | UNIQUE constraints |
| 009 | `009_add_coordinates_to_events.sql`| `lat/lon` to events |
| 010 | `010_evidence_citation.sql` | `evidence_registry`, `claim_evidence_link` |
| 011 | `011_pgvector.sql` | `document_embeddings` (3072-dim) |
| 012 | `012_document_upload_enhanced.sql`| Upload + APA metadata |
| 013 | `013_apa_approval_status.sql` | `apa_approval_status` |
| 014 | `014_populate_document_chunks.sql`| Drops `document_chunks` |
| 015 | `015_thaijo_evidence.sql` | `thaijo_*` columns in `evidence_registry` |
| 016 | `016_widen_apa_year.sql` | Type length changes |
| 017 | `017_fix_evidence_type_constraint.sql`| Fixed CHECK constraint for evidence_type |
| 018 | `018_thaijo_search_cache.sql` | `thaijo_search_cache` table with GIN index |
| 019 | `019_cleanup_thaijo_evidence.sql` | Cleaned up dirty URL data |
| 020 | `020_fix_evidence_download_urls.sql`| Normalize download URLs to view URLs |
| 021 | `021_evidence_registry_apa_thaijo.sql`| Added `thaijo_search_term` |

---

## 10. Documentation Discrepancies Found and Resolved

1. **Migrations Documentation**: The `DATABASE_API_ARCHITECTURE.md`, `DATABASE_API_REFERENCE.md`, and `ARCHITECTURE.md` only documented migrations up to 015. The system actually has 21 migrations, which are now tracked above.
2. **Missing ThaiJO Evidence Sync Agent**: `thaijo_evidence_sync.py` has been explicitly added in Section 5.
3. **Missing Short Chat Pipeline**: Now tracked in Section 3.
4. **Missing ThaiJO Research Report Pipeline**: Now tracked in Section 4.
5. **Tool Naming Constraints**: All correct tool names correspond exactly to the code implementations in `tools/`.
6. **API Endpoints**: Dozens of new endpoints like `POST /api/chat/short/stream`, `/api/thaijo/evidence-audit`, `/api/documents/minio/tree`, etc. are now accurately reflected in Section 8.
7. **`evidence_type` CHECK Constraint**: Migration 017 correctly addresses the CHECK constraint update mentioned in older documentation.