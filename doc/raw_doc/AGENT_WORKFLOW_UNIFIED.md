# Musya Agent — Unified Workflow Documentation

> รวม Chat Pipeline, Policy Brief Pipeline และ **Short Chat Branch** ภายใต้ **Shared Foundation Architecture** + ระบบ Routing อัตโนมัติ

> **เวอร์ชัน**: 7.0 (Short Chat + ThaiJO Subsystem)
> **วันที่**: 2026-04-16
> **ขอบเขต**: Shared Foundation (agents 1-4 + ThaiJO subsystem) + Chat Pipeline (5 specific) + Policy Brief Pipeline (4 specific) + Short Chat Branch (2 specific)

---

## 1. ภาพรวมระบบ (System Overview)

Musya Agent เป็นระบบ **Multi-Agent AI** ที่รวม 2 pipeline ภายใต้ **Request Router Agent**
ทั้ง 2 pipeline ใช้ **Shared Foundation Agents 1-4** ร่วมกัน แตกต่างกันเฉพาะส่วน domain-specific agents

```
User Message
    │
    ├── mode="short" (UI flag) ──────────────────────────────────────────┐
    │                                                                     │
    ▼                                                                     │
┌───────────────────────────────────────────────────────────────────────┐ │
│                    REQUEST ROUTER AGENT                              │ │
│                                                                     │ │
│  วิเคราะห์คำขอ → ตัดสินใจ pipeline                                   │ │
│                                                                     │ │
│  Output: { pipeline, confidence, reason, extracted_params }          │ │
│                                                                     │ │
│  ┌──────────────────┐  ┌──────────────────────────────┐  ┌────────┐ │ │
│  │  Keywords:        │  │  Keywords:                   │  │ mode   │ │ │
│  │  สถิติ, กราฟ,     │  │  นโยบาย, ตรวจราชการ,         │  │ flag   │ │ │
│  │  จุดเสี่ยง, อุบัติ │  │  policy brief, เขตสุขภาพ    │  │ =short │ │ │
│  │  → chat_pipeline  │  │  → policy_brief_pipeline    │  │ → short│ │ │
│  └────────┬─────────┘  └──────────────┬───────────────┘  └───┬────┘ │ │
└───────────┼────────────────────────────┼────────────────────────┼────┘ │
            │                            │                        │      │
            ▼                            ▼                        ▼      │
┌──────────────────────────────────────────────────────────────────────┐ │
│               SHARED FOUNDATION (Agents 1-4)                         │ │
│                                                                      │ │
│  1. Request Interpreter  →  parse intent, extract parameters         │ │
│  2. Data Retrieval       →  Document RAG + DB (+NLM for policy)      │ │
│                             ┌──────────────────────────────────┐     │ │
│                             │  ThaiJO Academic Subsystem       │     │ │
│                             │  tool: search_thaijo (tool 11)   │     │ │
│                             │  citations: C-200~C-299           │     │ │
│                             └──────────────────────────────────┘     │ │
│  3. SQL Specialist       →  complex queries, chart-ready data        │ │
│  4. Citation & Evidence  →  APA 7th citations, evidence validation   │ │
│                                                                      │ │
│  ※ Policy Brief pipeline: Retrieval Agent gets NLM tools added       │ │
│  ※ Policy Brief pipeline: Citation gets APA metadata for NotebookLM  │ │
│  ※ Short Chat: ใช้ Interpreter + Retrieval เท่านั้น (ข้าม SQL+Cite) │ │
└──────┬───────────────────────────────────┬───────────────────────┬──┘ │
       │                                   │                       │    │
       ▼                                   ▼                       ▼    │
┌──────────────────┐   ┌──────────────────────────────┐  ┌────────────┴──┐
│  CHAT-SPECIFIC   │   │  POLICY-SPECIFIC              │  │SHORT CHAT     │
│  (5 agents)      │   │  (4 agents, topic-conditional)│  │(2 agents)     │
│                  │   │                               │  │               │
│  5. Accident     │   │  5. RTI Analyst     ┐         │  │  SC-2. Quick  │
│     Analyst      │   │  6. Mental Analyst  ├parallel │  │     Retrieval │
│  6. Chart Builder│   │  7. NCD Analyst     ┘         │  │  SC-3. Quick  │
│  7. Research     │   │  8. Policy Report Writer       │  │     Answer    │
│     Synthesizer  │   │                               │  │     Writer    │
│  8. Deep Analyst │   │  → PolicyBriefResponse         │  │               │
│  9. Report       │   │    (per-domain + exec summary  │  │  → Short      │
│     Composer     │   │     + kpi_summary + citations) │  │    Response   │
│                  │   │                               │  │  (~30–60s)    │
│  → AgentResponse │   │                               │  │               │
│    (content +    │   │                               │  │               │
│     charts +     │   │                               │  │               │
│     citations +  │   │                               │  │               │
│     followups)   │   │                               │  │               │
└──────────────────┘   └──────────────────────────────┘  └───────────────┘
```

