# เอกสารสถาปัตยกรรมระบบ (System Architecture Document)
# Musya Agent — AI Backend สำหรับวิเคราะห์ข้อมูลสุขภาพ

> **เวอร์ชัน**: 2.0  
> **วันที่**: 2026-04-13  
> **ผู้อ่านเป้าหมาย**: Developer ใหม่ที่เข้ามาทำงานกับโปรเจกต์  
> **ขอบเขต**: Agent backend + แผนการย้ายความสามารถจาก Chat-

---

## 1. บทนำ

### 1.1 วัตถุประสงค์
เอกสารฉบับนี้อธิบายสถาปัตยกรรมของ **Musya Agent** ซึ่งเป็น backend AI service ที่:
1. ให้บริการ multi-agent pipeline (CrewAI) สำหรับวิเคราะห์ข้อมูลสุขภาพสาธารณะ (Phase 1: 6 agents, Phase 2: 7-8 agents พร้อม Citation & Evidence)
2. ให้บริการ Document RAG + Database RAG
3. **Citation & Evidence Layer** — trust layer ที่ทำให้รายงานตรวจสอบย้อนกลับถึงแหล่งข้อมูลต้นทางได้
4. **รองรับความสามารถที่ย้ายมาจาก Chat- frontend** (tool detection, API planning, domain queries)

### 1.2 ขอบเขตของ Components

| Component | เทคโนโลยี | Port | บทบาท | สถานะ |
|-----------|-----------|------|--------|-------|
| **Agent** | Python 3.12, FastAPI, CrewAI | 8000 | Backend AI service | ✅ Active |
| **Chat-** | Next.js 16, React 19, TypeScript | 3000 | Frontend หลัก (ปัจจุบัน) | ✅ Active |
| **ChatV1** | Next.js 16, React 19, TypeScript | 3000 | Frontend เดิม (legacy, Clean Architecture) | ⚠️ Legacy |

### 1.3 วิวัฒนาการระบบ

```
Phase 0 (เดิม):
  Chat- → เรียก Gemini API โดยตรงจาก client-side (ไม่ปลอดภัย)
  Chat- → Admin APIs อยู่ใน Next.js API routes

Phase 1 (ปัจจุบัน):
  Chat- → เรียก Agent backend ผ่าน proxy (Agent Mode)
  Agent → 6-agent pipeline สำหรับ accident domain

Phase 2A (แผน — Citation & Evidence):
  Agent → เพิ่ม Citation & Evidence Agent ใน pipeline (trust layer)
  Agent → evidence registry + claim mapping + coverage validation
  Agent → open_url contract สำหรับคลิกกลับไปเอกสารต้นฉบับ
  รายละเอียด: ดู Agent/doc/CITATION_EVIDENCE_AGENT.md

Phase 2B (แผน — ย้ายจาก Chat-):
  Chat- → เรียก Agent backend สำหรับทุก AI operation
  Agent → รวม AI utilities (detect-tool, plan-apis, etc.)
  Agent → รวม domain queries (accident, diabetes, mental)
  Agent → เพิ่ม prompt management (12 templates จาก Chat-)
```

---

## 2. ภาพรวมระบบ (System Context)

### 2.1 System Context Diagram

```
                    ┌────────────────────┐
                    │     ผู้ใช้งาน       │
                    │  (Browser Client)   │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
┌─────────────────┐ ┌────────────────┐ ┌─────────────────────┐
│   Chat- (ใหม่)   │ │ ChatV1 (เดิม)  │ │ External Systems    │
│   Next.js 16    │ │  Next.js 16    │ │ (อนาคต)             │
│   port 3000     │ │  port 3000     │ │                     │
└───────┬─────────┘ └──────┬─────────┘ └──────────┬──────────┘
        │                  │                       │
        │    ┌─────────────┤                       │
        │    │  proxy /api/agent/chat              │
        │    │  ★ Phase 2: all /api/ai/* calls     │
        │    └─────────────┼───────────────────────┘
        │                  │
   ┌────┴──────────────────┴────────────────────────┐
   │             Musya Agent Backend                  │
   │             FastAPI — port 8000                  │
   │                                                  │
   │  ┌─────────────────────────────────────────────┐ │
   │  │  ★ Agent Pipeline (6 agents, CrewAI)         │ │
   │  │  ★ AI Utility APIs (detect, plan, select)    │ │
   │  │  ★ Domain Query APIs (accident, diabetes, …) │ │
   │  │  ★ Document Management (ingest, search, APA) │ │
   │  │  ★ External Integrations (weather, ThaiJO)   │ │
   │  └─────────────────────────────────────────────┘ │
   │                                                  │
   │  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │
   │  │PostgreSQL│  │pgvector  │  │     MinIO       │ │
   │  │  :5432   │  │(built-in)│  │     :9000       │ │
   │  │ chat-aio │  │doc_embed │  │    uploads      │ │
   │  └──────────┘  └──────────┘  └────────────────┘ │
   └──────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ Google Gemini│ │  Open-Meteo  │ │    ThaiJO    │
   │   (LLM)     │ │  (Weather)   │ │  (Journals)  │
   └──────────────┘ └──────────────┘ └──────────────┘
```

