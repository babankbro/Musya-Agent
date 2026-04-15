# Musya Agent — Unified Workflow Documentation

> รวม Chat Pipeline และ Policy Brief Pipeline ภายใต้ **Shared Foundation Architecture** + ระบบ Routing อัตโนมัติ

> **เวอร์ชัน**: 6.0 (Shared Foundation Pipeline)
> **วันที่**: 2026-04-15
> **ขอบเขต**: Shared Foundation (agents 1-4) + Chat Pipeline (3 specific) + Policy Brief Pipeline (4 specific)

---

## 1. ภาพรวมระบบ (System Overview)

Musya Agent เป็นระบบ **Multi-Agent AI** ที่รวม 2 pipeline ภายใต้ **Request Router Agent**
ทั้ง 2 pipeline ใช้ **Shared Foundation Agents 1-4** ร่วมกัน แตกต่างกันเฉพาะส่วน domain-specific agents

```
User Message
    │
    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    REQUEST ROUTER AGENT                              │
│                                                                     │
│  วิเคราะห์คำขอ → ตัดสินใจ pipeline                                   │
│                                                                     │
│  Output: { pipeline, confidence, reason, extracted_params }          │
│                                                                     │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐    │
│  │  Keywords:           │    │  Keywords:                       │    │
│  │  สถิติ, กราฟ, จุดเสี่ยง │    │  นโยบาย, ตรวจราชการ, policy brief │    │
│  │  แนวโน้ม, อุบัติเหตุ   │    │  เขตสุขภาพ, บทสรุปผู้บริหาร      │    │
│  │  → chat_pipeline     │    │  → policy_brief_pipeline         │    │
│  └──────────┬──────────┘    └──────────────┬────────────────────┘    │
└─────────────┼──────────────────────────────┼────────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SHARED FOUNDATION (Agents 1-4)                         │
│                                                                     │
│  1. Request Interpreter  →  parse intent, extract parameters        │
│  2. Data Retrieval       →  Document RAG + DB (+NLM for policy)     │
│  3. SQL Specialist       →  complex queries, chart-ready data       │
│  4. Citation & Evidence  →  APA 7th citations, evidence validation  │
│                                                                     │
│  ※ Policy Brief pipeline: Retrieval Agent gets NLM tools added      │
│  ※ Policy Brief pipeline: Citation gets APA metadata for NotebookLM │
└──────────────┬──────────────────────────────┬───────────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐   ┌────────────────────────────────────┐
│   CHAT-SPECIFIC           │   │   POLICY-SPECIFIC                   │
│   (3 agents)              │   │   (4 agents)                        │
│                           │   │                                      │
│  5. Accident Analyst      │   │  5. RTI Analyst      ┐              │
│  6. Chart Builder         │   │  6. Mental Analyst   ├── parallel   │
│  7. Report Writer         │   │  7. NCD Analyst      ┘              │
│                           │   │  8. Policy Report Writer             │
│  → AgentResponse          │   │                                      │
│    (content + charts +    │   │  → PolicyBriefResponse               │
│     citations + followups)│   │    (per-domain reports + exec summary │
└──────────────────────────┘   │     + kpi_summary + citations)        │
                               └────────────────────────────────────┘
```

---

## 2. Request Router Agent (ตัวตัดสินใจ)

| Property | Value |
|----------|-------|
| **Role** | Request Router |
| **Goal** | วิเคราะห์คำขอและตัดสินใจว่าจะใช้ chat_pipeline หรือ policy_brief_pipeline |
| **Tools** | ไม่มี (ใช้ LLM วิเคราะห์ล้วน) |
| **Output** | JSON: pipeline, confidence, reason, extracted_params |

### กฎการ Routing

