# Musya Agent — Project Documentation

> **Version**: 0.2.0  
> **Last Updated**: 2026-04-16  
> **Stack**: Python 3.12 · FastAPI · CrewAI · PostgreSQL · pgvector · MinIO · Google Gemini

---

## 1. Project Overview

**Musya Agent** เป็น backend สำหรับระบบ Agentic AI + RAG (Retrieval-Augmented Generation) ที่ออกแบบมาเพื่อวิเคราะห์ข้อมูลสุขภาพสาธารณะ โดยเฉพาะข้อมูลอุบัติเหตุทางถนนของประเทศไทย ระบบใช้ CrewAI ในการจัดการ multi-agent pipeline ที่ทำงานร่วมกันตั้งแต่การตีความคำขอ ค้นหาข้อมูล วิเคราะห์ สร้างกราฟ จนถึงเขียนรายงาน

### Key Features
- **Multi-Agent Pipeline**: 10 agents (Router + 9 sequential) ด้วย CrewAI, 2 pipelines (Chat + Policy Brief)
- **Dual RAG**: Document RAG (pgvector 3072-dim) + Database RAG (PostgreSQL)
- **ThaiJO Integration**: ค้นหาบทความวิชาการจาก TCI-THAIJO พร้อม AI summary
- **Citation & Evidence**: APA 7th Edition citations, evidence registry, coverage validation
- **SQL Specialist**: เขียนและรัน custom SQL query ได้อัตโนมัติ (SELECT/WITH only)
- **Chart Builder**: สร้าง Chart.js-compatible JSON สำหรับ frontend (7 chart types)
- **Thai-Language Reports**: รายงานภาษาไทยระดับราชการ (2,000-4,000 คำ)
- **REST API**: FastAPI server ที่รองรับ sync, SSE streaming, และ unified routing
- **Policy Brief Pipeline**: สร้าง Policy Brief สำหรับ 5 จังหวัดเขตสุขภาพที่ 10 (RTI/Mental/NCD)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ChatV1 Frontend                       │
│               (Next.js — port 3000)                      │
└────────────────────┬────────────────────────────────────┘
                     │  POST /api/agent/chat (proxy)
                     ▼
┌─────────────────────────────────────────────────────────┐
│               Musya Agent Backend                        │
│               (FastAPI — port 8000)                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Routers  │→ │Orchestrat│→ │ Agents  │→ │  Tools  │  │
│  │(10 total)│  │  or      │  │(Router  │  │(25 total│  │
│  │          │  │(CrewAI)  │  │ +9 seq) │  │DB/RAG/..)│  │
│  └──────────┘  └──────────┘  └─────────┘  └─────────┘  │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │PostgreSQL│  │ pgvector │  │       MinIO          │   │
│  │(data)    │  │(vectors) │  │   (documents)        │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Message
  → POST /api/chat/unified
    → Request Router                   (เลือก pipeline: chat / policy_brief)
    → Orchestrator.run_chat()
      → Task 1: Request Interpreter    (ตีความคำขอ → JSON)
      → Task 2: Retrieval Agent        (ค้นข้อมูลจาก DB + Documents + ThaiJO)
      → Task 3: SQL Specialist          (เขียน/รัน custom SQL)
      → Task 4: Citation & Evidence     (normalize, register, APA citations)
      → Task 5: Accident Analyst        (วิเคราะห์ข้อมูล, Haddon Matrix)
      → Task 6: Chart Builder           (สร้าง ChartSpec JSON)
      → Task 7: Research Synthesizer    (narrative prose, 1200-2000 คำ)
      → Task 8: Deep Analyst            (root cause, policy gaps, 1000-1500 คำ)
      → Task 9: Report Composer         (รายงานภาษาไทย, 2000-4000 คำ)
    → AgentResponse (content, charts, tables, citations, follow_ups)