### 2.2 ความสัมพันธ์ระหว่าง Components

- **Chat-** เรียก **Agent backend** ผ่าน proxy `/api/agent/chat`
- **Chat-** ปัจจุบันยังเรียก **Gemini API** โดยตรง (⚠️ จะถูกย้ายไป Agent ใน Phase 2)
- ทั้ง Chat-, ChatV1, Agent ใช้ **PostgreSQL database เดียวกัน** (`chat-aio`)
- ทั้ง Chat-, ChatV1, Agent ใช้ **MinIO bucket เดียวกัน** (`uploads`)
- **pgvector** ใช้เฉพาะ Agent backend (vector store สำหรับ Document RAG — `document_embeddings` table ภายใน PostgreSQL `chat-aio`)

---

## 3. สถาปัตยกรรม Agent Backend (ปัจจุบัน)

### 3.1 Tech Stack

| Layer | เทคโนโลยี |
|-------|-----------|
| Framework | FastAPI 0.115+ / Uvicorn |
| Language | Python 3.12 |
| Agent | CrewAI 1.1.0+ (sequential process) |
| LLM | Google Gemini 2.0 Flash (via litellm) |
| DB | PostgreSQL 16 (asyncpg + psycopg2) |
| Vector Store | pgvector 0.8+ (PostgreSQL extension, `document_embeddings` table) |
| Storage | MinIO 7.2+ |
| Doc Processing | PyMuPDF (PDF), python-docx (DOCX) |
| Text Splitting | langchain-text-splitters (1000 chars, 200 overlap) |
| Streaming | SSE via sse-starlette |
| Config | pydantic-settings + python-dotenv |

### 3.2 Layer Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Routers (API Layer)               │
│  chat.py | health.py | ingest.py | test_ui.py             │
│  ★ Phase 2: ai_utils.py | domain.py | document.py         │
├──────────────────────────────────────────────────────────┤
│                  Orchestrator (CrewAI)                      │
│  orchestrator.py — Crew builder, run_chat(), result parser │
├──────────────────────────────────────────────────────────┤
│                  6 Agents (Sequential Pipeline)            │
│  request_interpreter → retrieval → sql_specialist          │
│  → analyst_accident → chart_builder → report_writer        │
├──────────────────────────────────────────────────────────┤
│                  Tools (20+ functions)                      │
│  accident.py (7) | chart_builder.py (7)                    │
│  common.py (3)   | sql_tools.py (3)                        │
├──────────────────────────────────────────────────────────┤
│                  RAG Layer                                  │
│  document_rag.py | vector_store.py | database_rag.py       │
├──────────────────────────────────────────────────────────┤
│                  Data Layer                                 │
│  PostgreSQL (pool.py) | pgvector (vector_store.py)         │
│  MinIO (minio_client.py)                                   │
├──────────────────────────────────────────────────────────┤
│                  Schemas (Pydantic Models)                  │
│  request.py | response.py                                  │
├──────────────────────────────────────────────────────────┤
│                  Config                                     │
│  config.py (pydantic Settings → .env)                      │
└──────────────────────────────────────────────────────────┘
```

### 3.3 CrewAI 6-Agent Pipeline

ระบบใช้ `Process.sequential` — แต่ละ agent ต้องใช้ context จาก agent ก่อนหน้า:

```
User Message
  │
  ▼
┌─────────────────────────────────────────┐
│ Agent 1: Request Interpreter            │
│ • แปลความคำขอ → structured JSON        │
│ • Output: topics, geography, time_range │
│ • Tools: ไม่มี (LLM only)              │
└───────┬──────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│ Agent 2: Data Retrieval Specialist      │
│ • ค้นข้อมูลจาก Document RAG + DB       │
│ • Tools (10):                           │
│   search_documents, get_indicator_catalog│
│   get_geography_profile,                │
│   get_province_year_summary,            │
│   get_province_roads,                   │
│   get_all_provinces_ranking,            │
│   get_accident_summary,                 │
│   get_accident_hotspots,                │
│   get_accident_time_distribution,       │
│   get_road_condition_risk               │
└───────┬──────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│ Agent 3: SQL Database Specialist        │
│ • เขียน/รัน custom SQL query           │
│ • Safety: SELECT/WITH only, LIMIT 1000 │
│ • Full schema knowledge ฝังใน prompt    │
│ • Tools (2):                            │
│   execute_custom_sql, explain_schema    │
└───────┬──────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│ Agent 4: Accident Data Analyst          │
│ • วิเคราะห์ข้อมูล สังเคราะห์ findings  │
│ • Output: key_findings, trends,         │
│   risk_areas, recommended_actions       │
│ • Tools: ไม่มี (ใช้ context)            │
└───────┬──────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│ Agent 5: Report Chart Builder           │
│ • สร้าง ChartSpec JSON สำหรับ Chart.js  │
│ • Tools (7):                            │
│   build_province_year_trend_chart,      │
│   build_province_roads_bar_chart,       │
│   build_accident_trend_chart,           │
│   build_hotspot_bar_chart,              │
│   build_time_distribution_chart,        │
│   build_road_condition_pie_chart,       │
│   build_monthly_death_bar_chart         │
└───────┬──────────────────────────┘
        ▼
