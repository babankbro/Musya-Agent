# Musya Agent — Workflow Documentation

> อธิบาย workflow ของระบบ Multi-Agent Pipeline และการทำงานของ Test UI

---

## 📋 ภาพรวมระบบ (System Overview)

Musya Agent เป็นระบบ **Multi-Agent AI** ที่ใช้ CrewAI ประกอบด้วย **7 agents** ทำงานต่อเนื่องกันแบบ Sequential Pipeline เพื่อตอบคำถามเกี่ยวกับข้อมูลอุบัติเหตุ สุขภาพ และโภชนาการ

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Server (port 8000)                      │
│                                                                     │
│  POST /api/chat  →  orchestrator.run_chat()                        │
│                                                                     │
│  Agent Pipeline (Sequential):                                       │
│                                                                     │
│  1. Request Interpreter                                             │
│       │                                                             │
│       ▼                                                             │
│  2. Data Retrieval Specialist  ←── RAG (pgvector) + DB Tools       │
│       │                                                             │
│       ▼                                                             │
│  3. SQL Specialist  ←── PostgreSQL (Direct SQL)                    │
│       │                                                             │
│       ▼                                                             │
│  4. Citation & Evidence Agent  ←── Evidence DB                     │
│       │                                                             │
│       ▼                                                             │
│  5. Accident Data Analyst                                           │
│       │                                                             │
│       ▼                                                             │
│  6. Chart Builder  ←── Chart DB Tools                              │
│       │                                                             │
│       ▼                                                             │
│  7. Report Writer                                                   │
│       │                                                             │
│       ▼                                                             │
│  AgentResponse (JSON)                                               │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
Test UI / Frontend
```

---

## 🤖 รายละเอียด 7 Agents

### Agent 1 — Request Interpreter

| Property | Value |
|----------|-------|
| **Role** | Request Interpreter |
| **Goal** | แปลความคำขอของผู้ใช้ให้เป็นโครงสร้างข้อมูลที่ชัดเจน |
| **Tools** | ไม่มี (ใช้ LLM วิเคราะห์ล้วน) |
| **Output** | JSON object ที่มี topics, geography, time_range, report_type, focus, language |

**ทำอะไร:**
- รับ `user_message` ดิบจากผู้ใช้
- วิเคราะห์หัวข้อ (accident / mental_health / nutrition / general)
- ระบุพื้นที่ทางภูมิศาสตร์ (จังหวัด, ภูมิภาค, ทั้งประเทศ)
- ระบุช่วงเวลา (start_date, end_date)
- ระบุประเภทรายงาน (health_plan / executive_summary / data_query / general_chat)
- ระบุภาษา (th / en)

**ตัวอย่าง Output:**
```json
{
    "topics": ["accident"],
    "geography": "เชียงใหม่",
    "time_range": {"start_date": "2020-01-01", "end_date": "2026-12-31"},
    "report_type": "data_query",
    "focus": ["แนวโน้มรายปี"],
    "language": "th"
}
```

---

### Agent 2 — Data Retrieval Specialist

| Property | Value |
|----------|-------|
| **Role** | Data Retrieval Specialist |
| **Goal** | ค้นหาและรวบรวมข้อมูลจากทั้งเอกสาร (Document RAG) และฐานข้อมูล |
| **Tools** | 10 tools (ดูด้านล่าง) |
| **Input** | ผลจาก Request Interpreter (Task Context) |
| **Output** | ข้อมูลทั้งหมดที่ค้นมาได้ พร้อมแหล่งที่มา |

**Tools ที่ใช้:**

| Tool | แหล่งข้อมูล | คำอธิบาย |
|------|------------|----------|
| `search_documents` | pgvector (`document_embeddings`) | ค้นเอกสารนโยบาย รายงานวิชาการ |
| `get_indicator_catalog` | PostgreSQL | รายการตัวชี้วัดสุขภาพ |
| `get_geography_profile` | PostgreSQL | ข้อมูลพื้นที่ทางภูมิศาสตร์ |
| `get_accident_summary` | PostgreSQL | สรุปสถิติอุบัติเหตุ |
| `get_accident_hotspots` | PostgreSQL | จุดเสี่ยงอุบัติเหตุ |
| `get_accident_time_distribution` | PostgreSQL | การกระจายตามช่วงเวลา |
| `get_road_condition_risk` | PostgreSQL | ความเสี่ยงตามสภาพถนน |
| `get_province_year_summary` | PostgreSQL | สรุปรายจังหวัดรายปี |
| `get_province_roads` | PostgreSQL | ถนนเสี่ยงรายจังหวัด |
| `get_all_provinces_ranking` | PostgreSQL | จัดอันดับทุกจังหวัด |

---

### Agent 3 — SQL Specialist

| Property | Value |
|----------|-------|
| **Role** | SQL Specialist |
| **Goal** | เขียน SQL query เพื่อดึงข้อมูลเฉพาะเจาะจงสำหรับกราฟหรือการวิเคราะห์พิเศษ |
| **Tools** | `execute_sql` (ส่งตรงไปยัง PostgreSQL) |
| **Input** | ผลจาก Retrieval Agent |
| **Output** | ข้อมูลในรูปแบบที่พร้อมสร้างกราฟ หรือผลลัพธ์ custom query |

**ตัดสินใจอัตโนมัติว่า:**
- ถ้าต้องการกราฟ/แนวโน้ม → เขียน SQL ดึงข้อมูล time-series
- ถ้าต้องการข้อมูลเฉพาะ → เขียน SQL แบบ custom
- ถ้าข้อมูลจาก Retrieval พอแล้ว → ตอบว่าไม่ต้องใช้ SQL เพิ่ม

**รู้โครงสร้าง Database:**
- `fact_accident_event` — เหตุการณ์อุบัติเหตุ (129,882 rows)
- `fact_accident_person` — ผู้ประสบเหตุ (202 rows)
- `dim_geography` — ข้อมูลพื้นที่ (83 rows)
- `dim_time` — มิติเวลา (4,018 rows)
- `mart_accident_summary`, `mart_accident_hotspot`, `mart_province_year` — Mart tables สำหรับ query เร็ว

---

### Agent 4 — Citation & Evidence Agent

| Property | Value |
|----------|-------|
| **Role** | Citation & Evidence Agent |
| **Goal** | ตรวจสอบหลักฐาน สร้าง citation และประเมินความน่าเชื่อถือของข้อมูล |
| **Tools** | `store_evidence`, `link_claim_evidence`, `get_evidence_summary` |
| **Input** | ผลจาก Retrieval + SQL Specialist |
| **Output** | JSON พร้อม evidence_items, claims, citations, coverage_report |

**5 ขั้นตอนหลัก:**

1. **Normalize Evidence** — แปลงข้อมูลดิบเป็น EvidenceItem ที่มี metadata ครบ
   - `evidence_type`: document / database / api
   - `trust_level`: high / medium / low
   - `source_ref`, `title`, `page_ref`, `section_label`

2. **Map Claims to Evidence** — เชื่อมข้อสรุปกับหลักฐาน
   - `support_level`: supported / partially_supported / insufficient / conflicting
   - `evidence_strength`: strong / moderate / weak

3. **Generate Citations** — สร้างรหัส citation (C-001, C-002, ...)
   - `citation_text` — inline citation สำหรับรายงาน
   - `bibliography_text` — reference list ท้ายรายงาน

4. **Prepare Source Notes** — สร้าง source note สำหรับแต่ละกราฟ/ตาราง

5. **Coverage Check** — ตรวจว่าทุก claim มี citation รองรับ

**ตัวอย่าง Output:**
```json
{
  "evidence_items": [
    {
      "evidence_id": "EV-001",
      "evidence_type": "database",
      "source_ref": "fact_accident_event",
      "title": "ข้อมูลอุบัติเหตุปี 2020-2026",
      "trust_level": "high"
    }
  ],
  "citations": [
    {
      "citation_code": "C-001",
      "citation_text": "[C-001] ฐานข้อมูลอุบัติเหตุ, 2024",
      "open_url": "/api/evidence/EV-001"
    }
  ],
  "coverage": {
    "coverage_score": 0.85,
    "uncited_claims": []
  }
}
```

---

### Agent 5 — Accident Data Analyst

| Property | Value |
|----------|-------|
| **Role** | Accident Data Analyst |
| **Goal** | วิเคราะห์ข้อมูลอุบัติเหตุ สังเคราะห์ประเด็นสำคัญ และเสนอแนวทางป้องกัน |
| **Tools** | ไม่มี (วิเคราะห์จาก context ของ tasks ก่อนหน้า) |
| **Input** | ผลจาก Retrieval + SQL Specialist + Citation & Evidence |
| **Output** | ผลการวิเคราะห์ 9 ส่วน |

**9 ส่วนของ Output:**
1. `key_findings` — ข้อค้นพบสำคัญ (≥3 ข้อ)
2. `trends` — แนวโน้มที่พบ (เพิ่ม/ลด/ทรงตัว)
3. `risk_areas` — พื้นที่เสี่ยงสูง
4. `risk_times` — ช่วงเวลาเสี่ยง
5. `risk_groups` — กลุ่มเสี่ยงหลัก
6. `contributing_factors` — ปัจจัยที่เกี่ยวข้อง
7. `recommended_actions` — มาตรการ (ระยะสั้น/กลาง/ยาว)
8. `chart_candidates` — กราฟที่ควรสร้าง
9. `table_candidates` — ตารางที่ควรสร้าง

**กฎสำคัญ:** ห้ามสรุปเกินหลักฐาน และต้องแยก "ข้อเท็จจริง" กับ "การตีความ" ชัดเจน

---

### Agent 6 — Chart Builder

| Property | Value |
|----------|-------|
| **Role** | Chart Builder |
| **Goal** | สร้าง ChartSpec JSON ที่พร้อมแสดงผลบน frontend Chart.js |
| **Tools** | 7 chart tools (ดูด้านล่าง) |
| **Input** | ผลจาก Retrieval + SQL Specialist + Analyst + Citation & Evidence |
| **Output** | JSON array ของ ChartSpec objects |

**Chart Tools:**

| Tool | ประเภทกราฟ | คำอธิบาย |
|------|-----------|----------|
| `build_province_year_trend_chart` | line/bar | แนวโน้มรายปีรายจังหวัด |
| `build_province_roads_bar_chart` | bar | ถนนเสี่ยงในจังหวัด |
| `build_accident_trend_chart` | line | แนวโน้มอุบัติเหตุรวม |
| `build_hotspot_bar_chart` | bar | จุดเสี่ยงอันดับสูงสุด |
| `build_time_distribution_chart` | bar | การกระจายตามช่วงเวลา |
| `build_road_condition_pie_chart` | pie | สัดส่วนสภาพถนน |
| `build_monthly_death_bar_chart` | bar | ผู้เสียชีวิตรายเดือน |

**ChartSpec Format (รองรับโดย Chart.js):**
```json
{
  "type": "bar",
  "title": "อุบัติเหตุจังหวัดเชียงใหม่ 2020-2026",
  "data": {
    "labels": ["2020", "2021", "2022", "2023", "2024"],
    "datasets": [
      {
        "label": "จำนวนครั้ง",
        "data": [1200, 1350, 980, 1100, 1420]
      }
    ]
  },
  "options": {},
  "source_note": "ที่มา: ฐานข้อมูลอุบัติเหตุ [C-001]"
}
```

---

### Agent 7 — Report Writer

| Property | Value |
|----------|-------|
| **Role** | Report Writer |
| **Goal** | เขียนรายงานภาษาไทยในรูปแบบ Markdown พร้อม citation และคำถามติดตาม |
| **Tools** | ไม่มี (สังเคราะห์จาก context ทั้งหมด) |
| **Input** | ผลจาก Analyst + Chart Builder + Citation & Evidence |
| **Output** | รายงาน Markdown พร้อม inline citation และ follow-up questions |

**โครงสร้าง Output:**
```markdown
## สรุปสถานการณ์