---

## 2. Request Router Agent (ตัวตัดสินใจ)

| Property | Value |
|----------|-------|
| **Role** | Request Router |
| **Goal** | วิเคราะห์คำขอและตัดสินใจว่าจะใช้ chat_pipeline, policy_brief_pipeline หรือ short_chat |
| **Tools** | ไม่มี (ใช้ LLM วิเคราะห์ล้วน + รับ mode flag จาก UI) |
| **Output** | JSON: pipeline, confidence, reason, extracted_params |

### กฎการ Routing

| เงื่อนไข | Pipeline | ตัวอย่าง |
|-----------|----------|----------|
| **mode flag = "short"** (ส่งมาจาก UI) | `short_chat` | — (user เลือก mode ถามสั้น) |
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

ทั้ง 3 pipeline ใช้ agents 1-4 ร่วมกัน (Chat / Policy Brief / Short Chat)
ลดความซ้ำซ้อนและให้ผลลัพธ์ที่สม่ำเสมอ

**Source**: `src/agents/shared_foundation.py`

```
build_foundation_agents(llm, include_nlm=False, include_thaijo=True, mode='full')
    → { interpreter, retriever, sql_specialist, citation_evidence }

build_foundation_tasks(agents, user_message, ...)
    → { interpret, retrieve, sql, citation }
```

### ThaiJO Academic Subsystem

ThaiJO เป็น subsystem ของ Shared Foundation ที่ให้ **academic context** ผ่าน Retrieval Agent:

| คุณสมบัติ | ค่า |
|-----------|-----|
| **Tool** | `search_thaijo(query, max_results=5)` |
| **Source** | api.thaijo.org (microservice port 8505) |
| **Tool number** | Tool 11 ใน Retrieval Agent |
| **Citation range** | C-200~C-299 |
| **Evidence type** | `thaijo_article` |
| **Trust level** | medium (peer-reviewed academic) |
| **APA format** | `apa_type: "article"` — journal article format |
| **File** | `src/tools/thaijo.py` |

```
Pipeline → Retrieval Agent → search_thaijo → ThaiJO API (port 8505)
                                           → บทความวิชาการ peer-reviewed
                                           → Citation Evidence Agent
                                           → [C-200] bibliography_text (APA article)
```

เปิดใช้งานในทุก pipeline:
- **Chat Pipeline**: ✅ (include_thaijo=True, default)
- **Policy Brief Pipeline**: ✅ (include_thaijo=True, default)
- **Short Chat Pipeline**: ✅ (search_thaijo optional ใน Quick Retrieval)

#### ThaiJO URL Validation & Cache (p01 fix — 2026-04)

เพื่อป้องกัน hallucinated `pdf_url` ใน Research Report pipeline:

