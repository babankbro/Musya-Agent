# Musya Agent — Project Documentation

> **Version**: 0.1.0  
> **Last Updated**: 2026-04-13  
> **Stack**: Python 3.12 · FastAPI · CrewAI · PostgreSQL · ChromaDB · MinIO · Google Gemini

---

## 1. Project Overview

**Musya Agent** เป็น backend สำหรับระบบ Agentic AI + RAG (Retrieval-Augmented Generation) ที่ออกแบบมาเพื่อวิเคราะห์ข้อมูลสุขภาพสาธารณะ โดยเฉพาะข้อมูลอุบัติเหตุทางถนนของประเทศไทย ระบบใช้ CrewAI ในการจัดการ multi-agent pipeline ที่ทำงานร่วมกันตั้งแต่การตีความคำขอ ค้นหาข้อมูล วิเคราะห์ สร้างกราฟ จนถึงเขียนรายงาน

### Key Features
- **Multi-Agent Pipeline**: 6 agents ทำงานแบบ sequential ด้วย CrewAI
- **Dual RAG**: Document RAG (ChromaDB) + Database RAG (PostgreSQL)
- **SQL Specialist**: เขียนและรัน custom SQL query ได้อัตโนมัติ
- **Chart Builder**: สร้าง Chart.js-compatible JSON สำหรับ frontend
- **Thai-Language Reports**: รายงานภาษาไทยในรูปแบบ Markdown
- **REST API**: FastAPI server ที่รองรับทั้ง sync และ SSE streaming

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
│  │(chat,    │  │  or      │  │(6 total)│  │(DB/RAG) │  │
│  │health,..)│  │(CrewAI)  │  │         │  │         │  │
│  └──────────┘  └──────────┘  └─────────┘  └─────────┘  │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │PostgreSQL│  │ ChromaDB │  │       MinIO          │   │
│  │(data)    │  │(vectors) │  │   (documents)        │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Message
  → POST /api/chat
    → Orchestrator.run_chat()
      → Task 1: Request Interpreter    (ตีความคำขอ → JSON)
      → Task 2: Retrieval Agent        (ค้นข้อมูลจาก DB + Documents)
      → Task 3: SQL Specialist          (เขียน/รัน custom SQL)
      → Task 4: Accident Analyst        (วิเคราะห์ข้อมูล)
      → Task 5: Chart Builder           (สร้าง ChartSpec JSON)
      → Task 6: Report Writer           (เขียนรายงานภาษาไทย)
    → AgentResponse (content, charts, tables, citations, follow_ups)