ในปี 2024 มีอุบัติเหตุทางถนนจำนวน 1,420 ครั้ง [C-001] เพิ่มขึ้น 29% 
จากปี 2023 [C-002]...

## จุดเสี่ยงสำคัญ
...

## ข้อเสนอแนะ
...

---
## อ้างอิง
[C-001] ฐานข้อมูลอุบัติเหตุแห่งชาติ. (2024). fact_accident_event.
[C-002] ...

---
**คำถามติดตาม:**
1. จุดเสี่ยงอุบัติเหตุในเชียงใหม่คือที่ไหนบ้าง?
2. กลุ่มเสี่ยงหลักที่ควรเร่งป้องกันคือใคร?
3. มาตรการใดได้ผลดีที่สุดในช่วง 5 ปีที่ผ่านมา?
```

---

## 🗄️ Data Sources

```
┌─────────────────────────────────────────────────────┐
│                  Data Sources                       │
│                                                     │
│  ┌──────────────┐   ┌──────────────────────────┐   │
│  │   pgvector   │   │      PostgreSQL           │   │
│  │  (RAG Store) │   │   (chat-aio database)    │   │
│  │ doc_embeddings│   │                          │   │
│  │ - นโยบาย     │   │ Fact Tables:             │   │
│  │ - รายงาน     │   │ - fact_accident_event    │   │
│  │ - แนวทาง     │   │ - fact_accident_person   │   │
│  │ - เอกสาร     │   │                          │   │
│  └──────────────┘   │ Dimension Tables:        │   │
│                     │ - dim_geography (83)     │   │
│  ┌──────────────┐   │ - dim_time (4,018)       │   │
│  │    MinIO     │   │ - dim_road_segment       │   │
│  │ (File Store) │   │                          │   │
│  │              │   │ Mart Tables:             │   │
│  │ - PDFs       │   │ - mart_accident_summary  │   │
│  │ - TXT files  │   │ - mart_accident_hotspot  │   │
│  │ - Documents  │   │ - mart_province_year     │   │
│  └──────────────┘   │                          │   │
│                     │ Evidence Tables:         │   │
│                     │ - evidence_registry      │   │
│                     │ - claim_evidence_link    │   │
│                     └──────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 🌐 API Endpoints