| Layer | Mechanism |
|-------|-----------|
| **Pre-LLM** | `THAIJO_URL_PATTERN` regex กรอง URL ผิดรูปแบบก่อน cache/return |
| **Cache** | `thaijo_search_cache` (PostgreSQL) เก็บ API results พร้อม GIN index บน `results_json` |
| **Cache-first** | `_search_thaijo_impl()` เช็ค cache HIT ก่อน call API — MISS แล้วค่อย UPSERT |
| **Post-LLM (Citation Agent)** | `_verify_thaijo_url_in_cache()` ตรวจ `open_url` ทุกตัวที่เป็น `thaijo_article` — clear ถ้าไม่พบใน cache |
| **Post-LLM (Orchestrator)** | `_parse()` ใช้ priority-based correction: exact match → pattern check → fuzzy ≥ 0.6 → clear |
| **Logging** | Citation guard log: `Citation guard: N ThaiJO citation(s) had URLs cleared` |

Config: `THAIJO_CACHE_TTL_DAYS=7` (`.env` หรือ `src/config.py`)

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
| **Tools** | 11 tools: `search_documents`, `get_indicator_catalog`, `get_geography_profile`, `get_province_year_summary`, `get_province_roads`, `get_all_provinces_ranking`, `get_accident_summary`, `get_accident_hotspots`, `get_accident_time_distribution`, `get_road_condition_risk`, `search_thaijo` (tool 11) |
| **Policy mode** | +2 tools: `NotebookLM Ask Tool`, `Get Supported Provinces` (NLM tools auto-added via `include_nlm=True`) → 13 tools total |
| **File** | `src/agents/retrieval.py` |

### Agent 3 — SQL Specialist

| Property | Value |
|----------|-------|
| **Role** | SQL Specialist |
| **Goal** | เขียน SQL query เพื่อดึงข้อมูลสำหรับกราฟหรือการวิเคราะห์พิเศษ |
| **Tools** | `execute_custom_sql`, `explain_schema`, `get_table_row_count` |
| **File** | `src/agents/sql_specialist.py` |

### Agent 4 — Citation & Evidence Agent

| Property | Value |
|----------|-------|
| **Role** | Citation & Evidence Agent |
| **Goal** | ตรวจสอบหลักฐาน สร้าง APA 7th Edition citation ประเมินความน่าเชื่อถือ |
| **Tools** | `list_all_documents_apa`, `lookup_document_apa`, `register_evidence`, `register_claim_links` |
| **Output** | JSON: evidence_items, claims, citations (with open_url + bibliography_text), reference_list, coverage_report |
| **Policy mode** | +APA metadata for NotebookLM sources (apa_type, apa_authors, apa_year, apa_publisher) |
| **File** | `src/agents/citation_evidence.py` |

---

## 4. Chat Pipeline (4 shared + 5 specific = 9 Agents)

Pipeline สำหรับค้นหาและวิเคราะห์ข้อมูลอุบัติเหตุ แสดงผลเป็นรายงาน + กราฟ