| เงื่อนไข | Pipeline | ตัวอย่าง |
|-----------|----------|----------|
| คำถามสถิติอุบัติเหตุทั่วไป | `chat_pipeline` | "สถิติอุบัติเหตุเชียงใหม่ปี 2024" |
| ขอกราฟ/แนวโน้ม/จุดเสี่ยง | `chat_pipeline` | "กราฟแนวโน้มอุบัติเหตุรายปี" |
| คำถามสนทนาทั่วไป/ทักทาย | `chat_pipeline` | "สวัสดี", "ระบบนี้ทำอะไรได้บ้าง" |
| ขอ Policy Brief/รายงานเชิงนโยบาย | `policy_brief_pipeline` | "สร้าง policy brief จ.อุบลราชธานี" |
| ขอรายงานตรวจราชการ | `policy_brief_pipeline` | "รายงานตรวจราชการ จ.ศรีสะเกษ" |
| วิเคราะห์สุขภาพจิต/NCD เชิงนโยบาย (เขต 10) | `policy_brief_pipeline` | "วิเคราะห์เชิงนโยบาย สุขภาพจิต จ.ยโสธร" |
| จังหวัดนอกเขต 10 | `chat_pipeline` | "สถิติอุบัติเหตุกรุงเทพ" |
| ไม่แน่ใจ | `chat_pipeline` (default) | — |

### Fallback Mechanism

Router มี 2 ระดับ:
1. **LLM-based routing** — ใช้ Gemini วิเคราะห์เชิงลึก (confidence สูง)
2. **Keyword-based fallback** — ใช้ keyword matching เมื่อ LLM parsing ล้มเหลว

```
User Message
    │
    ▼
[LLM Router Agent] ──── success ────→ { pipeline, confidence }
    │
    │ (parse failed)
    ▼
[Keyword Fallback] ──── always works ────→ { pipeline, confidence }
```

### Output Schema

```json
{
    "pipeline": "chat_pipeline",
    "confidence": 0.92,
    "reason": "ผู้ใช้ถามสถิติอุบัติเหตุรายปี ไม่ได้ขอรายงานเชิงนโยบาย",
    "extracted_params": {
        "province": "เชียงใหม่",
        "topics": ["accident"],
        "year": 2564,
        "report_type": "data_query"
    }
}
```

---

## 3. Shared Foundation Agents (1-4)

ทั้ง Chat Pipeline และ Policy Brief Pipeline ใช้ agents 1-4 ร่วมกัน
ลดความซ้ำซ้อนและให้ผลลัพธ์ที่สม่ำเสมอ

**Source**: `src/agents/shared_foundation.py`

```
build_foundation_agents(llm, include_nlm=False)  →  { interpreter, retriever, sql_specialist, citation_evidence }
build_foundation_tasks(agents, user_message, ...) →  { interpret, retrieve, sql, citation }
```

### Agent 1 — Request Interpreter

| Property | Value |
|----------|-------|
| **Role** | Request Interpreter |
| **Goal** | แปลความคำขอเป็นโครงสร้าง JSON (topics, geography, time_range, report_type) |
| **Tools** | ไม่มี |
| **Output** | JSON: topics, geography, time_range, report_type, focus, language |
| **File** | `src/agents/request_interpreter.py` |

### Agent 2 — Data Retrieval Specialist

| Property | Value |
|----------|-------|
| **Role** | Data Retrieval Specialist |
| **Goal** | ค้นหาข้อมูลจาก Document RAG (pgvector) และฐานข้อมูล PostgreSQL |
| **Tools** | 10 tools: search_documents, get_indicator_catalog, get_geography_profile, get_accident_summary, get_accident_hotspots, get_accident_time_distribution, get_road_condition_risk, get_province_year_summary, get_province_roads, get_all_provinces_ranking |
| **Policy mode** | +2 tools: `nlm_ask`, `get_supported_provinces` (NLM tools auto-added via `include_nlm=True`) |
| **File** | `src/agents/retrieval.py` |

### Agent 3 — SQL Specialist

| Property | Value |
|----------|-------|
| **Role** | SQL Specialist |
| **Goal** | เขียน SQL query เพื่อดึงข้อมูลสำหรับกราฟหรือการวิเคราะห์พิเศษ |
| **Tools** | execute_sql |
| **File** | `src/agents/sql_specialist.py` |

### Agent 4 — Citation & Evidence Agent

| Property | Value |
|----------|-------|
| **Role** | Citation & Evidence Agent |
| **Goal** | ตรวจสอบหลักฐาน สร้าง APA 7th Edition citation ประเมินความน่าเชื่อถือ |
| **Tools** | store_evidence, link_claim_evidence, get_evidence_summary |
| **Output** | JSON: evidence_items, claims, citations, reference_list, coverage_report |
| **Policy mode** | +APA metadata for NotebookLM sources (apa_type, apa_authors, apa_year, apa_publisher) |
| **File** | `src/agents/citation_evidence.py` |