┌─────────────────────────────────────────┐
│ Agent 6: Health Report Writer           │
│ • เรียบเรียงรายงานภาษาไทย Markdown     │
│ • โครงสร้าง:                            │
│   สรุปสาระสำคัญ → สถานการณ์ปัจจุบัน →  │
│   ข้อค้นพบ → พื้นที่/กลุ่มเสี่ยง →     │
│   ข้อเสนอเชิงมาตรการ → ข้อจำกัด →      │
│   คำถามติดตาม 3 ข้อ                    │
│ • Tools: ไม่มี (ใช้ context)            │
└───────┬──────────────────────────┘
        ▼
AgentResponse {content, charts, tables, citations, follow_ups, metadata}
```

### 3.4 RAG Architecture

#### Document RAG (pgvector — PostgreSQL Native)
```
MinIO (uploads bucket)
  │ POST /api/ingest
  ▼
Document Extraction
  ├── PDF → PyMuPDF (fitz)
  ├── DOCX → python-docx
  └── TXT/MD → direct read
  │
  ▼
Text Chunking (langchain-text-splitters)
  │ chunk_size=1000, overlap=200
  ▼
pgvector Vector Store (PostgreSQL chat-aio)
  │ Table: document_embeddings (vector(3072))
  │ Embedding: Google Gemini gemini-embedding-001 (API — ไม่ต้องดาวน์โหลด model)
  ▼
search_documents(query, top_k=5) → relevant chunks (cosine similarity)
```

#### Database RAG (PostgreSQL Star Schema)
```
Raw CSV Data (2020-2026)
  │ import_csv_all_years.py
  ▼
Fact Tables (fact_accident_event, fact_accident_person)
  │
  ▼
Mart Tables (pre-aggregated)
  ├── mart_accident_summary (monthly)
  ├── mart_accident_hotspot (risk scores)
  ├── mart_province_year (province yearly)
  └── mart_province_road (province road yearly)
  │
  ▼