```
[SHARED FOUNDATION]                          [CHAT-SPECIFIC]
Interpreter → Retrieval → SQL → Citation  →  Analyst → Chart → Research Synthesizer → Deep Analyst → Report Composer
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

### Agent 7 — Research Synthesizer *(NEW)*

| Property | Value |
|----------|-------|
| **Role** | Research Synthesizer |
| **Goal** | แปลงข้อมูลดิบและผลการวิเคราะห์เป็น narrative prose blocks 4 บล็อก (1,200–2,000 คำ) |
| **Output** | 4 narrative blocks: สถานการณ์, กลุ่มเสี่ยง, GAP, บริบทพื้นที่ |
| **File** | `src/agents/research_synthesizer.py` |

### Agent 8 — Deep Analyst *(NEW)*

| Property | Value |
|----------|-------|
| **Role** | Deep Policy Analyst |
| **Goal** | วิเคราะห์เชิงลึก 4 มิติ: Root Cause (Haddon Matrix), Comparative, Policy Implications, Trend |
| **Output** | การวิเคราะห์ 4 มิติ รวม 1,000–1,500 คำ |
| **File** | `src/agents/deep_analyst.py` |

### Agent 9 — Report Composer

| Property | Value |
|----------|-------|
| **Role** | Report Writer |
| **Goal** | เขียนรายงาน Markdown ภาษาไทย 2,000–4,000 คำ พร้อม citation และคำถามติดตาม |
| **Output** | Markdown report + inline citations [C-xxx] + KPI table + reference list APA 7th + follow-up questions |
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

## 6. Accident Policy Pipeline (Zone 10) — 3 Agents (NEW)

Pipeline แบบย่อ (3 agents) สำหรับวิเคราะห์และจัดทำรายงานนโยบายอุบัติเหตุทางถนนสำหรับเขตสุขภาพที่ 10 ดึงข้อมูลจาก Data Marts และ Fact tables ในระบบโดยตรงเพื่อลดเวลา (ไม่ต้องใช้ NotebookLM)

```
[ZONE10 FETCH]                [ZONE10 ANALYST]                [ZONE10 WRITER]
Zone10 SQL Data Fetcher  →  Zone10 Policy Analyst  →  Zone10 Report Writer
```

### Agent Z1 — Zone10 SQL Data Fetcher
| Property | Value |
|----------|-------|
| **Role** | Zone 10 SQL Data Fetcher |
| **Goal** | ดึงข้อมูล 7 policy queries สำหรับเขตสุขภาพ 10 โดยใช้ 7 tools |
| **Tools** | 7 tools: `get_zone10_top_roads`, `get_zone10_time_bands`, `get_zone10_motorcycle_severity`, `get_zone10_car_serious_injuries`, `get_zone10_environment_risk`, `get_zone10_yearly_kpi`, `get_zone10_monthly_risk` |
| **LLM Tier** | Fast (gemini-2.0-flash) |
| **File** | `src/agents/accident_policy_agent.py` |

### Agent Z2 — Zone10 Policy Analyst
| Property | Value |
|----------|-------|
| **Role** | Zone 10 Policy Analyst |
| **Goal** | วิเคราะห์ข้อมูลด้วยกรอบ Haddon Matrix แยก 4 หมวดนโยบาย |
| **LLM Tier** | Pro (gemini-2.5-pro) |
| **File** | `src/agents/accident_policy_agent.py` |

### Agent Z3 — Zone10 Report Writer
| Property | Value |
|----------|-------|
| **Role** | Zone 10 Report Writer |
| **Goal** | เขียนรายงานนโยบายสำหรับ สสส./สสจ./ศปถ. ในรูปแบบราชการ |
| **LLM Tier** | Pro (gemini-2.5-pro) |
| **File** | `src/agents/accident_policy_agent.py` |

---

## 7. Accident Chat Pipeline (Zone 10) — 2 Agents (NEW)

Pipeline สำหรับตอบคำถามสั้นๆ และวิเคราะห์ข้อมูลอุบัติเหตุจาก SQL โดยอัตโนมัติ

```
[SQL SPECIALIST]                [ANSWER WRITER]
Accident SQL Data Specialist  →  RTI Policy Answer Writer
```

### Agent C1 — Accident SQL Data Specialist
| Property | Value |
|----------|-------|
| **Role** | Accident SQL Data Specialist |
| **Goal** | ดึงข้อมูลอุบัติเหตุที่ถูกต้องและครบถ้วนจากฐานข้อมูลโดยใช้เครื่องมือที่เหมาะสม |
| **Tools** | `ACCIDENT_CHAT_TOOLS` |
| **LLM Tier** | Fast (gemini-2.0-flash) |
| **File** | `src/agents/accident_chat_orchestrator.py` |

### Agent C2 — RTI Policy Answer Writer
| Property | Value |
|----------|-------|
| **Role** | RTI Policy Answer Writer |
| **Goal** | เขียนคำตอบภาษาไทยทางการที่ชัดเจน มีตาราง Markdown และข้อเสนอแนะเชิงนโยบาย |
| **LLM Tier** | Pro (gemini-2.5-pro) |
| **File** | `src/agents/accident_chat_orchestrator.py` |

---

## 8. Short Chat Pipeline (2 shared + 2 specific = 4 Agents)

Pipeline น้ำหนักเบาสำหรับตอบคำถามสั้น ๆ รวดเร็ว ไม่ต้องรอรายงานเต็ม

```
[SHARED FOUNDATION — minimal]    [SHORT-CHAT-SPECIFIC]
Interpreter → Quick Retrieval  →  Quick Answer Writer
(ข้าม SQL Specialist + Citation & Evidence Agent เต็มรูปแบบ)
```

**เปิดใช้งานด้วย**: mode flag = "short" จาก UI หรือ ChatRequest

### Agent SC-1 — Request Interpreter (shared)

ใช้ agent เดียวกับ Shared Foundation Agent 1 — parse intent แบบเดียวกัน

### Agent SC-2 — Quick Retrieval

| Property | Value |
|----------|-------|
| **Role** | Quick Retrieval Specialist |
| **Goal** | ค้นหาข้อมูลที่เกี่ยวข้องอย่างรวดเร็ว (1 round, ไม่ exhaustive) |
| **Tools** | `search_documents`, `get_accident_summary`, `search_thaijo` (optional) |
| **ไม่ใช้** | SQL Specialist, NLM tools, Citation & Evidence full pipeline |
| **File** | `src/agents/shared_foundation.py` (mode='short' builds minimal retriever) |

### Agent SC-3 — Quick Answer Writer

| Property | Value |
|----------|-------|
| **Role** | Quick Answer Writer |
| **Goal** | สรุปข้อมูลเป็นคำตอบสั้น ภาษาไทย 500–1,000 คำ พร้อม citation เบื้องต้น |
| **Output** | Markdown สั้น + inline citations [C-xxx] + follow-up questions (2-3 ข้อ) |
| **ไม่มี** | กราฟ, KPI table, Deep Analysis |
| **Disclaimer** | "อ้างอิงเบื้องต้น — ใช้ 'รายงานเต็ม' สำหรับรายงานที่ผ่าน APA validation" |
| **File** | `src/agents/quick_answer_writer.py` *(สร้างใหม่)* |

### ประสิทธิภาพ Short Chat

| ขั้นตอน | เวลาโดยประมาณ |
|---------|---------------|
| Request Router | 2-3 วินาที |
| Request Interpreter | 3-5 วินาที |
| Quick Retrieval | 10-15 วินาที |
| Quick Answer Writer | 10-15 วินาที |
| **รวม** | **~25–40 วินาที** |

### Output Schema

```json
{
    "pipeline_used": "short_chat",
    "content": "## สรุปจุดเสี่ยง\n...",
    "citations": [
        { "code": "C-101", "bibliography_text": "...", "open_url": "..." }
    ],
    "elapsed_seconds": 35.2,
    "follow_up_questions": ["ต้องการรายงานเต็มหรือไม่?", "..."]
}
```

---

## 7. API Endpoints

| Method | Path | Pipeline | คำอธิบาย |
|--------|------|----------|----------|
| `GET` | `/api/health` | — | ตรวจสุขภาพระบบ |
| `POST` | `/api/chat` | chat only | Chat Pipeline (Phase 2) — backward compatible |
| `POST` | `/api/chat/unified` | **auto-route** | **Unified: Router → chat หรือ policy-brief อัตโนมัติ** |
| `POST` | `/api/chat/stream` | **auto-route** | **Unified SSE stream** |
| `POST` | `/api/chat/short` | **short_chat** | **Short Chat — คำตอบสั้น ~30–60s** *(ใหม่)* |
| `POST` | `/api/chat/short/stream` | **short_chat** | **Short Chat SSE stream** *(ใหม่)* |
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
│   │   ├── policy_report_writer.py    ← Policy-specific: Agent 8
│   │   ├── quick_answer_writer.py     ← ★ Short Chat: SC-3 Quick Answer Writer
│   │   └── short_chat_orchestrator.py  ← ★ Short Chat Orchestrator (3 agents)
│   ├── tools/
│   │   ├── common.py                  ← search_documents, geography tools
│   │   ├── accident.py                ← accident domain tools
│   │   ├── chart_builder.py           ← chart data tools
│   │   └── notebooklm.py             ← nlm_ask tool (added to Retrieval Agent in policy mode)
│   ├── routers/
│   │   ├── chat.py                    ← /api/chat + /api/chat/unified + /api/chat/stream + /api/chat/short + /api/chat/short/stream
│   │   ├── policy_brief.py            ← /api/policy-brief (direct access)
│   │   ├── health.py                  ← /api/health
│   │   ├── ingest.py                  ← /api/ingest
│   │   └── evidence.py                ← /api/evidence/{id}
│   └── schemas/
│       ├── request.py                 ← ChatRequest (+ mode field)
│       ├── response.py                ← AgentResponse, ChartSpec, Citation
│       ├── evidence.py                ← EvidenceItem, Claim
│       ├── policy_brief.py            ← PolicyBriefRequest/Response
│       └── short_chat.py              ← ★ ShortChatRequest/Response
```