| Method | Path | คำอธิบาย |
|--------|------|----------|
| `GET` | `/api/health` | ตรวจสุขภาพระบบ (postgres / minio / pgvector) |
| `POST` | `/api/chat` | ส่งคำถามและรับคำตอบจาก Agent Pipeline |
| `POST` | `/api/ingest` | นำเข้าเอกสารจาก MinIO เข้า pgvector (`document_embeddings`) |
| `GET` | `/api/evidence/{id}` | ดูข้อมูล evidence item |
| `GET` | `/docs` | Swagger UI สำหรับ API |
| `GET` | `/static/test_ui.html` | Test UI หลัก |
| `GET` | `/static/citation_test_ui.html` | Citation & Evidence Test UI |

**Chat Request Format:**
```json
POST /api/chat
{
  "message": "สถิติอุบัติเหตุจังหวัดเชียงใหม่ ทุกปี 2020-2026",
  "session_id": null
}
```

**Chat Response Format:**
```json
{
  "content": "## รายงาน...\n\n...[C-001]...",
  "topic": "accident",
  "charts": [
    {
      "type": "bar",
      "title": "อุบัติเหตุเชียงใหม่ 2020-2026",
      "data": { "labels": [...], "datasets": [...] },
      "source_note": "ที่มา: ..."
    }
  ],
  "tables": [],
  "citations": [
    {
      "citation_code": "C-001",
      "source_type": "database",
      "source_ref": "fact_accident_event",
      "citation_text": "[C-001] ฐานข้อมูลอุบัติเหตุ, 2024"
    }
  ],
  "follow_ups": [
    "จุดเสี่ยงอุบัติเหตุในเชียงใหม่คือที่ไหนบ้าง?",
    "กลุ่มเสี่ยงหลักคือใคร?",
    "มาตรการใดได้ผลดีที่สุด?"
  ],
  "metadata": {
    "elapsed_seconds": 145.3,
    "agent_count": 7,
    "pipeline": "phase2_with_citation_evidence",
    "chart_count": 2,
    "citation_count": 3
  }
}
```