```

---

## 3. Directory Structure

```
Agent/
├── src/                        # Main application source code
│   ├── main.py                 # FastAPI entrypoint, lifespan, CORS, routers
│   ├── config.py               # Pydantic Settings (env-based config)
│   ├── agents/                 # CrewAI agent definitions
│   │   ├── orchestrator.py     # Crew builder, run_chat(), result parsing
│   │   ├── request_interpreter.py  # ตีความคำขอผู้ใช้ → structured JSON
│   │   ├── retrieval.py        # ค้นข้อมูลจาก Document RAG + DB tools
│   │   ├── sql_specialist.py   # เขียน/รัน custom SQL (schema-aware)
│   │   ├── analyst_accident.py # วิเคราะห์ข้อมูลอุบัติเหตุ
│   │   ├── chart_builder.py    # สร้าง ChartSpec JSON สำหรับ frontend
│   │   └── report_writer.py    # เขียนรายงานภาษาไทย Markdown
│   ├── tools/                  # CrewAI tool functions
│   │   ├── accident.py         # 7 accident data tools (province, roads, ranking, etc.)
│   │   ├── chart_builder.py    # 7 chart-building tools (trend, hotspot, pie, etc.)
│   │   ├── common.py           # search_documents, get_indicator_catalog, get_geography_profile
│   │   └── sql_tools.py        # execute_custom_sql, explain_schema, get_table_row_count
│   ├── routers/                # FastAPI route handlers
│   │   ├── chat.py             # POST /api/chat, POST /api/chat/stream (SSE)
│   │   ├── health.py           # GET /api/health (PostgreSQL + MinIO + ChromaDB)
│   │   ├── ingest.py           # POST /api/ingest (document ingestion)
│   │   └── test_ui.py          # Test UI routes
│   ├── schemas/                # Pydantic request/response models
│   │   ├── request.py          # ChatRequest, ReportRequest
│   │   └── response.py         # AgentResponse, ChartSpec, TableSpec, Citation
│   ├── rag/                    # RAG (Retrieval-Augmented Generation) layer
│   │   ├── document_rag.py     # PDF/DOCX extraction, chunking, ingestion, search
│   │   ├── vector_store.py     # ChromaDB client, add/search documents
│   │   └── database_rag.py     # PostgreSQL query helpers
│   └── db/                     # Database connectivity
│       ├── pool.py             # Async (asyncpg) + Sync (psycopg2) connection pools
│       └── minio_client.py     # MinIO client for document storage
├── database/                   # SQL migrations + data import scripts
│   ├── 001_shared_core.sql     # dim_geography, dim_time, dim_source, etc.
│   ├── 002_document_rag.sql    # document_registry, document_chunks, indicator_catalog
│   ├── 003_accident_domain.sql # fact_accident_event, fact_accident_person, mart tables
│   ├── 004_seed_accident_mockup.sql  # Mock data seeding
│   ├── 005–009_*.sql           # Enhancement migrations (roads, province marts, coordinates)
│   ├── import_csv_all_years.py # CSV import script (accident2020–2026.csv)
│   └── accident20XX.csv        # Raw accident CSV data (2020–2026)
├── doc/                        # Documentation
├── tests/                      # Pytest test suite
├── static/                     # Static files (test UI HTML)
├── pyproject.toml              # Project metadata + dependencies
├── docker-compose.yml          # PostgreSQL + MinIO + ChromaDB
├── Dockerfile                  # Agent server container
└── .env                        # Environment variables
```

---

## 4. Agents

### 4.1 Request Interpreter
- **Role**: แปลความคำขอผู้ใช้เป็น structured JSON
- **Output**: `{ topics, geography, time_range, report_type, focus, language }`
- **Tools**: ไม่มี (ใช้ LLM อย่างเดียว)

### 4.2 Data Retrieval Specialist
- **Role**: ค้นหาข้อมูลจาก Document RAG และ Database RAG
- **Tools** (10 tools):
  - `search_documents` — ค้นเอกสารจาก ChromaDB
  - `get_indicator_catalog` — ตัวชี้วัดสุขภาพ
  - `get_geography_profile` — ข้อมูลพื้นที่
  - `get_province_year_summary` — สรุปอุบัติเหตุรายจังหวัดรายปี
  - `get_province_roads` — ถนนเสี่ยงในจังหวัด
  - `get_all_provinces_ranking` — จัดอันดับ 77 จังหวัด
  - `get_accident_summary` — สรุปอุบัติเหตุรายเดือน
  - `get_accident_hotspots` — จุดเสี่ยง top-N
  - `get_accident_time_distribution` — กระจายตามเวลา
  - `get_road_condition_risk` — ความเสี่ยงตามสภาพถนน

### 4.3 SQL Database Specialist
- **Role**: เขียนและรัน custom SQL query
- **Backstory**: มี full schema knowledge ฝังอยู่ใน prompt (fact, dim, mart tables)
- **Tools**:
  - `execute_custom_sql` — รัน read-only SQL (auto LIMIT 1000, SELECT/WITH only)
  - `explain_schema` — ดู schema ของ table

### 4.4 Accident Data Analyst
- **Role**: วิเคราะห์ข้อมูล สังเคราะห์ key_findings, trends, risk_areas, recommended_actions
- **Tools**: ไม่มี (ใช้ context จาก Retrieval + SQL)

### 4.5 Report Chart Builder
- **Role**: สร้าง ChartSpec JSON สำหรับ Chart.js
- **Tools** (7 tools):
  - `build_province_year_trend_chart` — line chart แนวโน้มรายปี
  - `build_province_roads_bar_chart` — bar chart ถนนเสี่ยง
  - `build_accident_trend_chart` — line chart แนวโน้มรายเดือน
  - `build_hotspot_bar_chart` — bar chart จุดเสี่ยง
  - `build_time_distribution_chart` — bar chart ตามชั่วโมง
  - `build_road_condition_pie_chart` — pie chart สภาพถนน
  - `build_monthly_death_bar_chart` — bar chart เสียชีวิตรายเดือน

### 4.6 Health Report Writer
- **Role**: เรียบเรียงรายงานภาษาไทยแบบ Markdown
- **Output Structure**:
  - สรุปสาระสำคัญ → สถานการณ์ปัจจุบัน → ข้อค้นพบ → พื้นที่/กลุ่มเสี่ยง → ข้อเสนอเชิงมาตรการ → ข้อจำกัด → คำถามติดตาม 3 ข้อ

---

## 5. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root — API info + links |
| `GET` | `/api/health` | Health check (PostgreSQL + MinIO + ChromaDB) |
| `POST` | `/api/chat` | Process chat message through agent pipeline → `AgentResponse` |
| `POST` | `/api/chat/stream` | SSE stream version of chat |
| `POST` | `/api/ingest` | Ingest documents from MinIO → ChromaDB |
| `GET` | `/test` | Standalone test UI |
| `GET` | `/docs` | FastAPI auto-generated Swagger docs |

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
  "metadata": { "elapsed_seconds": 45.2, "agent_count": 6, "chart_count": 2 }
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
| **ChromaDB** | Vector store (document embeddings) | `./chroma_data` (local persistent) |
| **Google Gemini** | LLM via litellm (`gemini/gemini-2.0-flash`) | API key required |

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
| `CHROMA_PERSIST_DIR` | `./chroma_data` | ChromaDB storage path |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins |

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
# Run migrations in order
psql -U postgres -d chat-aio -f database/001_shared_core.sql
psql -U postgres -d chat-aio -f database/002_document_rag.sql
psql -U postgres -d chat-aio -f database/003_accident_domain.sql
# ... through 009

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
| `chromadb` | >=0.5 | Vector store |
| `minio` | >=7.2 | Object storage client |
| `google-genai` | >=1.0 | Gemini API (non-deprecated) |
| `langchain-google-genai` | >=2.0 | LangChain Gemini integration |
| `langchain-text-splitters` | >=0.3 | Text chunking |
| `PyMuPDF` | >=1.24 | PDF text extraction |
| `python-docx` | >=1.1 | DOCX text extraction |
| `pydantic` | >=2.8 | Data validation |
| `pydantic-settings` | >=2.5 | Env-based config |
| `sse-starlette` | >=2.1 | Server-Sent Events |
| `python-dotenv` | >=1.0 | .env file loading |