---

## 10. Shared Foundation Architecture

ทั้ง 2 pipeline ใช้ `shared_foundation.py` สร้าง agents 1-4 ร่วมกัน:

| Component | Chat Pipeline | Policy Brief Pipeline | Short Chat Pipeline |
|-----------|:---:|:---:|:---:|
| Request Interpreter | Agent 1 | Agent 1 (identical) | SC-1 (identical) |
| Data Retrieval Agent | Agent 2 (11 tools) | Agent 2 (11 tools + 2 NLM tools = 13) | SC-2 (3 tools, minimal) |
| **ThaiJO Subsystem** | **Tool 11 ✅** | **Tool 11 ✅** | **Optional ✅** |
| SQL Specialist | Agent 3 | Agent 3 (identical) | ❌ ข้าม |
| Citation & Evidence | Agent 4 | Agent 4 (+APA metadata for NLM sources) | ❌ ข้าม (inline only) |
| PostgreSQL connection | Retrieval + SQL | Retrieval + SQL | Retrieval only |
| pgvector (RAG) | Retrieval | Retrieval | Retrieval |
| NotebookLM | — | Retrieval (via `include_nlm=True`) | — |

### How it works

```python
# Chat pipeline
agents = build_foundation_agents(llm, include_nlm=False, include_thaijo=True, mode='full')
tasks  = build_foundation_tasks(agents, user_message, mode='full')

# Policy pipeline
agents = build_foundation_agents(llm, include_nlm=True, include_thaijo=True, province=province, notebook_id=notebook_id, mode='full')
tasks  = build_foundation_tasks(agents, user_message, province=province, year=year, ...)

# Short Chat pipeline
agents = build_foundation_agents(llm, include_nlm=False, include_thaijo=True, mode='short')
tasks  = build_foundation_tasks(agents, user_message, mode='short')  # returns interpret + retrieve only
```