---

## 4. Chat Pipeline (4 shared + 3 specific = 7 Agents)

Pipeline สำหรับค้นหาและวิเคราะห์ข้อมูลอุบัติเหตุ แสดงผลเป็นรายงาน + กราฟ

```
[SHARED FOUNDATION]                          [CHAT-SPECIFIC]
Interpreter → Retrieval → SQL → Citation  →  Analyst → Chart → Writer
```

### Agent 5 — Accident Data Analyst

| Property | Value |
|----------|-------|
| **Role** | Accident Data Analyst |
| **Goal** | วิเคราะห์ข้อมูลอุบัติเหตุ สังเคราะห์ประเด็นสำคัญ เสนอแนวทางป้องกัน |
| **Output** | key_findings, trends, risk_areas, risk_times, risk_groups, contributing_factors, recommended_actions, chart_candidates, table_candidates |
| **File** | `src/agents/analyst_accident.py` |

### Agent 6 — Chart Builder

| Property | Value |
|----------|-------|
| **Role** | Chart Builder |
| **Goal** | สร้าง ChartSpec JSON สำหรับ Chart.js |
| **Tools** | 7 chart tools |
| **Output** | JSON array ของ ChartSpec objects |
| **File** | `src/agents/chart_builder.py` |

### Agent 7 — Report Writer

| Property | Value |
|----------|-------|
| **Role** | Report Writer |
| **Goal** | เขียนรายงาน Markdown ภาษาไทย พร้อม citation และคำถามติดตาม |
| **Output** | Markdown report + inline citations + follow-up questions |
| **File** | `src/agents/report_writer.py` |

---

## 5. Policy Brief Pipeline (4 shared + 4 specific = 8 Agents)

Pipeline สำหรับสร้าง Policy Brief สาธารณสุข จากรายงานตรวจราชการผ่าน NotebookLM

```
[SHARED FOUNDATION with NLM]                 [POLICY-SPECIFIC]
Interpreter → Retrieval(+NLM) → SQL → Citation  →  [RTI‖Mental‖NCD] → Report Writer
```

### จังหวัดที่รองรับ (เขตสุขภาพที่ 10)

| จังหวัด | Notebook ID |
|---------|-------------|
| มุกดาหาร | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` |
| ยโสธร | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` |
| ศรีสะเกษ | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` |
| อำนาจเจริญ | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` |
| อุบลราชธานี | `bc3d9350-1855-45f0-a2c3-a5634ed8056e` |

### Shared Foundation differences for Policy Brief

| Agent | Chat mode | Policy mode |
|-------|-----------|-------------|
| **Retrieval Agent** | 10 standard tools | +2 NLM tools (`nlm_ask`, `get_supported_provinces`) |
| **Citation & Evidence** | Standard APA | +APA metadata for NotebookLM (apa_type, apa_authors, apa_year, apa_publisher) |

### Agent 5 — RTI Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Road Traffic Injury Policy Analyst |
| **Goal** | วิเคราะห์ RTI เชิงพื้นที่/พฤติกรรม สังเคราะห์ข้อเสนอนโยบาย |
| **Framework** | Haddon Matrix + 4 มาตรการหลัก |
| **Execution** | parallel with Mental & NCD |
| **Context** | retrieve_task, sql_task, citation_task |
| **File** | `src/agents/policy_rti.py` |

### Agent 6 — Mental Health Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Mental Health & Suicide Prevention Policy Analyst |
| **Goal** | วิเคราะห์สถิติสุขภาพจิต ระบุกลุ่มเปราะบาง เสนอนโยบายเชิงระบบ |
| **Safety** | Safety Guardrails บังคับ — epidemiological language, ห้ามระบุตัวตน, disclaimer |
| **Execution** | parallel with RTI & NCD |
| **File** | `src/agents/policy_mental.py` |

### Agent 7 — NCD Policy Analyst