---

## 🖥️ Test UI (`/static/test_ui.html`)

Test UI เป็น Single-page HTML ที่ให้ทดสอบ Agent ผ่านเบราว์เซอร์โดยตรง

### หน้าจอและ Tabs

```
┌─────────────────────────────────────────────────────────────────┐
│  🟣 Musya Agent Test UI            [Health] [Chat] [Charts]     │
│                                             [Tools] [Data]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tab: Chat                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [Quick Questions]                                      │   │
│  │  สรุปสถานการณ์ปี 2024 | จุดเสี่ยง 10 อันดับ | ...       │   │
│  │                                                         │   │
│  │  ─── Agent Response ───                                 │   │
│  │  📄 Markdown Report                                     │   │
│  │  📊 Charts (Chart.js)                                   │   │
│  │  🔖 Citations [C-001] [C-002]                          │   │
│  │  💬 Follow-up suggestions                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [พิมพ์คำถาม...                              ] [ส่ง]           │
└─────────────────────────────────────────────────────────────────┘
```

### 4 Tabs หลัก

#### Tab 1: Chat
- **Quick Questions** — คำถามตัวอย่างคลิกเดียว
- **Message Bubble** — แสดงคำถามผู้ใช้และคำตอบ Agent
- **Chart Rendering** — แสดงกราฟจาก ChartSpec ผ่าน Chart.js อัตโนมัติ
- **Citation Badges** — แสดง citation codes ที่คลิกได้
- **Follow-ups** — คำถามแนะนำถัดไป

