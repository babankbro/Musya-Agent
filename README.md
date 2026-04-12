# Musya Agent — Agentic AI + RAG Backend

CrewAI-based backend for generating health plan documents using AI agents and RAG (Retrieval-Augmented Generation).

## Architecture

```
ChatV1 (Next.js :3000) → Agent (FastAPI :8000) → CrewAI Agents
                                                    ├── Document RAG (ChromaDB + MinIO)
                                                    └── Database RAG (PostgreSQL marts)
```

## Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 16 (from ChatV1 docker-compose)
- MinIO (from ChatV1 docker-compose)
- Google Gemini API key

### 2. Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Copy and edit env
copy .env.example .env
# Edit .env and set GEMINI_API_KEY
```

### 3. Run Database Migrations

Make sure PostgreSQL is running (via ChatV1's docker-compose), then:

```bash
# Run shared core schema
psql -h localhost -U postgres -d chat-aio -f database/001_shared_core.sql
psql -h localhost -U postgres -d chat-aio -f database/002_document_rag.sql
psql -h localhost -U postgres -d chat-aio -f database/003_accident_domain.sql
```

### 4. Start the Server

```bash
python -m src.main
# or
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Ingest Documents

```bash
curl -X POST http://localhost:8000/api/ingest
```

### 6. Test Chat

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "สรุปสถานการณ์อุบัติเหตุ"}'
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (DB, MinIO, ChromaDB) |
| POST | `/api/chat` | Chat with agent (JSON response) |
| POST | `/api/chat/stream` | Chat with SSE streaming |
| POST | `/api/ingest` | Ingest documents from MinIO |
| GET | `/docs` | Swagger UI |

## Project Structure

```
Agent/
├── src/
│   ├── main.py              # FastAPI app
│   ├── config.py             # Settings from env
│   ├── db/                   # Database & MinIO clients
│   ├── rag/                  # RAG pipeline (document + database)
│   ├── agents/               # CrewAI agents
│   ├── tools/                # Agent tools (domain-specific)
│   ├── schemas/              # Pydantic models
│   └── routers/              # FastAPI routes
├── database/                 # SQL migrations
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Viewing Agent Logs & Debugging

### Option 1: Run Backend Directly (Recommended for Development)

**Windows:**
```bash
run_server.bat
```

**Or manually:**
```bash
cd d:\work\musya\Agent
.venv\Scripts\activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Linux/Mac:**
```bash
cd /path/to/Agent
source .venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The terminal will show:
- ✅ Each agent's task execution
- ✅ Tool calls with parameters
- ✅ Tool results and observations
- ✅ Agent reasoning steps
- ✅ Final responses in formatted boxes

### Option 2: Run with Docker and View Logs

**Start container:**
```bash
docker-compose -f docker-compose.agent.yml up --build
```

**View live logs:**
```bash
docker logs -f musya-agent
```

**View logs from specific time:**
```bash
docker logs --since 5m musya-agent
```

### Option 3: Enable Enhanced Tracing

Add to `.env` file:
```bash
# Enhanced CrewAI tracing
CREWAI_TRACING_ENABLED=true
LOG_LEVEL=debug

# Optional: LangChain verbose mode
LANGCHAIN_VERBOSE=true
```

Then restart the server to see even more detailed agent execution traces.

### What You'll See in Logs

When a chat request is processed, you'll see output like:

```
2026-04-06 16:39:57 [INFO] src.agents.orchestrator: Starting crew for message: สรุปอุบัติเหตุ...

# Agent: Request Interpreter
[2026-04-06 16:40:01][DEBUG]: == Working Agent: นักตีความคำขอ
[2026-04-06 16:40:01][INFO]: == Starting Task: วิเคราะห์คำขอของผู้ใช้...
> Entering new CrewAgentExecutor chain...
Thought: ผู้ใช้ต้องการสรุปข้อมูลอุบัติเหตุ...
Action: search_documents
Action Input: {"topic": "accident", "keywords": "สรุปอุบัติเหตุ"}
Observation: [Document results...]
Final Answer: {"topics": ["accident"], "geography": "", ...}

# Agent: Retrieval Specialist
[2026-04-06 16:40:15][DEBUG]: == Working Agent: ผู้เชี่ยวชาญด้านการค้นหาข้อมูล
Action: get_accident_summary
Action Input: {"start_date": "", "end_date": ""}
Observation: สรุปข้อมูลอุบัติเหตุ: 2024/01: อุบัติเหตุ 45 ครั้ง...

# Agent: Accident Analyst
[2026-04-06 16:40:30][DEBUG]: == Working Agent: นักวิเคราะห์อุบัติเหตุ
Thought: วิเคราะห์แนวโน้มและปัจจัยเสี่ยง...

# Agent: Report Writer
[2026-04-06 16:40:45][DEBUG]: == Working Agent: นักเขียนรายงาน
Final Answer: [Formatted Thai report in markdown]

[2026-04-06 16:40:50][INFO] src.agents.orchestrator: Crew completed in 53.2s
```

### Test UI with Live Logs

1. Start the backend: `run_server.bat`
2. Open Test UI: http://localhost:8000/test
3. Send a chat message in the UI
4. Watch the terminal to see all agent execution steps in real-time

## Testing

Run the test suite:
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_tools.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Development Phases

- **Phase 1** ✅ (completed): Accident domain + basic pipeline + mockup data + tests + test UI
- **Phase 2**: + Mental Health domain + Citation system
- **Phase 3**: + Nutrition domain + General chat + DOCX export