Agent Tools query marts via query_db() → JSON response
```

### 3.5 Connection Pool Strategy

| Pool | Library | Min-Max | ใช้สำหรับ |
|------|---------|---------|-----------|
| **Async Pool** | asyncpg | 2-10 | FastAPI async endpoints (health, ingest) |
| **Sync Pool** | psycopg2 (ThreadedConnectionPool) | 1-5 | CrewAI agent tools (query_db) |

> **เหตุผล**: CrewAI tools ทำงาน synchronous จึงใช้ psycopg2 แยกจาก FastAPI async endpoints

### 3.6 Directory Structure

```
Agent/
├── src/                            # Main application source code
│   ├── main.py                     # FastAPI entrypoint, lifespan, CORS, routers
│   ├── config.py                   # Pydantic Settings (env-based config)
│   ├── agents/                     # CrewAI agent definitions
│   │   ├── orchestrator.py         # Crew builder, run_chat(), result parsing
│   │   ├── request_interpreter.py  # ตีความคำขอผู้ใช้ → structured JSON
│   │   ├── retrieval.py            # ค้นข้อมูลจาก Document RAG + DB tools
│   │   ├── sql_specialist.py       # เขียน/รัน custom SQL (schema-aware)
│   │   ├── analyst_accident.py     # วิเคราะห์ข้อมูลอุบัติเหตุ
│   │   ├── chart_builder.py        # สร้าง ChartSpec JSON สำหรับ frontend
│   │   └── report_writer.py        # เขียนรายงานภาษาไทย Markdown
│   ├── tools/                      # CrewAI tool functions (@tool decorator)
│   │   ├── accident.py             # 7 accident data query tools
│   │   ├── chart_builder.py        # 7 chart-building tools
│   │   ├── common.py               # search_documents, get_indicator_catalog, etc.
│   │   └── sql_tools.py            # execute_custom_sql, explain_schema
│   ├── routers/                    # FastAPI route handlers
│   │   ├── chat.py                 # POST /api/chat, POST /api/chat/stream
│   │   ├── health.py               # GET /api/health
│   │   ├── ingest.py               # POST /api/ingest
│   │   └── test_ui.py              # Test UI routes
│   ├── schemas/                    # Pydantic request/response models
│   │   ├── request.py              # ChatRequest, ReportRequest
│   │   └── response.py             # AgentResponse, ChartSpec, TableSpec, Citation
│   ├── rag/                        # RAG layer
│   │   ├── document_rag.py         # PDF/DOCX extraction, chunking, ingestion, search
│   │   ├── vector_store.py         # pgvector client (psycopg2 + Gemini embeddings), add/search documents
│   │   └── database_rag.py         # PostgreSQL query helpers
│   └── db/                         # Database connectivity
│       ├── pool.py                 # Async (asyncpg) + Sync (psycopg2) pools
│       └── minio_client.py         # MinIO client for document storage
├── database/                       # SQL migrations + data import scripts
│   ├── 001_shared_core.sql         # dim_geography, dim_time, dim_source, etc.
│   ├── 002_document_rag.sql        # document_registry, indicator_catalog (document_chunks dropped in 014)
│   ├── 003_accident_domain.sql     # fact_accident_event, fact_accident_person, marts
│   ├── 004-009_*.sql               # Enhancement migrations
│   ├── 011_pgvector.sql            # pgvector extension + document_embeddings table (vector(3072))
│   ├── import_csv_all_years.py     # CSV import script
│   └── accident20XX.csv            # Raw accident CSV data
├── doc/                            # Documentation
├── tests/                          # pytest test suite
├── static/                         # Static files (test UI HTML)
├── pyproject.toml                  # Dependencies (CrewAI, FastAPI, asyncpg, etc.)
├── docker-compose.yml              # PostgreSQL (pgvector/pgvector:pg16) + MinIO
├── Dockerfile                      # Agent server container
└── .env                            # Environment variables
```

---

## 4. สถาปัตยกรรมเป้าหมาย (Phase 2 — ย้ายจาก Chat-)

### 4.1 ภาพรวมการเปลี่ยนแปลง

```
┌──────────────────────────────────────────────────────────────────┐
│                    Agent Backend (Phase 2)                         │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    FastAPI Routers                            │ │
│  │                                                              │ │
│  │  ★ chat.py          — Agent Pipeline (existing)              │ │
│  │  ★ health.py        — Health check (existing)                │ │
│  │  ★ ingest.py        — Document ingestion (existing)          │ │
│  │  ★ ai_utils.py      — Tool detect, API plan, file select    │ │← ย้ายจาก Chat-
│  │  ★ domain.py        — NL→SQL queries (accident/diabetes/..)  │ │← ย้ายจาก Chat-
│  │  ★ document.py      — APA extract, bulk APA                  │ │← ย้ายจาก Chat-
│  │  ★ external.py      — Weather, ThaiJO                        │ │← ย้ายจาก Chat-
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Business Logic                             │ │
│  │                                                              │ │
│  │  agents/orchestrator.py  — CrewAI pipeline (existing)        │ │
│  │  services/               — ★ New service layer               │ │
│  │    ├── ai_service.py     — Tool detect, plan, SQL gen        │ │← ย้ายจาก Chat- GeminiAIService
│  │    ├── domain_service.py — NL→SQL query execution            │ │← ย้ายจาก Chat- PgDomainRepository
│  │    ├── weather_service.py— Open-Meteo adapter                │ │← ย้ายจาก Chat- OpenMeteoAdapter
│  │    └── journal_service.py— ThaiJO adapter                    │ │← ย้ายจาก Chat- ThaiJOAdapter
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                    Prompts Layer                               │ │
│  │  src/prompts/            — ★ 12 prompt templates (.py)        │ │← ย้ายจาก Chat- .js prompts
│  │    ├── prompt_chat.py                                         │ │
│  │    ├── prompt_plan.py                                         │ │
│  │    ├── prompt_chart.py                                        │ │
│  │    ├── prompt_deep_research.py                                │ │
│  │    └── ... (12 total)                                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 API Design (Phase 2 — ใหม่)

#### AI Utility APIs (ย้ายจาก Chat- client-side)

```
POST /api/ai/detect-tool
  Request:  {"text": "สร้างกราฟอุบัติเหตุเชียงใหม่"}
  Response: {"tool": "สร้างกราฟ"}
  ← เดิม: ChatInterface.tsx → aiDetectTool() (client-side Gemini Flash)

POST /api/ai/plan-apis
  Request:  {"text": "สถิติอุบัติเหตุเชียงใหม่กับพยากรณ์อากาศ"}
  Response: {"useAccident": true, "accidentMessage": "...", "useWeather": true, ...}
  ← เดิม: ChatInterface.tsx → aiPlanAdminApiCalls() (client-side)

POST /api/ai/select-files
  Request:  {"text": "สรุปงานวิจัยอุบัติเหตุ", "fileMetadata": [...]}
  Response: {"selectedFiles": ["accident_study.pdf", "report_2025.docx"]}
  ← เดิม: ChatInterface.tsx → searchRelevantFiles() (client-side)

POST /api/ai/generate-sql
  Request:  {"schema": "...", "question": "จำนวนอุบัติเหตุเชียงใหม่ปี 2025", "table": "accident"}
  Response: {"sql": "SELECT COUNT(*) FROM accident WHERE ..."}
  ← เดิม: GeminiAIService.generateSQL() (ChatV1 server-side)

POST /api/ai/summarize
  Request:  {"prompt": "สรุปข้อมูลพยากรณ์อากาศ", "context": "..."}
  Response: {"text": "สรุป: ..."}
  ← เดิม: GeminiAIService.summarize() (ChatV1)
```