#### Tab 2: Charts
- แสดงกราฟทั้งหมดจาก session ปัจจุบันแบบ gallery

#### Tab 3: Tools
- ทดสอบ tool แต่ละตัวโดยตรง (get_accident_summary, get_hotspots, ฯลฯ)

#### Tab 4: Data
- แสดงภาพรวมข้อมูลในฐานข้อมูล (table row counts, schema info)

### Chart Rendering Flow (Frontend)

```
AgentResponse.charts (JSON array)
    │
    ▼
JavaScript: renderCharts(charts)
    │
    ├── toNumeric(v)  — แปลงค่าให้เป็นตัวเลข
    │
    ├── Chart.js: new Chart(canvas, {
    │       type: chartSpec.type,
    │       data: chartSpec.data,
    │       options: chartSpec.options
    │   })
    │
    └── แสดงผลใน .chart-card div
```

### ฟังก์ชันหลักใน JavaScript

| Function | คำอธิบาย |
|----------|----------|
| `handleSend(event)` | ส่ง message ไปยัง `/api/chat` |
| `sendQuick(msg)` | ส่ง quick question |
| `renderMessage(role, content, charts, citations, followUps)` | แสดงผลลัพธ์ |
| `renderCharts(charts)` | สร้างกราฟจาก ChartSpec |
| `checkHealth()` | ตรวจสอบ `/api/health` ทุก 30 วินาที |
| `switchTab(name)` | เปลี่ยน tab |
| `loadDataOverview()` | โหลดข้อมูล overview สำหรับ Data tab |
| `clearChat()` | ล้างประวัติแชท |

---

## ⏱️ ประสิทธิภาพและ Timing

| ขั้นตอน | เวลาโดยประมาณ |
|---------|--------------|
| Request Interpreter | 5-10 วินาที |
| Data Retrieval (tools) | 10-20 วินาที |
| SQL Specialist | 10-15 วินาที |
| Citation & Evidence | 10-15 วินาที |
| Accident Analyst | 15-20 วินาที |
| Chart Builder (tools) | 10-15 วินาที |
| Report Writer | 15-25 วินาที |
| **รวม Pipeline ทั้งหมด** | **~2-3 นาที** |

> **หมายเหตุ:** เวลาขึ้นอยู่กับความซับซ้อนของคำถาม จำนวน tools ที่ถูกเรียก และ latency ของ Gemini API

---

## 🔧 LLM Configuration

```python
# ใช้ gemini/gemini-2.0-flash ผ่าน CrewAI
llm = f"gemini/{settings.GEMINI_MODEL}"  # → "gemini/gemini-2.0-flash"

# CrewAI จะ route ผ่าน google-genai provider
# ต้องตั้งค่า environment variables:
# GEMINI_API_KEY=your_key
# GOOGLE_API_KEY=your_key  ← ต้องมีทั้งคู่
```

---

## 🚀 วิธีเริ่มระบบ