---

## 11. ประสิทธิภาพและ Timing

### Chat Pipeline (9 agents sequential)
| ขั้นตอน | เวลาโดยประมาณ |
|---------|---------------|
| Request Router | 3-5 วินาที |
| Request Interpreter | 5-10 วินาที |
| Data Retrieval (search_documents บังคับ) | 15-25 วินาที |
| SQL Specialist | 10-15 วินาที |
| Citation & Evidence | 10-15 วินาที |
| Accident Analyst | 15-20 วินาที |
| Chart Builder | 10-15 วินาที |
| Research Synthesizer | 15-20 วินาที |
| Deep Analyst | 15-20 วินาที |
| Report Composer | 20-30 วินาที |
| **รวม** | **~3-5 นาที** |

### Policy Brief Pipeline (4-8 agents, topic-conditional parallel)
| ขั้นตอน | เวลาโดยประมาณ |
|---------|---------------|
| Request Router | 3-5 วินาที |
| Request Interpreter | 5-10 วินาที |
| Data Retrieval (+search_documents บังคับ +NLM) | 30-60 วินาที |
| SQL Specialist | 10-15 วินาที |
| Citation & Evidence (+APA) | 10-15 วินาที |
| Analysts (เฉพาะ topic ที่ขอ) parallel | 15-20 วินาที |
| Policy Report Writer | 20-30 วินาที |
| **รวม (1 topic)** | **~2-3 นาที** |
| **รวม (3 topics)** | **~3-4 นาที** |