#### Domain Query APIs (ย้ายจาก Chat- admin APIs)

```
POST /api/domain/accident
  Request:  {"message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025"}
  Response: {"sql": "SELECT ...", "reply": "สรุป...", "total": 120, "rows": [...], "chart": {...}}
  ← เดิม: Chat-/app/api/admin/accident/route.ts
  ★ ปรับปรุง: ใช้ mart tables + readonly pool + optional ChartSpec

POST /api/domain/diabetes
  Request:  {"message": "ผลงานเบาหวานรายจังหวัด"}
  Response: {"sql": "SELECT ...", "reply": "สรุป...", "total": 50, "rows": [...]}
  ← เดิม: Chat-/app/api/admin/diabetes/route.ts

POST /api/domain/mental
  Request:  {"message": "ข้อมูลสุขภาพจิตรายอำเภอ", "table": "bipola"}
  Response: {"sql": "SELECT ...", "reply": "สรุป...", "total": 30, "rows": [...]}
  ← เดิม: Chat-/app/api/admin/mental/route.ts (dynamic table detection)

POST /api/domain/query
  Request:  {"table": "accident", "page": 1, "pageSize": 50, "search": "เชียงใหม่"}
  Response: {"rows": [...], "columns": [...], "total": 1200}
  ← เดิม: Chat-/app/api/admin/db-table/route.ts

POST /api/domain/csv-import
  Request:  FormData {file, tableName, mode: "append"|"replace"}
  Response: {"inserted": 500, "skipped": 3, "errors": [...]}
  ← เดิม: Chat-/app/api/admin/csv-import/route.ts
```

#### Document APIs (ย้ายจาก Chat- file APIs)

```
POST /api/document/extract-apa
  Request:  {"fileName": "report.pdf", "filePath": "/folder1/"}
  Response: {"apaJson": {"abstract": "...", "keywords": {...}, ...}}
  ← เดิม: Chat-/app/api/files/apa/route.ts

POST /api/document/extract-apa/bulk
  Request:  {"files": [{"fileName": "a.pdf", "filePath": "/"}, ...]}
  Response: {"results": [...], "errors": [...]}
  ← เดิม: Chat-/app/api/files/apa/bulk (concurrency ≤ 8)
```

#### External Integration APIs (ย้ายจาก Chat-)

```
GET /api/external/weather?lat=13.75&lon=100.5&days=7
  Response: {"forecasts": [{"date": "...", "temp_max": 35, ...}]}
  ← เดิม: Chat-/app/api/weather/route.ts (Open-Meteo)

POST /api/external/thaijo
  Request:  {"term": "อุบัติเหตุทางถนน", "size": 10}
  Response: {"articles": [...]}
  ← เดิม: Chat-/app/api/admin/thaijo/route.ts
```

### 4.3 Phase 2 Directory Structure (เป้าหมาย)

```
Agent/src/
├── main.py
├── config.py
├── agents/                     # CrewAI agents (existing)
│   ├── orchestrator.py
│   ├── request_interpreter.py
│   ├── retrieval.py
│   ├── sql_specialist.py
│   ├── analyst_accident.py
│   ├── chart_builder.py
│   └── report_writer.py
├── tools/                      # CrewAI tools (existing)
│   ├── accident.py
│   ├── chart_builder.py
│   ├── common.py
│   └── sql_tools.py
├── routers/                    # FastAPI routes
│   ├── chat.py                 # (existing) Agent pipeline
│   ├── health.py               # (existing) Health check
│   ├── ingest.py               # (existing) Document ingestion
│   ├── test_ui.py              # (existing) Test UI
│   ├── ai_utils.py             # ★ NEW: Tool detect, API plan, file select, SQL gen
│   ├── domain.py               # ★ NEW: NL→SQL queries, table CRUD, CSV import
│   ├── document.py             # ★ NEW: APA extraction, bulk APA
│   └── external.py             # ★ NEW: Weather, ThaiJO
├── services/                   # ★ NEW: Business logic services
│   ├── ai_service.py           # Gemini interactions (detect, plan, SQL gen, APA)
│   ├── domain_service.py       # NL→SQL execution, table operations
│   ├── weather_service.py      # Open-Meteo adapter
│   └── journal_service.py      # ThaiJO adapter
├── prompts/                    # ★ NEW: Prompt templates (ย้ายจาก Chat- .js)
│   ├── prompt_chat.py
│   ├── prompt_plan.py
│   ├── prompt_search.py
│   ├── prompt_summary.py
│   ├── prompt_consult.py
│   ├── prompt_compare.py
│   ├── prompt_chart.py
│   ├── prompt_article.py
│   ├── prompt_disease_surveillance.py
│   ├── prompt_situation.py
│   ├── prompt_deep_research.py
│   └── prompt_step_read.py
├── schemas/                    # Pydantic models
│   ├── request.py              # (existing)
│   ├── response.py             # (existing)
│   ├── ai_schemas.py           # ★ NEW: DetectToolRequest/Response, etc.
│   └── domain_schemas.py       # ★ NEW: DomainQueryRequest/Response, etc.
├── rag/                        # RAG layer (existing)
├── db/                         # Database connectivity (existing)
└── __init__.py
```