| Property | Value |
|----------|-------|
| **Role** | Nutrition & NCD Policy Analyst |
| **Goal** | วิเคราะห์ห่วงโซ่ความเสี่ยง NCD เสนอ life-course intervention |
| **Framework** | Risk Chain: เด็กอ้วน → DM/HT → CKD → ภาระระบบ (ต้นน้ำ/กลางน้ำ/ปลายน้ำ) |
| **Execution** | parallel with RTI & Mental |
| **File** | `src/agents/policy_ncd.py` |

### Agent 8 — Policy Report Writer

| Property | Value |
|----------|-------|
| **Role** | Policy Brief Report Writer |
| **Goal** | สังเคราะห์ผลจาก 3 Analysts เป็น per-domain reports + Executive Summary + KPI Summary |
| **Output** | JSON: executive_summary, rti_report, mental_report, ncd_report, cross_topic_links, kpi_summary_table |
| **Style** | รายงานตรวจราชการ 4 ส่วน (สถานการณ์ → มาตรการ → ผลดำเนินงาน → ปัญหา/ข้อเสนอ) |
| **File** | `src/agents/policy_report_writer.py` |

---

## 6. API Endpoints

| Method | Path | Pipeline | คำอธิบาย |
|--------|------|----------|----------|
| `GET` | `/api/health` | — | ตรวจสุขภาพระบบ |
| `POST` | `/api/chat` | chat only | Chat Pipeline (Phase 2) — backward compatible |
| `POST` | `/api/chat/unified` | **auto-route** | **Unified: Router → chat หรือ policy-brief อัตโนมัติ** |
| `POST` | `/api/chat/stream` | **auto-route** | **Unified SSE stream** |
| `POST` | `/api/policy-brief` | policy-brief only | Policy Brief Pipeline (Phase 3) — direct access |
| `GET` | `/api/policy-brief/provinces` | — | รายชื่อจังหวัดที่รองรับ |
| `POST` | `/api/ingest` | — | นำเข้าเอกสารสู่ pgvector |
| `GET` | `/api/evidence/{id}` | — | ดู evidence item |

### Unified Endpoint (`POST /api/chat/unified`)

**Request:**
```json
POST /api/chat/unified
{
    "message": "สร้าง policy brief จ.อุบลราชธานี เรื่องอุบัติเหตุและสุขภาพจิต",
    "session_id": null
}
```

**Response:**
```json
{
    "pipeline_used": "policy_brief_pipeline",
    "routing": {
        "pipeline": "policy_brief_pipeline",
        "confidence": 0.95,
        "reason": "ผู้ใช้ขอสร้าง policy brief สำหรับจังหวัดในเขต 10",
        "extracted_params": {
            "province": "อุบลราชธานี",
            "topics": ["rti", "mental"],
            "year": 2564
        }
    },
    "result": {
        "province": "อุบลราชธานี",
        "policy_brief": "# นโยบายสาธารณสุข...",
        "sections": { "rti": {...}, "mental": {...} },
        "cross_topic_links": [...],
        "charts": [...],
        "citations": [...],
        "metadata": {
            "elapsed_seconds": 180,
            "pipeline_used": "policy_brief_pipeline",
            "routing_confidence": 0.95
        }
    }
}
```

---

## 7. Data Sources