### Short Chat Pipeline (4 agents sequential)
| ขั้นตอน | เวลาโดยประมาณ |
|---------|---------------|
| Request Router | 2-3 วินาที |
| Request Interpreter | 3-5 วินาที |
| Quick Retrieval (search_documents + optional ThaiJO) | 10-15 วินาที |
| Quick Answer Writer | 10-15 วินาที |
| **รวม** | **~25–40 วินาที** |

---

## 12. ตัวอย่างการ Routing

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
User: "ขอเเผนการลดอุบัติเหตุจังหวัดอุบลราชธานี ร้อยละ 20"
→ keyword 'อุบัติเหตุ' + จังหวัดในเขต 10 + 'แผนการลด' → policy_brief_pipeline topics=["rti"]
→ RTI Analyst เท่านั้น (Mental/NCD ไม่ถูกสร้าง)

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

### ตัวอย่างที่ 3: → short_chat (UI mode flag)

```
User: [เลือก mode "ถามสั้น" ใน UI] "จุดเสี่ยงอุบัติเหตุอุบลราชธานีมีที่ไหนบ้าง"

Request: POST /api/chat/short { "message": "...", "mode": "short" }

Router Output:
{
    "pipeline": "short_chat",
    "confidence": 1.0,
    "reason": "mode flag = short ตั้งจาก UI",
    "extracted_params": { "province": "อุบลราชธานี", "topics": ["accident"] }
}

→ ใช้ 4 agents: Router → [Interpreter → Quick Retrieval → Quick Answer Writer]
→ ผลลัพธ์: สรุปจุดเสี่ยง 500–800 คำ + citations เบื้องต้น ภายใน ~35 วินาที
→ Disclaimer: "ใช้ 'รายงานเต็ม' สำหรับกราฟและการวิเคราะห์เชิงลึก"
```

### ตัวอย่างที่ 4: Fallback

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

## 13. ข้อควรระวัง

| ประเด็น | รายละเอียด | วิธีจัดการ |
|---------|-----------|-----------|
| **Router Latency** | Router เพิ่ม ~3-5 วินาที | ใช้ keyword fallback ถ้า LLM ช้า |
| **Ambiguous Requests** | คำขอที่กำกวมอาจถูก route ผิด | Default เป็น chat_pipeline (ปลอดภัยกว่า) |
| **Document RAG empty** | search_documents คืนค่าว่าง | ตรวจสอบว่า document_embeddings มีข้อมูล (ต้อง ingest ก่อน) |
| **Topic extraction** | LLM อาจ extract topics ผิด | Keyword fallback ใน _keyword_fallback() ทำงานแทน |
| **Province Validation** | Policy Brief ต้องมีจังหวัดในเขต 10 | Fallback เป็น chat_pipeline ถ้าไม่มีจังหวัด |
| **Mental Health Safety** | ข้อมูล suicide อ่อนไหว | Safety guardrails + disclaimer บังคับ (Policy Brief) |
| **Backward Compatibility** | `/api/chat` ยังใช้ได้ | `/api/chat` ใช้ chat_pipeline เดิม, `/api/chat/unified` ใช้ router |
| **Short Chat ไม่มีกราฟ** | SQL + Chart Builder ถูกข้าม | แจ้ง user ใน response: "ใช้รายงานเต็มสำหรับกราฟ" |
| **ThaiJO API ไม่ up** | search_thaijo timeout | graceful fallback — ข้าม ThaiJO, ใช้ sources อื่น |
| **Short Chat citation ไม่ครบ** | ไม่ผ่าน Citation Agent เต็มรูป | Disclaimer บังคับในทุก short chat response |

---

*Last updated: 2026-04-16 | Musya Agent v7.0 — Short Chat Branch + ThaiJO Subsystem*