---

## 5. Chat- Architecture (Reference — ความสามารถที่ต้องย้าย)

### 5.1 Chat- Message Flow (ปัจจุบัน)

```
User types message
       │
       ▼
┌──────────────────────────────────────┐
│     ChatInterface.handleSend()       │
│     (2,171 lines — inline logic)     │
│                                      │
│  1. aiDetectTool(text)              │  ← ★ ย้ายไป Agent /api/ai/detect-tool
│     → "เขียนแผนงาน" | "สร้างกราฟ"  │
│     → null (normal chat)            │
│                                      │
│  2. aiPlanAdminApiCalls(text)       │  ← ★ ย้ายไป Agent /api/ai/plan-apis
│     → [{endpoint, payload}, ...]    │
│                                      │
│  3. runPlannedAdminApis(plans)      │  ← ★ Agent ทำเองได้ (มี DB access)
│     → context string               │
│                                      │
│  4. searchRelevantFiles(text)       │  ← ★ ย้ายไป Agent /api/ai/select-files
│     → file metadata array           │
│                                      │
│  5. Build final prompt:             │  ← ★ ย้ายไป Agent /api/ai/chat
│     PROMPT_* + context + files      │
│                                      │
│  6. Fetch Gemini Pro (SSE)          │  ← ★ Agent เรียก Gemini (server-side)
│     → Stream text chunks            │
│                                      │
│  7. Post-process response           │  ← ยังอยู่ frontend (parse charts/tables)
│                                      │
│  8. Save to session                 │  ← ยังอยู่ frontend (save to DB/localStorage)
└──────────────────────────────────────┘
```

### 5.2 Chat- Prompt System (12 Templates)

| File | Export | จุดประสงค์ | Agent Target |
|------|--------|-----------|-------------|
| `promptchat.js` | PROMPT_CHAT | สนทนาทั่วไป | `prompt_chat.py` |
| `promptplan.js` | PROMPT_PLAN | เขียนแผนงานสุขภาพ | `prompt_plan.py` |
| `promptsearch.js` | PROMPT_SEARCH | ค้นหาข้อมูล | `prompt_search.py` |
| `promptsummary.js` | PROMPT_SUMMARY | สรุปเอกสาร | `prompt_summary.py` |
| `promptconsult.js` | PROMPT_CONSULT | ปรึกษาผู้เชี่ยวชาญ | `prompt_consult.py` |
| `promptcompare.js` | PROMPT_COMPARE | เปรียบเทียบข้อมูล | `prompt_compare.py` |
| `promptchart_doc.js` | PROMPT_CHART_DOC | สร้างกราฟจากเอกสาร | `prompt_chart.py` |
| `prompta.js` | PROMPT_A | Article template | `prompt_article.py` |
| `promptb.js` | PROMPT_B | Disease surveillance | `prompt_disease_surveillance.py` |
| `promptc.js` | PROMPT_C | Situation report | `prompt_situation.py` |
| `promptdeepresearch.js` | PROMPT_DEEPRESEARCH | Deep research | `prompt_deep_research.py` |
| `promptstepRead.js` | PROMPT_STEP_READ | Step-by-step reading | `prompt_step_read.py` |

### 5.3 Chat- Admin APIs (ต้องย้าย)

| Chat- Endpoint | Agent Target | ข้อดีที่ได้ |
|----------------|-------------|------------|
| `POST /api/admin/accident` | `POST /api/domain/accident` | ใช้ mart tables + readonly pool |
| `POST /api/admin/diabetes` | `POST /api/domain/diabetes` | readonly pool |
| `POST /api/admin/mental` | `POST /api/domain/mental` | readonly pool |
| `GET/POST /api/admin/db-table` | `POST /api/domain/query` | readonly pool |
| `POST /api/admin/csv-import` | `POST /api/domain/csv-import` | centralized |
| `POST /api/admin/thaijo` | `POST /api/external/thaijo` | centralized |
| `POST /api/admin/chatweather` | `GET /api/external/weather` | centralized |
| `POST /api/files/apa` | `POST /api/document/extract-apa` | centralized |

---

## 6. Infrastructure & Deployment

### 6.1 Docker Compose