```
┌──────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  NotebookLM      │  │  PostgreSQL       │  │  pgvector    │  │
│  │  (PDF reports)   │  │  (chat-aio DB)    │  │  (RAG Store) │  │
│  │                  │  │                   │  │              │  │
│  │  ใช้โดย:         │  │  ใช้โดย:          │  │  ใช้โดย:     │  │
│  │  Retrieval Agent │  │  Retrieval Agent  │  │  Retrieval   │  │
│  │  (policy mode)   │  │  + SQL Specialist │  │  Agent       │  │
│  │                  │  │                   │  │              │  │
│  │  รายงานตรวจราชการ │  │  Fact tables:     │  │  เอกสารนโยบาย │  │
│  │  5 จังหวัด       │  │  fact_accident_*  │  │  รายงานวิชาการ │  │
│  │  เขตสุขภาพที่ 10 │  │  Mart tables:     │  │              │  │
│  └──────────────────┘  │  mart_*           │  └──────────────┘  │
│                        │  Dim tables:      │                    │
│                        │  dim_*            │                    │
│                        │  Evidence tables: │                    │
│                        │  evidence_*       │                    │
│                        └──────────────────┘                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. โครงสร้างไฟล์

```
Agent/
├── src/
│   ├── agents/
│   │   ├── shared_foundation.py       ← ★ Shared Foundation (agents 1-4) factory
│   │   ├── request_router.py          ← Request Router Agent (ตัวตัดสินใจ)
│   │   ├── unified_orchestrator.py    ← Unified Orchestrator (รวม pipeline)
│   │   ├── orchestrator.py            ← Chat Pipeline (4 shared + 3 specific)
│   │   ├── policy_orchestrator.py     ← Policy Brief Pipeline (4 shared + 4 specific)
│   │   ├── progress.py                ← Agent progress tracking for UI timeline
│   │   ├── request_interpreter.py     ← Foundation: Agent 1
│   │   ├── retrieval.py               ← Foundation: Agent 2 (+NLM in policy mode)
│   │   ├── sql_specialist.py          ← Foundation: Agent 3
│   │   ├── citation_evidence.py       ← Foundation: Agent 4 (+APA metadata in policy)
│   │   ├── analyst_accident.py        ← Chat-specific: Agent 5
│   │   ├── chart_builder.py           ← Chat-specific: Agent 6
│   │   ├── report_writer.py           ← Chat-specific: Agent 7
│   │   ├── nlm_data_fetcher.py        ← (legacy, tools now in Retrieval Agent)
│   │   ├── policy_rti.py              ← Policy-specific: Agent 5
│   │   ├── policy_mental.py           ← Policy-specific: Agent 6
│   │   ├── policy_ncd.py              ← Policy-specific: Agent 7
│   │   └── policy_report_writer.py    ← Policy-specific: Agent 8
│   ├── tools/
│   │   ├── common.py                  ← search_documents, geography tools
│   │   ├── accident.py                ← accident domain tools
│   │   ├── chart_builder.py           ← chart data tools
│   │   └── notebooklm.py             ← nlm_ask tool (added to Retrieval Agent in policy mode)
│   ├── routers/
│   │   ├── chat.py                    ← /api/chat + /api/chat/unified + /api/chat/stream
│   │   ├── policy_brief.py            ← /api/policy-brief (direct access)
│   │   ├── health.py                  ← /api/health
│   │   ├── ingest.py                  ← /api/ingest
│   │   └── evidence.py                ← /api/evidence/{id}
│   └── schemas/
│       ├── request.py                 ← ChatRequest
│       ├── response.py                ← AgentResponse, ChartSpec, Citation
│       ├── evidence.py                ← EvidenceItem, Claim
│       └── policy_brief.py            ← PolicyBriefRequest/Response
```

---

## 9. Shared Foundation Architecture

ทั้ง 2 pipeline ใช้ `shared_foundation.py` สร้าง agents 1-4 ร่วมกัน:

| Component | Chat Pipeline | Policy Brief Pipeline |
|-----------|:---:|:---:|
| Request Interpreter | Agent 1 | Agent 1 (identical) |
| Data Retrieval Agent | Agent 2 (10 tools) | Agent 2 (10 tools + 2 NLM tools) |
| SQL Specialist | Agent 3 | Agent 3 (identical) |
| Citation & Evidence | Agent 4 | Agent 4 (+APA metadata for NLM sources) |
| PostgreSQL connection | Retrieval + SQL | Retrieval + SQL |
| pgvector (RAG) | Retrieval | Retrieval |
| NotebookLM | — | Retrieval (via `include_nlm=True`) |

### How it works

```python
# Chat pipeline
agents = build_foundation_agents(llm, include_nlm=False)
tasks  = build_foundation_tasks(agents, user_message)