```powershell
# 1. เริ่ม Docker services
docker-compose up -d postgres minio

# 2. Activate Conda environment
conda activate musya-agent

# 3. เริ่ม Agent Server
C:\Users\baban\.conda\envs\musya-agent\python.exe -m uvicorn src.main:app --reload

# 4. ทดสอบ health
curl http://localhost:8000/api/health

# 5. Ingest เอกสาร (ครั้งแรก)
curl -X POST http://localhost:8000/api/ingest

# 6. เปิด Test UI
# http://localhost:8000/static/test_ui.html
# http://localhost:8000/static/citation_test_ui.html
```

---

## 📁 โครงสร้างไฟล์

```
Agent/
├── src/
│   ├── main.py                    ← FastAPI app + lifespan
│   ├── config.py                  ← Pydantic Settings
│   ├── agents/
│   │   ├── orchestrator.py        ← run_chat(), build_crew()
│   │   ├── request_interpreter.py ← Agent 1
│   │   ├── retrieval.py           ← Agent 2 + tools
│   │   ├── sql_specialist.py      ← Agent 3 + DB schema
│   │   ├── citation_evidence.py   ← Agent 4 + schemas
│   │   ├── analyst_accident.py    ← Agent 5
│   │   ├── chart_builder.py       ← Agent 6 + chart tools
│   │   └── report_writer.py       ← Agent 7
│   ├── routers/
│   │   ├── chat.py                ← POST /api/chat
│   │   ├── health.py              ← GET /api/health
│   │   ├── ingest.py              ← POST /api/ingest
│   │   └── evidence.py            ← GET /api/evidence/{id}
│   ├── tools/
│   │   ├── common.py              ← search_documents, geography tools
│   │   ├── accident.py            ← accident domain tools
│   │   └── chart_builder.py       ← chart data tools
│   ├── rag/
│   │   └── document_rag.py        ← pgvector search + ingestion (vector_store.py)
│   ├── db/
│   │   ├── pool.py                ← asyncpg + psycopg2 pools
│   │   └── minio_client.py        ← MinIO client
│   └── schemas/
│       ├── response.py            ← AgentResponse, ChartSpec, Citation
│       └── evidence.py            ← EvidenceItem, Claim, EvidenceContext
├── static/
│   ├── test_ui.html               ← Main Test UI (Chat+Charts+Tools+Data)
│   └── citation_test_ui.html      ← Citation & Evidence Test UI
├── database/
│   ├── 001_shared_core.sql        ← dim_geography, dim_time
│   ├── 002_document_rag.sql       ← document_registry, document_chunks
│   ├── 003_accident_domain.sql    ← fact_accident_event, fact_accident_person
│   └── 010_evidence_citation.sql  ← evidence_registry, claim_evidence_link
├── scripts/
│   ├── check_database.py          ← ตรวจสอบ DB connection + tables
│   ├── run_migrations.py          ← รัน SQL migrations
│   ├── prepare_sample_documents.py ← อัปโหลด sample docs สู่ MinIO
│   └── test_citation_setup.py     ← ทดสอบ Citation & Evidence setup
├── environment.yml                ← Conda environment
├── .env                           ← Environment variables (gitignored)
└── docker-compose.yml             ← PostgreSQL + MinIO containers
```

---

## 🔍 Logging & Debugging

ทุก agent step จะ log ออกมาใน terminal:

```
★★★★★★★★★★★★★★★★★
🚀 [CREW START] message: สถิติอุบัติเหตุเชียงใหม่...
   agents: Request Interpreter → Retrieval → SQL → Citation & Evidence → Analyst → Chart Builder → Report Writer
★★★★★★★★★★★★★★★★★

────────────────────────────────────────────────────
🤔 [AGENT THINKING]
  Thought  : ผู้ใช้ต้องการข้อมูลอุบัติเหตุในจังหวัดเชียงใหม่...
  Action   : get_province_year_summary
  Input    : {"province": "เชียงใหม่", "start_year": 2020}
────────────────────────────────────────────────────

════════════════════════════════════════════════════
🏁 [TASK COMPLETE] จากผลการตีความคำขอ...
  Result: {"accident_count": 1420, "death_count": 89...}
════════════════════════════════════════════════════
```

---

*Last updated: 2026-04-13 | Musya Agent Phase 2 (with Citation & Evidence)*