```
Agent Docker Compose (docker-compose.yml):
┌──────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  agent   │  │ postgres │  │ minio  │ │
│  │ FastAPI  │  │  PG 16   │  │ MinIO  │ │
│  │  :8000   │  │  :5432   │  │ :9000  │ │
│  └──────────┘  └──────────┘  └────────┘ │
│  + pgvector (extension inside postgres container)  │
└──────────────────────────────────────────┘
```

### 6.2 Shared Database Strategy

ทั้ง 3 components ใช้ database `chat-aio` เดียวกัน:

| กลุ่มตาราง | เจ้าของ | ตัวอย่างตาราง |
|------------|---------|--------------|
| **Application** | Chat-/ChatV1 | users, chat_sessions, chat_messages, planning_history, file_apa_metadata |
| **Dimension** | Agent | dim_geography, dim_time, dim_road_segment, dim_source |
| **Fact** | Agent | fact_accident_event, fact_accident_person |
| **Mart** | Agent | mart_accident_summary, mart_province_year, mart_province_road |
| **Document RAG** | Agent | document_registry, document_embeddings, indicator_catalog |
| **Domain Data** | Chat- (CSV import) | accident, diabetes, bipola |

> **ข้อสังเกต**: ตาราง `accident` (Thai columns, raw CSV) ใน Chat- กับ `fact_accident_event` (normalized star schema) ใน Agent เป็นข้อมูลคนละ format

### 6.3 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `chat-aio` | Database name (shared) |
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
| `EMBEDDING_MODEL` | `models/gemini-embedding-001` | Gemini embedding model (3072-dim, API-based) |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `info` | Logging level |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |

---

## 7. Cross-Cutting Concerns

### 7.1 Security

| ด้าน | Agent (ปัจจุบัน) | Agent (Phase 2 เป้าหมาย) | Chat- (reference) |
|------|-----------------|------------------------|-------------------|
| **API Key** | ✅ Server-side only | ✅ Server-side only | ⚠️ Client-side exposed |
| **SQL Safety** | ✅ SELECT/WITH + LIMIT 1000 | ✅ + readonly pool | ⚠️ ไม่ validate |
| **CORS** | ✅ Configurable origins | ✅ | N/A |
| **Request Validation** | ✅ Pydantic models | ✅ | Manual validation |
| **Auth** | ❌ (ใช้ CORS) | ✅ API key / token header | Base64 token |

### 7.2 Error Handling

Agent ใช้ JSON response พร้อม HTTP status codes:
- `400` Bad Request — ข้อมูลไม่ครบ
- `404` Not Found
- `500` Internal Server Error
- `503` Service Unavailable — external API timeout / DB down

> **ภาษา**: Error messages เป็นภาษาไทย (เช่น "กรุณาระบุข้อความ")

### 7.3 Thai Localization
- Agent prompts ทั้งหมดเป็นภาษาไทย
- Report output เป็นภาษาไทย Markdown
- ชื่อคอลัมน์ใน accident table เป็นภาษาไทย (ต้อง double-quote ใน SQL)
- ChartSpec labels เป็นภาษาไทย

---

## 8. Technology Decisions

### 8.1 ทำไมเลือก CrewAI (Sequential Process)
CrewAI ใช้ `Process.sequential` เพราะแต่ละ agent ต้องพึ่ง context จาก agent ก่อนหน้า:
- Request Interpreter ตีความก่อน → Retrieval ค้นตาม topics → SQL ถาม custom query → Analyst วิเคราะห์ → Chart สร้างกราฟ → Writer เขียนรายงาน

### 8.2 ทำไมใช้ `.replace()` แทน `.format()` ใน Prompt Templates
Prompt templates มี JSON curly braces (`{...}`) ซึ่ง conflict กับ Python `.format()` — ใช้ `.replace("{user_message}", ...)` แทน

### 8.3 ทำไมใช้ Shared Database
ใช้ database `chat-aio` เดียวกันเพื่อ:
- Agent สามารถอ่าน domain data จาก Chat- ได้ (accident, diabetes, bipola tables)
- ลดการ duplicate ข้อมูล
- dim tables ใช้ร่วมกันข้าม domains

### 8.4 ทำไมย้ายจาก Chat- client-side มา Agent
1. **Security**: Chat- เรียก Gemini API โดยตรงจาก browser → API key expose ใน DevTools
2. **Consistency**: รวม AI logic ไว้ที่เดียว ไม่กระจายตาม components
3. **Reusability**: ทุก frontend (Chat-, ChatV1, Mobile app อนาคต) ใช้ Agent API เดียวกัน
4. **Safety**: Agent มี readonly pool + SQL validation ที่ Chat- ไม่มี
5. **Maintainability**: prompts, tools, services จัดการที่ backend → deploy ครั้งเดียว ทุก frontend ได้ประโยชน์