```

---

## 3. Directory Structure

```
Agent/
├── src/                        # Main application source code
│   ├── main.py                 # FastAPI entrypoint, lifespan, CORS, routers
│   ├── config.py               # Pydantic Settings (env-based config)
│   ├── agents/                 # CrewAI agent definitions (21 files)
│   │   ├── orchestrator.py     # Chat Crew builder, run_chat(), result parsing
│   │   ├── shared_foundation.py # Shared LLM config, agent/task factories
│   │   ├── request_router.py   # Agent 0: Pipeline routing (chat vs policy_brief)
│   │   ├── request_interpreter.py  # Agent 1: ตีความคำขอผู้ใช้ → structured JSON
│   │   ├── retrieval.py        # Agent 2: ค้นข้อมูลจาก Document RAG + DB + ThaiJO
│   │   ├── sql_specialist.py   # Agent 3: เขียน/รัน custom SQL (schema-aware)
│   │   ├── citation_evidence.py # Agent 4: Citation & Evidence (APA 7th)
│   │   ├── analyst_accident.py # Agent 5: วิเคราะห์อุบัติเหตุ, Haddon Matrix
│   │   ├── chart_builder.py    # Agent 6: สร้าง ChartSpec JSON สำหรับ frontend
│   │   ├── research_synthesizer.py # Agent 7: narrative prose (1200-2000 คำ)
│   │   ├── deep_analyst.py     # Agent 8: root cause, policy gaps (1000-1500 คำ)
│   │   ├── report_writer.py    # Agent 9: เขียนรายงานภาษาไทย (2000-4000 คำ)
│   │   ├── policy_orchestrator.py  # Policy Brief Crew builder
│   │   ├── unified_orchestrator.py # Unified routing (chat/policy auto-select)
│   │   ├── nlm_data_fetcher.py # NotebookLM data fetcher
│   │   ├── policy_rti.py       # RTI domain analyst (Policy Brief)
│   │   ├── policy_mental.py    # Mental health analyst (Policy Brief)
│   │   ├── policy_ncd.py       # NCD analyst (Policy Brief)
│   │   ├── policy_report_writer.py # Policy Brief report writer
│   │   ├── progress.py         # Progress tracking for SSE streaming
│   │   └── __init__.py
│   ├── tools/                  # CrewAI tool functions (6 files)
│   │   ├── accident.py         # 7 accident data tools (province, roads, ranking, etc.)
│   │   ├── chart_builder.py    # 7 chart-building tools (trend, hotspot, pie, etc.)
│   │   ├── common.py           # search_documents, get_indicator_catalog, get_geography_profile
│   │   ├── sql_tools.py        # execute_custom_sql, explain_schema, get_table_row_count
│   │   ├── thaijo.py           # search_thaijo (TCI-THAIJO academic search)
│   │   └── notebooklm.py       # nlm_ask, get_supported_provinces (NotebookLM)
│   ├── routers/                # FastAPI route handlers (10 files)
│   │   ├── chat.py             # POST /api/chat, /api/chat/unified, /api/chat/stream
│   │   ├── health.py           # GET /api/health
│   │   ├── ingest.py           # POST /api/ingest
│   │   ├── evidence.py         # GET/POST /api/evidence/*, /api/documents/open
│   │   ├── upload.py           # POST /api/documents/upload, /upload-url
│   │   ├── documents.py        # CRUD /api/documents, MinIO browse
│   │   ├── citation.py         # GET /api/citations/session/*, /document/*
│   │   ├── policy_brief.py     # POST /api/policy-brief
│   │   ├── thaijo.py           # POST /api/thaijo/search, GET /api/thaijo/status
│   │   └── test_ui.py          # Test UI routes
│   ├── schemas/                # Pydantic request/response models
│   │   ├── request.py          # ChatRequest, ReportRequest
│   │   ├── response.py         # AgentResponse, ChartSpec, TableSpec, Citation
│   │   ├── evidence.py         # EvidenceItem, Claim, ClaimEvidenceLink, CoverageReport
│   │   └── policy_brief.py     # PolicyBriefRequest, PolicyBriefResponse
│   ├── rag/                    # RAG (Retrieval-Augmented Generation) layer
│   │   ├── document_rag.py     # PDF/DOCX extraction, chunking, ingestion, search
│   │   ├── vector_store.py     # pgvector client (psycopg2 + Gemini embeddings), add/search documents
│   │   └── database_rag.py     # PostgreSQL query helpers
│   └── db/                     # Database connectivity
│       ├── pool.py             # Async (asyncpg) + Sync (psycopg2) connection pools
│       └── minio_client.py     # MinIO client for document storage
├── database/                   # SQL migrations + data import scripts (15 migrations)
│   ├── 001_shared_core.sql     # dim_geography, dim_time, dim_source, etc.
│   ├── 002_document_rag.sql    # document_registry, document_chunks, indicator_catalog
│   ├── 003_accident_domain.sql # fact_accident_event, fact_accident_person, mart tables
│   ├── 004_seed_accident_mockup.sql  # Mock data seeding
│   ├── 005_enhance_road_geo.sql     # Alters dim_road_segment
│   ├── 006_province_marts.sql       # mart_province_year, mart_province_road
│   ├── 007_all_years_province.sql   # csv_year, serious_injured, views
│   ├── 008_prevent_duplicates.sql   # UNIQUE constraints
│   ├── 009_add_coordinates.sql      # lat/lon to events
│   ├── 010_evidence_citation.sql    # evidence_registry, claim_evidence_link
│   ├── 011_pgvector.sql             # document_embeddings (vector 3072-dim)
│   ├── 012_document_upload_enhanced.sql # Upload + APA fields
│   ├── 013_apa_approval_status.sql  # apa_approval_status column
│   ├── 014_populate_document_chunks.sql # Drops old document_chunks
│   ├── 015_thaijo_evidence.sql      # ThaiJO columns in evidence_registry
│   ├── import_csv_all_years.py # CSV import script (accident2020–2026.csv)
│   └── accident20XX.csv        # Raw accident CSV data (2020–2026)
├── doc/                        # Documentation
├── tests/                      # Pytest test suite
├── static/                     # Static files (test UI HTML)
├── pyproject.toml              # Project metadata + dependencies
├── docker-compose.yml          # PostgreSQL (pgvector/pgvector:pg16) + MinIO
├── Dockerfile                  # Agent server container
└── .env                        # Environment variables
```

---

## 4. Agents — Chat Pipeline (10 agents)

### Agent 0: Request Router
- **Role**: Pipeline routing — เลือกว่าจะใช้ chat pipeline หรือ policy_brief pipeline
- **LLM Tier**: Fast (gemini-2.0-flash)
- **Tools**: ไม่มี

### Agent 1: Request Interpreter
- **Role**: แปลความคำขอผู้ใช้เป็น structured JSON
- **Output**: `{ topics, geography, time_range, report_type, focus, language }`
- **LLM Tier**: Fast
- **Tools**: ไม่มี

### Agent 2: Data Retrieval Specialist
- **Role**: ค้นหาข้อมูลจาก Document RAG, Database RAG, และ ThaiJO
- **LLM Tier**: Fast
- **Tools** (11 tools):
  - `search_documents` — ค้นเอกสารจาก pgvector (`document_embeddings`)
  - `get_indicator_catalog` — ตัวชี้วัดสุขภาพ
  - `get_geography_profile` — ข้อมูลพื้นที่
  - `get_province_year_summary` — สรุปอุบัติเหตุรายจังหวัดรายปี
  - `get_province_roads` — ถนนเสี่ยงในจังหวัด
  - `get_all_provinces_ranking` — จัดอันดับ 77 จังหวัด
  - `get_accident_summary` — สรุปอุบัติเหตุรายเดือน
  - `get_accident_hotspots` — จุดเสี่ยง top-N
  - `get_accident_time_distribution` — กระจายตามเวลา
  - `get_road_condition_risk` — ความเสี่ยงตามสภาพถนน
  - `search_thaijo` — ค้นหาบทความวิชาการจาก TCI-THAIJO

### Agent 3: SQL Database Specialist
- **Role**: เขียนและรัน custom SQL query
- **LLM Tier**: Fast
- **Tools** (3 tools):
  - `execute_custom_sql` — รัน read-only SQL (auto LIMIT 1000, SELECT/WITH only)
  - `explain_schema` — ดู schema ของ table
  - `get_table_row_count` — นับจำนวนแถวในตาราง

### Agent 4: Citation & Evidence
- **Role**: Normalize evidence, สร้าง APA citations, map claims to evidence
- **LLM Tier**: Fast
- **Tools** (4 tools):
  - `list_all_documents_apa` — แสดงรายการเอกสารทั้งหมดพร้อม APA citation
  - `lookup_document_apa` — ค้นหา APA citation ของเอกสารเฉพาะ
  - `register_evidence` — บันทึก EvidenceItem ลง evidence_registry
  - `register_claim_links` — บันทึก Claim↔Evidence links
- **Citation Ranges**: C-001~C-099 (reports), C-100~C-199 (database), C-200~C-299 (ThaiJO), C-300+ (external)

### Agent 5: Accident Data Analyst
- **Role**: วิเคราะห์ข้อมูล สังเคราะห์ key_findings, trends, risk_areas, Haddon Matrix
- **LLM Tier**: Pro (gemini-2.5-pro)
- **Tools**: ไม่มี (ใช้ context จาก Retrieval + SQL + Citation)

### Agent 6: Report Chart Builder
- **Role**: สร้าง ChartSpec JSON สำหรับ Chart.js
- **LLM Tier**: Pro
- **Tools** (7 tools):
  - `build_province_year_trend_chart` — line chart แนวโน้มรายปี
  - `build_province_roads_bar_chart` — bar chart ถนนเสี่ยง
  - `build_accident_trend_chart` — line chart แนวโน้มรายเดือน
  - `build_hotspot_bar_chart` — bar chart จุดเสี่ยง
  - `build_time_distribution_chart` — bar chart ตามชั่วโมง
  - `build_road_condition_pie_chart` — pie chart สภาพถนน
  - `build_monthly_death_bar_chart` — bar chart เสียชีวิตรายเดือน

### Agent 7: Research Synthesizer
- **Role**: สังเคราะห์ข้อมูลเป็น narrative prose (1,200-2,000 คำ)
- **LLM Tier**: Pro
- **Output**: 4 narrative blocks — สถานการณ์ภาพรวม, วิเคราะห์ปัจจัยเสี่ยง, เปรียบเทียบ, บทเรียน
- **Tools**: ไม่มี

### Agent 8: Deep Analyst
- **Role**: วิเคราะห์เชิงลึก root cause, policy gaps (1,000-1,500 คำ)
- **LLM Tier**: Pro
- **Output**: 4 มิติ — Root Cause Analysis, Policy Gap, Systemic Barriers, Actionable Recommendations
- **Tools**: ไม่มี

### Agent 9: Report Composer
- **Role**: เรียบเรียงรายงานภาษาไทยระดับราชการ (2,000-4,000 คำ)
- **LLM Tier**: Pro
- **Output Structure**:
  - สรุปสาระสำคัญ → สถานการณ์ปัจจุบัน → ข้อค้นพบ → พื้นที่/กลุ่มเสี่ยง → ข้อเสนอเชิงมาตรการ → ข้อจำกัด → คำถามติดตาม 3 ข้อ

### Policy Brief Pipeline (9 agents)
ใช้ agents ร่วมกัน (Router, Interpreter, Retrieval, SQL, Citation) และเพิ่ม domain analysts:
- **RTI Analyst** — วิเคราะห์อุบัติเหตุทางถนน (3 tools)
- **Mental Health Analyst** — วิเคราะห์สุขภาพจิต/การฆ่าตัวตาย
- **NCD Analyst** — วิเคราะห์โรคไม่ติดต่อเรื้อรัง/โภชนาการ
- **Policy Report Writer** — สังเคราะห์ 3-domain brief
- **NLM Data Fetcher** — ดึงข้อมูลจาก NotebookLM (2 tools: `nlm_ask`, `get_supported_provinces`)

---

## 5. API Endpoints (10 routers, ~40 endpoints)

### Core Pipeline
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root — API info + links |
| `GET` | `/api/health` | Health check (PostgreSQL + MinIO + pgvector) |
| `POST` | `/api/chat` | Chat pipeline → `AgentResponse` |
| `POST` | `/api/chat/unified` | Auto-route to chat or policy pipeline |
| `POST` | `/api/chat/stream` | SSE streaming with progress |
| `POST` | `/api/ingest` | Ingest documents from MinIO → pgvector |
| `POST` | `/api/policy-brief` | Policy Brief pipeline |
| `POST` | `/api/policy-brief/stream` | Policy Brief SSE streaming |

### Document Management
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/upload` | Direct file upload |
| `POST` | `/api/documents/upload-url` | Upload from URL |
| `GET` | `/api/documents` | Paginated document list |
| `GET` | `/api/documents/registry` | All document registry |
| `GET` | `/api/documents/{id}` | Document detail |
| `PATCH` | `/api/documents/{id}` | Update document metadata |
| `DELETE` | `/api/documents/{id}` | Delete document |
| `POST` | `/api/documents/{id}/reingest` | Reingest document |
| `GET` | `/api/documents/minio/tree` | MinIO folder tree |
| `GET` | `/api/documents/minio/browse` | Browse MinIO prefix |
| `GET` | `/api/documents/minio/read` | Read file text preview |
| `POST` | `/api/documents/minio/apa-draft` | AI-generated APA draft |
| `POST` | `/api/documents/minio/approve` | Approve & ingest document |
| `POST` | `/api/documents/analyze-upload` | Analyze uploaded file for APA |