# Policy pipeline
agents = build_foundation_agents(llm, include_nlm=True, province=province, notebook_id=notebook_id)
tasks  = build_foundation_tasks(agents, user_message, province=province, year=year, ...)
```

---

## 10. ประสิทธิภาพและ Timing

### Chat Pipeline (7 agents sequential)
| ขั้นตอน | เวลาโดยประมาณ |
|---------|--------------|
| Request Router | 3-5 วินาที |
| Request Interpreter | 5-10 วินาที |
| Data Retrieval | 10-20 วินาที |
| SQL Specialist | 10-15 วินาที |
| Citation & Evidence | 10-15 วินาที |
| Accident Analyst | 15-20 วินาที |
| Chart Builder | 10-15 วินาที |
| Report Writer | 15-25 วินาที |
| **รวม** | **~2-3 นาที** |

### Policy Brief Pipeline (8 agents, 3 parallel)
| ขั้นตอน | เวลาโดยประมาณ |
|---------|--------------|
| Request Router | 3-5 วินาที |
| Request Interpreter | 5-10 วินาที |
| Data Retrieval (+NLM, 3 queries) | 30-60 วินาที |
| SQL Specialist | 10-15 วินาที |
| Citation & Evidence (+APA) | 10-15 วินาที |
| RTI + Mental + NCD Analysts (parallel) | 15-20 วินาที |
| Policy Report Writer | 20-30 วินาที |
| **รวม** | **~2-3 นาที** |

---

## 11. ตัวอย่างการ Routing

### ตัวอย่างที่ 1: → chat_pipeline

```
User: "สถิติอุบัติเหตุจังหวัดเชียงใหม่ ทุกปี 2020-2026"

Router Output:
{
    "pipeline": "chat_pipeline",
    "confidence": 0.95,
    "reason": "ถามสถิติอุบัติเหตุทั่วไป ต้องการกราฟรายปี",
    "extracted_params": {
        "province": "เชียงใหม่",
        "topics": ["accident"],
        "report_type": "data_query"
    }
}

→ ใช้ 7 agents: [Foundation: Interpreter → Retrieval → SQL → Citation] → Analyst → Chart → Report
→ ผลลัพธ์: รายงาน + กราฟแนวโน้มอุบัติเหตุ
```

### ตัวอย่างที่ 2: → policy_brief_pipeline

```
User: "สร้าง policy brief สาธารณสุข จ.อุบลราชธานี ครอบคลุมอุบัติเหตุ สุขภาพจิต และ NCD"

Router Output:
{
    "pipeline": "policy_brief_pipeline",
    "confidence": 0.98,
    "reason": "ขอสร้าง policy brief สำหรับจังหวัดในเขตสุขภาพที่ 10",
    "extracted_params": {
        "province": "อุบลราชธานี",
        "topics": ["rti", "mental", "ncd"],
        "year": 2564,
        "report_type": "policy_brief"
    }
}

→ ใช้ 8 agents: [Foundation: Interpreter → Retrieval(+NLM) → SQL → Citation] → [RTI‖Mental‖NCD] → Report Writer
→ ผลลัพธ์: Policy Brief ฉบับสมบูรณ์ + Executive Summary + KPI Summary
```

### ตัวอย่างที่ 3: Fallback

```
User: "จุดเสี่ยงอุบัติเหตุ จ.อุบลราชธานี"

Router Output:
{
    "pipeline": "chat_pipeline",
    "confidence": 0.85,
    "reason": "ถามจุดเสี่ยงอุบัติเหตุ เป็น data query ไม่ใช่ policy brief",
    "extracted_params": {
        "province": "อุบลราชธานี",
        "topics": ["accident"]
    }
}

→ แม้จังหวัดอยู่ในเขต 10 แต่ไม่ได้ขอ policy brief → ใช้ chat_pipeline
```

---

## 12. ข้อควรระวัง

| ประเด็น | รายละเอียด | วิธีจัดการ |
|---------|-----------|-----------|
| **Router Latency** | Router เพิ่ม ~3-5 วินาที | ใช้ keyword fallback ถ้า LLM ช้า |
| **Ambiguous Requests** | คำขอที่กำกวมอาจถูก route ผิด | Default เป็น chat_pipeline (ปลอดภัยกว่า) |
| **Province Validation** | Policy Brief ต้องมีจังหวัดในเขต 10 | Fallback เป็น chat_pipeline ถ้าไม่มีจังหวัด |
| **Mental Health Safety** | ข้อมูล suicide อ่อนไหว | Safety guardrails + disclaimer บังคับ (Policy Brief) |
| **Backward Compatibility** | `/api/chat` ยังใช้ได้ | `/api/chat` ใช้ chat_pipeline เดิม, `/api/chat/unified` ใช้ router |

---

*Last updated: 2026-04-15 | Musya Agent v6.0 — Shared Foundation Pipeline Architecture*