### 8.5 ทำไม ChartSpec Contract
Agent สร้าง `ChartSpec` JSON ที่ map 1:1 กับ `ChartRenderer.tsx` ใน frontend:
```json
{
  "type": "line|bar|pie|doughnut",
  "title": "ชื่อกราฟ",
  "data": { "labels": [...], "datasets": [...] },
  "options": {},
  "source_note": "mart_province_year"
}
```

---

## 9. Known Issues & Technical Debt

| ปัญหา | ระดับ | แนวทางแก้ไข |
|--------|-------|-------------|
| Chat- เรียก Gemini จาก client-side | 🔴 Critical | Phase 2: ย้ายมา Agent API |
| Chat- admin APIs ไม่มี readonly pool | 🟠 High | Phase 2: ย้ายมา Agent ที่มี readonly pool |
| 12 prompts อยู่ใน Chat- (.js) | 🟡 Medium | Phase 2: ย้ายมา Agent (.py) |
| ไม่มี rate limiting | 🟡 Medium | เพิ่ม FastAPI rate limiter |
| ไม่มี API authentication | 🟡 Medium | เพิ่ม API key / token validation |
| ไม่มี request logging / tracing | 🟡 Medium | เพิ่ม structured logging + OpenTelemetry |
| pgvector (vector data ใน PostgreSQL) ไม่มี backup strategy แยก | 🟡 Medium | ใช้ PostgreSQL backup ครอบคลุม (pg_dump รวม `document_embeddings` อัตโนมัติ) |

---

## 10. ภาคผนวก

### A. Chat Request End-to-End Sequence (Agent Mode)

```
Browser                Chat-/ChatV1         Agent Backend        PostgreSQL     pgvector
  │                      │                      │                    │              │
  │  User sends message  │                      │                    │              │
  ├─────────────────────►│                      │                    │              │
  │                      │  POST /api/chat      │                    │              │
  │                      ├─────────────────────►│                    │              │
  │                      │                      │  search_documents  │              │
  │                      │                      ├──────────────────────────────────►│
  │                      │                      │◄───────────────────────────────────┤
  │                      │                      │  query_db(SQL)     │              │
  │                      │                      ├───────────────────►│              │
  │                      │                      │◄───────────────────┤              │
  │                      │                      │  (repeat per agent)│              │
  │                      │◄─────────────────────┤                    │              │
  │                      │  AgentResponse JSON   │                    │              │
  │  render charts,      │                      │                    │              │
  │  tables, content     │                      │                    │              │
  │◄─────────────────────┤                      │                    │              │
```

### B. AgentResponse Schema

```json
{
  "content": "## สรุปสาระสำคัญ\n...(Markdown ภาษาไทย)",
  "topic": "accident",
  "charts": [
    {
      "type": "line",
      "title": "แนวโน้มอุบัติเหตุจังหวัดเชียงใหม่",
      "data": {
        "labels": ["2020", "2021", "2022", "2023", "2024", "2025"],
        "datasets": [
          {"label": "อุบัติเหตุ", "data": [1200, 1150, 1100, 1050, 980, 920]},
          {"label": "เสียชีวิต", "data": [45, 42, 38, 35, 30, 28]}
        ]
      },
      "options": {},
      "source_note": "mart_province_year"
    }
  ],
  "tables": [
    {"title": "สรุปรายจังหวัด", "headers": ["จังหวัด","อุบัติเหตุ","เสียชีวิต"], "rows": [["เชียงใหม่",920,28]]}
  ],
  "citations": [{"title": "รายงานอุบัติเหตุ 2025", "source": "กรมทางหลวง", "page": "12"}],
  "follow_ups": ["จังหวัดไหนมีอัตราเสียชีวิตสูงสุด?", "เปรียบเทียบช่วงเทศกาลกับช่วงปกติ"],
  "metadata": {"elapsed_seconds": 45.2, "agent_count": 6, "chart_count": 1}
}
```

### C. เอกสารอ้างอิง

| เอกสาร | ตำแหน่ง | เนื้อหา |
|--------|---------|---------|
| Agent SRS | `Agent/doc/SRS.md` | ข้อกำหนดความต้องการ |
| Agent Database & API | `Agent/doc/DATABASE_API.md` | ฐานข้อมูลและ API reference |
| Agent Project Docs | `Agent/doc/PROJECT_DOCUMENTATION.md` | เอกสารโปรเจกต์ |
| Agent RAG Design | `Agent/doc/Agentic_AI_RAG_Design.md` | RAG system design |
| Agent SQL Specialist | `Agent/doc/SQL_SPECIALIST_AGENT.md` | SQL agent documentation |
| Chat- SRS | `Chat-/doc/SRS.md` | SRS ของระบบรวม |
| Chat- Architecture | `Chat-/doc/ARCHITECTURE.md` | สถาปัตยกรรมรวมทั้งระบบ |
| Chat- Database & API | `Chat-/doc/DATABASE_API.md` | DB + API reference (Chat-) |