### Evidence & Citation
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/documents/open/{id}` | Open document (redirect to MinIO URL) |
| `GET` | `/api/evidence/{id}` | Single evidence item |
| `GET` | `/api/evidence/{id}/query` | Evidence query details |
| `GET` | `/api/evidence/session/{id}` | Session evidence |
| `GET` | `/api/evidence/session/{id}/coverage` | Coverage report |
| `GET` | `/api/citations/session/{id}` | Session citations |
| `GET` | `/api/citations/document/{id}` | Document APA |

### ThaiJO
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/thaijo/search` | ThaiJO article search |
| `GET` | `/api/thaijo/status` | ThaiJO service status |

### Other
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/docs` | FastAPI auto-generated Swagger docs |
| `GET` | `/test` | Standalone test UI |

### Request/Response Schemas

**ChatRequest**:
```json
{
  "message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025",
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

**AgentResponse**:
```json
{
  "content": "## สรุปสาระสำคัญ\n...",
  "topic": "accident",
  "charts": [
    {
      "type": "line",
      "title": "แนวโน้มอุบัติเหตุจังหวัดเชียงใหม่",
      "data": { "labels": ["2020","2021",...], "datasets": [...] },
      "options": {},
      "source_note": "mart_province_year"
    }
  ],
  "tables": [],
  "citations": [],
  "follow_ups": ["คำถาม 1", "คำถาม 2", "คำถาม 3"],
  "metadata": { "elapsed_seconds": 45.2, "agent_count": 10, "chart_count": 2 }
}
```

---

## 6. Database Schema

### Fact Tables (ข้อมูลหลัก)
| Table | Description | Key Columns |
|-------|-------------|-------------|
| `fact_accident_event` | เหตุการณ์อุบัติเหตุ | accident_id, event_datetime, geography_id, road_segment_id, severity_level, injured_count, death_count, csv_year |
| `fact_accident_person` | ผู้ประสบเหตุแต่ละคน | person_event_id, accident_id, age, sex, injury_level, helmet_used, seatbelt_used |

### Dimension Tables (ข้อมูลมิติ)
| Table | Description | Key Columns |
|-------|-------------|-------------|
| `dim_geography` | พื้นที่ (จังหวัด/อำเภอ) | geography_id, province_name, district_name, latitude, longitude |
| `dim_road_segment` | ข้อมูลถนน | road_segment_id, road_name, road_code, geography_id, km_marker |
| `dim_time` | มิติเวลา | time_id, full_date, year_no, month_no, day_of_week |
| `dim_source` | แหล่งข้อมูล | source_id, source_name, source_type |

### Mart Tables (ข้อมูลสรุป)
| Table | Description | Key Columns |
|-------|-------------|-------------|
| `mart_accident_summary` | สรุปรายเดือน | year_no, month_no, geography_id, accident_count, death_count |
| `mart_accident_hotspot` | จุดเสี่ยง | hotspot_id, hotspot_score, accident_count, dominant_timeband |
| `mart_province_year` | สรุปรายจังหวัดรายปี | province_name, year_no, accident_count, death_count, top_vehicle, top_cause |
| `mart_province_road` | สรุปรายถนน | province_name, road_name, year_no, hotspot_score, dominant_cause |

### Data Coverage
- **ปีข้อมูล**: 2020–2026 (CSV import)
- **จังหวัด**: ครบ 77 จังหวัด
- **UNIQUE constraints**: ป้องกันข้อมูลซ้ำทั้ง fact_accident_event, dim_geography, dim_road_segment

---

## 7. Infrastructure

### External Services
| Service | Purpose | Default Connection |
|---------|---------|-------------------|
| **PostgreSQL** | Relational DB (facts, dims, marts) | `localhost:5432 / chat-aio` |
| **MinIO** | Object storage (PDF, DOCX uploads) | `localhost:9000` |
| **pgvector** | Vector store (document embeddings, 3072-dim) | PostgreSQL `chat-aio` — table `document_embeddings` |
| **Google Gemini** | LLM — Fast: `gemini-2.0-flash`, Pro: `gemini-2.5-pro` | API key required |
| **ThaiJO API** | TCI-THAIJO academic article search | `http://72.61.120.205:8505/api/v1/thaijo` |

### Connection Pools
- **Async Pool** (asyncpg): สำหรับ FastAPI async endpoints — min 2, max 10
- **Sync Pool** (psycopg2): สำหรับ CrewAI tools (synchronous) — min 1, max 5

---

## 8. Configuration

ใช้ Pydantic Settings อ่านจาก `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `chat-aio` | Database name (shared with ChatV1) |
| `DB_USER` | `postgres` | DB user |
| `DB_PASSWORD` | `1234` | DB password |
| `MINIO_ENDPOINT` | `localhost` | MinIO host |
| `MINIO_PORT` | `9000` | MinIO port |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `uploads` | MinIO bucket |
| `GEMINI_API_KEY` | — | Google Gemini API key (**required**) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `PGVECTOR_COLLECTION` | `musya_documents` | pgvector collection name |
| `EMBEDDING_MODEL` | `models/gemini-embedding-001` | Gemini embedding model (3072-dim) |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |
| `REPORT_MAX_TOKENS` | `8192` | Max tokens for report generation |
| `ALLOW_EXTERNAL_URL_IMPORT` | `True` | Allow document upload from external URL |
| `EXTERNAL_URL_TIMEOUT` | `30` | Timeout for external URL import (seconds) |
| `THAIJO_API_URL` | `http://72.61.120.205:8505/api/v1/thaijo` | ThaiJO microservice URL |
| `THAIJO_TIMEOUT` | `120` | ThaiJO request timeout (seconds) |
| `THAIJO_DEFAULT_SIZE` | `5` | Default number of ThaiJO results |
| `THAIJO_MAX_SIZE` | `10` | Max ThaiJO results per query |
| `THAIJO_ENABLED` | `True` | Enable/disable ThaiJO integration |

> **Important**: ต้องตั้งทั้ง `GEMINI_API_KEY` และระบบจะ set `GOOGLE_API_KEY` ให้อัตโนมัติ

---

## 9. Setup & Run

### Prerequisites
- Python 3.11–3.13
- PostgreSQL 15+
- MinIO
- Google Gemini API key

### Installation
```bash
cd Agent
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -e .
```

### Database Migrations
```bash
# Run migrations in order (001–015)
psql -U postgres -d chat-aio -f database/001_shared_core.sql
psql -U postgres -d chat-aio -f database/002_document_rag.sql
psql -U postgres -d chat-aio -f database/003_accident_domain.sql
# ... through 015_thaijo_evidence.sql

# Import CSV data
python database/import_csv_all_years.py
```

### Run Server
```bash
python -m src.main
# or
agent-server          # via pyproject.toml [project.scripts]
# or
run_server.bat        # Windows batch file
```

### Run Tests
```bash
pytest tests/ -v
```

---

## 10. Key Design Decisions

1. **`.replace()` not `.format()`** — Prompt templates ใช้ `.replace("{user_message}", ...)` เพราะ JSON curly braces จะ conflict กับ Python `.format()`

2. **Sequential Process** — CrewAI Crew ใช้ `Process.sequential` เพราะแต่ละ task ต้องใช้ context จาก task ก่อนหน้า

3. **Shared Database** — ใช้ DB `chat-aio` เดียวกับ ChatV1 เพื่อ reuse dim tables และ domain data

4. **Chart.js Contract** — `ChartSpec` ออกแบบให้ map 1:1 กับ `ChartRenderer.tsx` ใน ChatV1 frontend

5. **Safety** — `execute_custom_sql` อนุญาตเฉพาะ SELECT/WITH, auto LIMIT 1000

6. **Idempotent Import** — CSV import scripts ใช้ `ON CONFLICT DO NOTHING` ป้องกันข้อมูลซ้ำ

---

## 11. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `crewai[tools]` | >=1.1.0 | Multi-agent orchestration |
| `fastapi` | >=0.115 | Web framework |
| `uvicorn[standard]` | >=0.30 | ASGI server |
| `asyncpg` | >=0.29 | Async PostgreSQL driver |
| `psycopg2-binary` | >=2.9 | Sync PostgreSQL driver |
| `pgvector` | >=0.3 | pgvector Python adapter |
| `psycopg2-binary` | >=2.9 | Sync PostgreSQL driver (also used by vector_store) |
| `minio` | >=7.2 | Object storage client |
| `google-genai` | >=1.0 | Gemini API — LLM + embedding (non-deprecated) |
| `langchain-google-genai` | >=2.0 | LangChain Gemini integration |
| `langchain-text-splitters` | >=0.3 | Text chunking |
| `PyMuPDF` | >=1.24 | PDF text extraction |
| `python-docx` | >=1.1 | DOCX text extraction |
| `pydantic` | >=2.8 | Data validation |
| `pydantic-settings` | >=2.5 | Env-based config |
| `sse-starlette` | >=2.1 | Server-Sent Events |
| `python-dotenv` | >=1.0 | .env file loading |
