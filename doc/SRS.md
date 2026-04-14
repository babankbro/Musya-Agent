# เอกสารข้อกำหนดความต้องการซอฟต์แวร์ (SRS)
# ระบบ Musya Agent — AI Backend สำหรับวิเคราะห์ข้อมูลสุขภาพ

> **เวอร์ชัน**: 2.0  
> **วันที่**: 2026-04-13  
> **มาตรฐานอ้างอิง**: IEEE 830-1998  
> **ขอบเขต**: Agent backend — ครอบคลุมความสามารถที่ย้ายมาจาก Chat- frontend

---

## 1. บทนำ

### 1.1 วัตถุประสงค์ของเอกสาร
เอกสารฉบับนี้ระบุข้อกำหนดความต้องการซอฟต์แวร์ (Software Requirements Specification) ของระบบ **Musya Agent** ซึ่งเป็น backend AI service ที่:
1. ให้บริการ 6-agent pipeline สำหรับวิเคราะห์ข้อมูลสุขภาพสาธารณะ
2. **รองรับความสามารถทั้งหมดจาก Chat- frontend** ที่ต้องย้ายมาเป็น backend service
3. ให้บริการ RAG (Document + Database) สำหรับ frontend ทุกเวอร์ชัน

### 1.2 ขอบเขตของระบบ
**ชื่อระบบ**: Musya Agent — AI Backend Service  
**ผู้สนับสนุน**: สำนักงานกองทุนสนับสนุนการสร้างเสริมสุขภาพ (สสส.)  
**จุดมุ่งหมาย**: ให้บริการ AI analysis backend ที่ frontend (Chat- หรือ ChatV1) สามารถเรียกใช้ได้ผ่าน REST API โดยไม่ต้องเรียก LLM โดยตรงจาก client

**ระบบจะทำสิ่งต่อไปนี้**:
- วิเคราะห์ข้อมูลอุบัติเหตุทางถนนด้วย AI Agent Pipeline (6 agents)
- ค้นหาข้อมูลจากเอกสาร (Document RAG) และฐานข้อมูล (Database RAG)
- สร้างรายงานภาษาไทยพร้อมกราฟ Chart.js และตาราง
- **รองรับ tool detection** — ตรวจจับเครื่องมือที่ผู้ใช้ต้องการ (เดิมอยู่ใน Chat- client-side)
- **รองรับ API planning** — วางแผนเรียก API ตามคำถาม (เดิมอยู่ใน Chat- client-side)
- **รองรับ file relevance selection** — เลือกเอกสารที่เกี่ยวข้อง (เดิมอยู่ใน Chat- client-side)
- **รองรับ domain queries** — NL→SQL สำหรับอุบัติเหตุ/เบาหวาน/สุขภาพจิต (เดิมอยู่ใน Chat- admin APIs)
- สร้างรายงาน DOCX ตามรูปแบบราชการไทย (อนาคต)
- Document ingestion จาก MinIO → pgvector (PostgreSQL `document_embeddings`)

**ระบบจะไม่ทำสิ่งต่อไปนี้**:
- ไม่จัดการ authentication/authorization (เป็นหน้าที่ของ frontend)
- ไม่ให้คำวินิจฉัยทางการแพทย์
- ไม่ประมวลผล real-time streaming sensor data

### 1.3 คำจำกัดความและคำย่อ

| คำย่อ | ความหมาย |
|-------|---------|
| **RAG** | Retrieval-Augmented Generation — AI ดึงข้อมูลจากแหล่งภายนอกก่อนตอบ |
| **CrewAI** | Python framework สำหรับ multi-agent AI orchestration |
| **ChartSpec** | JSON format ที่ Agent สร้างสำหรับ Chart.js rendering |
| **SSE** | Server-Sent Events — one-way streaming จาก server ไป client |
| **MinIO** | S3-compatible object storage สำหรับเก็บไฟล์เอกสาร |
| **pgvector** | PostgreSQL extension สำหรับเก็บ document embeddings (แทน ChromaDB) |
| **APA** | American Psychological Association — มาตรฐานการอ้างอิงวิชาการ |
| **Mart** | Pre-aggregated database table สำหรับ fast analytics |
| **LLM** | Large Language Model (Google Gemini) |
| **NL→SQL** | Natural Language to SQL — แปลภาษาธรรมชาติเป็น SQL query |

### 1.4 เอกสารอ้างอิง
- `Agent/doc/ARCHITECTURE.md` — สถาปัตยกรรมระบบ Agent
- `Agent/doc/DATABASE_API.md` — ฐานข้อมูลและ API reference
- `Agent/doc/PROJECT_DOCUMENTATION.md` — เอกสารโปรเจกต์
- `Chat-/doc/SRS.md` — SRS ของระบบรวม (reference)
- `Chat-/doc/ARCHITECTURE.md` — สถาปัตยกรรมรวมทั้งระบบ (reference)

---

## 2. คำอธิบายทั่วไป

### 2.1 มุมมองผลิตภัณฑ์
Musya Agent เป็น backend AI service ที่ออกแบบให้ frontend เรียกใช้ผ่าน REST API:

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Chat- / ChatV1)              │
│                    Next.js — port 3000                    │
│                                                           │
│  เดิม: เรียก Gemini โดยตรง     ใหม่: เรียก Agent backend  │
│  (client-side, ไม่ปลอดภัย)     (server-side, ปลอดภัย)     │
└───────────────────────┬─────────────────────────────────┘
                        │  REST API (port 8000)
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   Musya Agent Backend                     │
│                   FastAPI — port 8000                     │
│                                                           │
│  ┌────────────┐ ┌────────────┐ ┌───────────────────────┐ │
│  │ Chat API   │ │ AI Utility │ │ Agent Pipeline        │ │
│  │ (analysis) │ │ APIs       │ │ (6-agent CrewAI)      │ │
│  │            │ │ (detect,   │ │                       │ │
│  │ POST /chat │ │ plan, etc.)│ │ Request→Retrieve→SQL  │ │
│  └────────────┘ └────────────┘ │ →Analyze→Chart→Report │ │
│                                 └───────────────────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌───────────────────────┐ │
│  │ PostgreSQL │ │ pgvector   │ │ MinIO                 │ │
│  │ (data)     │ │ (vectors)  │ │ (documents)           │ │
│  └────────────┘ └────────────┘ └───────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 2.2 ฟังก์ชันหลักของระบบ

```
┌─────────────────────────────────────────────────────────────┐
│                    Musya Agent Backend                        │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ ★ AI Agent       │  │ ★ AI Utility Services            │ │
│  │   Pipeline       │  │   (ย้ายจาก Chat- client-side)     │ │
│  │   (6 agents)     │  │   • Tool Detection               │ │
│  │                  │  │   • API Planning                  │ │
│  │                  │  │   • File Relevance Selection      │ │
│  │                  │  │   • SQL Generation (NL→SQL)       │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ ★ Document RAG   │  │ ★ Domain Query Service           │ │
│  │   (pgvector +    │  │   (ย้ายจาก Chat- /api/admin/*)    │ │
│  │    MinIO ingest) │  │   • อุบัติเหตุ (accident)         │ │
│  │                  │  │   • เบาหวาน (diabetes)            │ │
│  └──────────────────┘  │   • สุขภาพจิต (mental)            │ │
│                        └──────────────────────────────────┘ │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ ★ Health Check   │  │ ★ Report Engine (อนาคต)          │ │
│  │   & Monitoring   │  │   • DOCX generation              │ │
│  │                  │  │   • PDF generation                │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 ลักษณะผู้ใช้งาน (Consumer ของ Agent API)

| Consumer | คำอธิบาย | API ที่ใช้ |
|----------|---------|-----------|
| **Chat- Frontend** | Frontend หลัก ที่เรียก Agent ผ่าน proxy | `/api/chat`, `/api/ai/*` |
| **ChatV1 Frontend** | Legacy frontend ที่มี Agent Mode | `/api/chat`, `/api/agent/chat` proxy |
| **Admin Panel** | หน้า admin สำหรับ domain queries | `/api/domain/*` |
| **External System** | ระบบภายนอกที่ต้องการ AI analysis | `/api/chat`, `/api/ingest` |

### 2.4 ข้อจำกัดทั่วไป
- ต้องใช้ Google Gemini API key (external dependency)
- AI Agent Pipeline ใช้เวลา 30-60 วินาทีต่อ request
- ข้อมูลอุบัติเหตุจำกัดเฉพาะปี 2020-2026
- CrewAI tools ทำงานแบบ synchronous (ใช้ psycopg2 pool)
- ภาษาหลัก: ไทย (prompts, reports, error messages)

### 2.5 สมมติฐานและข้อพึ่งพิง
- Frontend จัดการ authentication/authorization
- PostgreSQL, MinIO ทำงานตลอดเวลา
- Google Gemini API มี uptime สูง
- Frontend เข้าถึง Agent ผ่าน CORS-allowed origins เท่านั้น

---

## 3. ความต้องการเชิงหน้าที่ (Functional Requirements)

### 3.1 ระบบ AI Agent Pipeline (ปัจจุบัน ✅)

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ |
|----|------------|---------------|-------|
| **FR-AGT-01** | 6-agent sequential pipeline (Request Interpreter → Retrieval → SQL → Analyst → Chart → Report) | Must | ✅ ใช้งานได้ |
| **FR-AGT-02** | Document RAG — ค้นหาเอกสารจาก pgvector (PostgreSQL `document_embeddings`) | Must | ✅ ใช้งานได้ |
| **FR-AGT-03** | Database RAG — query ข้อมูลจาก PostgreSQL mart tables | Must | ✅ ใช้งานได้ |
| **FR-AGT-04** | Custom SQL query execution (read-only, SELECT/WITH only, auto LIMIT 1000) | Must | ✅ ใช้งานได้ |
| **FR-AGT-05** | สร้าง ChartSpec JSON ที่ compatible กับ frontend ChartRenderer | Must | ✅ ใช้งานได้ |
| **FR-AGT-06** | เขียนรายงานภาษาไทย Markdown ตามโครงสร้างราชการ | Must | ✅ ใช้งานได้ |
| **FR-AGT-07** | SSE streaming สำหรับ real-time response | Should | ✅ ใช้งานได้ |
| **FR-AGT-08** | Document ingestion จาก MinIO → pgvector (`document_embeddings`) | Must | ✅ ใช้งานได้ |
| **FR-AGT-09** | Health check endpoint (PostgreSQL + MinIO + pgvector status) | Must | ✅ ใช้งานได้ |

**รายละเอียด FR-AGT-01 (6-Agent Pipeline)**:
```
User Message → POST /api/chat
  → Agent 1: Request Interpreter (ตีความ → JSON: topics, geography, time_range)
  → Agent 2: Data Retrieval (10 tools: search_documents, get_accident_*, get_province_*)
  → Agent 3: SQL Specialist (execute_custom_sql, explain_schema — SELECT/WITH only)
  → Agent 4: Accident Analyst (วิเคราะห์ key findings, trends, risk areas)
  → Agent 5: Chart Builder (7 tools: build_*_chart → ChartSpec JSON)
  → Agent 6: Report Writer (Markdown ภาษาไทย: สรุป→สถานการณ์→ข้อค้นพบ→เสี่ยง→มาตรการ→ข้อจำกัด→คำถาม)
  → AgentResponse {content, charts, tables, citations, follow_ups, metadata}
```

---

### 3.2 ระบบ Citation & Evidence (Phase 2A 🆕)

Citation & Evidence Agent เป็น trust layer ที่แปลงผล retrieval ให้เป็นหลักฐานที่ตรวจสอบย้อนกลับได้ พร้อมสร้าง citation, source note และ reference list

> **รายละเอียดเต็ม**: ดู `Agent/doc/CITATION_EVIDENCE_AGENT.md`

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ |
|----|------------|---------------|-------|
| **FR-CIT-01** | Normalize evidence จากทุกแหล่ง (document, database, API) เป็น EvidenceItem กลาง | Must | 📋 วางแผน |
| **FR-CIT-02** | ลงทะเบียน evidence ใน evidence_registry พร้อม provenance metadata | Must | 📋 วางแผน |
| **FR-CIT-03** | Map claim กับ evidence (supported/partially/insufficient/conflicting) | Must | 📋 วางแผน |
| **FR-CIT-04** | สร้าง citation_code (C-001) + display citation_text + bibliography_text | Must | 📋 วางแผน |
| **FR-CIT-05** | เติม source_note ให้ ChartSpec/TableSpec อัตโนมัติจาก evidence | Must | 📋 วางแผน |
| **FR-CIT-06** | Coverage validation — ตรวจว่า numeric claims ทุกข้อมี citation | Should | 📋 วางแผน |
| **FR-CIT-07** | open_url contract — คลิกกลับไปเอกสารต้นฉบับได้ (NotebookLM-style) | Should | 📋 วางแผน |
| **FR-CIT-08** | Reference list ท้ายรายงาน — เฉพาะ evidence ที่ถูกใช้จริง | Must | 📋 วางแผน |

**รายละเอียด FR-CIT-01 (Evidence Normalization)**:
- **Input**: ผลจาก Retrieval Agent (document chunks + DB query results + API responses)
- **Output**: `EvidenceItem[]` ที่มี evidence_id, source_ref, title, page_ref, section_label, trust_level, open_url
- **Acceptance Criteria**: ทุก evidence ชิ้นมี unique evidence_id (EV-NNN) และ trust_level (high/medium/low)

**รายละเอียด FR-CIT-07 (open_url Contract)**:
- **Document evidence**: `open_url = /api/documents/open/{doc_id}?page={n}`
- **Database evidence**: `open_url = /api/evidence/{ev_id}/query` (แสดง SQL + results)
- **API evidence**: `open_url = original API URL`
- **Frontend**: คลิก `[C-001]` ในรายงาน → เปิด source ตาม open_url

---

### 3.3 ระบบ AI Utility Services (ย้ายจาก Chat- ⬆️)

ความสามารถเหล่านี้ปัจจุบันอยู่ใน Chat- client-side (เรียก Gemini โดยตรงจาก browser) ซึ่งมีปัญหาด้าน security (API key exposure) — ต้องย้ายมาเป็น Agent backend API

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ | แหล่งเดิม (Chat-) |
|----|------------|---------------|-------|--------------------|
| **FR-UTL-01** | Tool Detection — ตรวจจับเครื่องมือ AI จากข้อความผู้ใช้ | Must | 🔄 ต้องย้าย | `ChatInterface.tsx → aiDetectTool()` |
| **FR-UTL-02** | API Planning — วางแผนเรียก domain API ตามคำถาม | Must | 🔄 ต้องย้าย | `ChatInterface.tsx → aiPlanAdminApiCalls()` |
| **FR-UTL-03** | File Relevance Selection — เลือกเอกสารที่เกี่ยวข้องจาก APA metadata | Should | 🔄 ต้องย้าย | `ChatInterface.tsx → searchRelevantFiles()` |
| **FR-UTL-04** | SQL Generation (NL→SQL) — แปลภาษาธรรมชาติเป็น SQL | Must | 🔄 ต้องย้าย | `Chat-/app/api/admin/accident` etc. |
| **FR-UTL-05** | APA Metadata Extraction — สกัด metadata จากเอกสาร | Should | 🔄 ต้องย้าย | `Chat-/app/api/files → extractAPA()` |
| **FR-UTL-06** | Text Summarization — สรุปเนื้อหาเอกสาร | Should | 🔄 ต้องย้าย | `Chat-/app/api/admin/chatweather` |

**รายละเอียด FR-UTL-01 (Tool Detection)**:

เดิมใน Chat-:
```javascript
// Chat-/app/components/chat/ChatInterface.tsx (client-side)
const tool = await aiDetectTool(userText);
// เรียก Gemini Flash โดยตรงจาก browser → ⚠️ API key exposed
```

ย้ายมา Agent:
```
POST /api/ai/detect-tool
Request:  {"text": "สร้างกราฟอุบัติเหตุเชียงใหม่"}
Response: {"tool": "สร้างกราฟ"}
```

**เครื่องมือที่ต้องตรวจจับ** (จาก Chat- 12 prompts):

| เครื่องมือ | Prompt Template (Chat-) | คำอธิบาย |
|-----------|-------------------------|---------|
| `เขียนแผนงาน` | PROMPT_PLAN | สร้างแผนงานสุขภาพ |
| `สร้างกราฟ` | PROMPT_CHART_DOC | สร้างกราฟจากเอกสาร |
| `สรุปเอกสาร` | PROMPT_SUMMARY | สรุปเนื้อหาเอกสาร |
| `ปรึกษาผู้เชี่ยวชาญ` | PROMPT_CONSULT | ปรึกษาด้านสุขภาพ |
| `เปรียบเทียบข้อมูล` | PROMPT_COMPARE | เปรียบเทียบข้อมูลสุขภาพ |
| `ค้นหาข้อมูล` | PROMPT_SEARCH | ค้นหาข้อมูลจากฐานข้อมูล |
| `วิจัยเชิงลึก` | PROMPT_DEEPRESEARCH | Deep research (ใหม่จาก Chat-) |
| `อ่านขั้นตอน` | PROMPT_STEP_READ | Step-by-step reading (ใหม่จาก Chat-) |
| `บทความ` | PROMPT_A | Article template (ใหม่จาก Chat-) |
| `เฝ้าระวังโรค` | PROMPT_B | Disease surveillance (ใหม่จาก Chat-) |
| `สถานการณ์` | PROMPT_C | Situation report (ใหม่จาก Chat-) |
| (normal chat) | PROMPT_CHAT | สนทนาทั่วไป |

**รายละเอียด FR-UTL-02 (API Planning)**:

เดิมใน Chat-:
```javascript
// Chat-/app/components/chat/ChatInterface.tsx (client-side)
const plans = await aiPlanAdminApiCalls(userText);
// → {useAccident: true, accidentMessage: "...", useDiabetes: false, ...}
```

ย้ายมา Agent:
```
POST /api/ai/plan-apis
Request:  {"text": "สถิติอุบัติเหตุเชียงใหม่กับสมุทรปราการ"}
Response: {
  "useAccident": true, "accidentMessage": "เปรียบเทียบเชียงใหม่กับสมุทรปราการ",
  "useDiabetes": false, "useMental": false,
  "useWeather": false, "useThaijo": false
}
```

---

### 3.3 ระบบ Domain Query Service (ย้ายจาก Chat- admin APIs ⬆️)

ความสามารถเหล่านี้ปัจจุบันอยู่ใน Chat- `/api/admin/*` — NL→SQL queries ที่ Gemini แปลภาษาธรรมชาติเป็น SQL แล้วรัน

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ | แหล่งเดิม (Chat-) |
|----|------------|---------------|-------|--------------------|
| **FR-DOM-01** | Accident Domain Query (NL→SQL→Results) | Must | 🔄 ต้องย้าย | `POST /api/admin/accident` |
| **FR-DOM-02** | Diabetes Domain Query (NL→SQL→Results) | Should | 🔄 ต้องย้าย | `POST /api/admin/diabetes` |
| **FR-DOM-03** | Mental Health Domain Query (dynamic table detection) | Should | 🔄 ต้องย้าย | `POST /api/admin/mental` |
| **FR-DOM-04** | Generic Table Query (list/read/search + pagination) | Should | 🔄 ต้องย้าย | `GET/POST /api/admin/db-table` |
| **FR-DOM-05** | CSV Import (auto-create table, type coercion, batch insert) | Should | 🔄 ต้องย้าย | `POST /api/admin/csv-import` |

**รายละเอียด FR-DOM-01 (Accident Domain Query)**:

เดิมใน Chat-:
```
POST /api/admin/accident
Request:  {"message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025"}
Process:
  1. Gemini generates SQL from NL + hardcoded accident table schema
  2. Execute SQL on PostgreSQL (⚠️ ไม่มี readonly pool)
  3. Gemini summarizes results in Thai
Response: {"sql": "SELECT ...", "reply": "สรุป...", "total": 120, "rows": [...]}
```

ย้ายมา Agent (ปรับปรุง):
```
POST /api/domain/accident
Request:  {"message": "สถิติอุบัติเหตุเชียงใหม่ปี 2025"}
Process:
  1. Gemini generates SQL from NL + full schema knowledge (Agent มี dim/fact/mart)
  2. ✅ Execute SQL via readonly pool + SELECT/WITH validation
  3. ✅ ใช้ Agent's mart tables (denormalized, faster)
  4. Gemini summarizes results in Thai
  5. ✅ Optionally generate ChartSpec for visualization
Response: {"sql": "...", "reply": "...", "total": 120, "rows": [...], "chart": {...}}
```

---

### 3.4 ระบบ Document & Storage (ย้ายจาก Chat- ⬆️)

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ | แหล่งเดิม (Chat-) |
|----|------------|---------------|-------|--------------------|
| **FR-DOC-01** | Document Ingestion (MinIO → extract → chunk → pgvector) | Must | ✅ ใช้งานได้ | `POST /api/ingest` (Agent) |
| **FR-DOC-02** | Document Search (semantic search via pgvector cosine similarity) | Must | ✅ ใช้งานได้ | `search_documents` tool |
| **FR-DOC-03** | APA Metadata Extraction จากเอกสาร | Should | 🔄 ต้องย้าย | `Chat-/app/api/files/apa` |
| **FR-DOC-04** | Bulk APA Regeneration (หลายไฟล์พร้อมกัน) | Could | 🔄 ต้องย้าย | `Chat-/app/api/files/apa/bulk` |

---

### 3.5 ระบบ Weather & External Data (ย้ายจาก Chat- ⬆️)

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ | แหล่งเดิม (Chat-) |
|----|------------|---------------|-------|--------------------|
| **FR-EXT-01** | พยากรณ์อากาศ (Open-Meteo API) + AI สรุป | Could | 🔄 ต้องย้าย | `Chat-/app/api/weather`, `/api/admin/chatweather` |
| **FR-EXT-02** | ThaiJO วารสารวิชาการ (proxy search) | Could | 🔄 ต้องย้าย | `Chat-/app/api/admin/thaijo` |

---

### 3.6 ระบบ Report Engine (อนาคต 🆕)

| ID | ความต้องการ | ลำดับความสำคัญ | สถานะ |
|----|------------|---------------|-------|
| **FR-RPT-01** | สร้าง DOCX ตามรูปแบบราชการไทย (TH Sarabun, หัวข้อราชการ) | Should | 📋 วางแผน |
| **FR-RPT-02** | สร้าง PDF จาก report content | Could | 📋 วางแผน |
| **FR-RPT-03** | Template-based report generation | Could | 📋 วางแผน |

---

## 4. ความต้องการเชิงไม่ใช่หน้าที่ (Non-Functional Requirements)

### 4.1 ด้านประสิทธิภาพ (Performance)

| ID | ความต้องการ | เป้าหมาย |
|----|------------|---------|
| **NFR-PERF-01** | Agent Pipeline response time (6-agent) | Complete response < 60 วินาที |
| **NFR-PERF-02** | SSE streaming first token | < 5 วินาที |
| **NFR-PERF-03** | AI Utility API response (detect-tool, plan-apis) | < 3 วินาที |
| **NFR-PERF-04** | Domain query (NL→SQL→results) | < 10 วินาที |
| **NFR-PERF-05** | Database query on mart tables | < 100ms |
| **NFR-PERF-06** | Document ingestion (per file) | < 30 วินาที |
| **NFR-PERF-07** | Health check response | < 500ms |

### 4.2 ด้านความปลอดภัย (Security)

| ID | ความต้องการ | วิธีการ | สถานะ |
|----|------------|--------|-------|
| **NFR-SEC-01** | SQL injection prevention | Parameterized queries ($1, $2) | ✅ |
| **NFR-SEC-02** | AI-generated SQL safety | SELECT/WITH only + LIMIT 1000 | ✅ |
| **NFR-SEC-03** | CORS configuration | Configurable allowed origins | ✅ |
| **NFR-SEC-04** | API key protection | Server-side only (ไม่ส่งไป client) | ✅ |
| **NFR-SEC-05** | Readonly DB pool สำหรับ AI-generated SQL | แยก pool (เดิม Chat- ไม่มี ⚠️) | ✅ |
| **NFR-SEC-06** | Request validation | Pydantic models | ✅ |

> **ข้อได้เปรียบจากการย้ายมา Agent**: Chat- เรียก Gemini API โดยตรงจาก client → API key ถูก expose ใน browser DevTools | Agent เรียก Gemini จาก server → API key ปลอดภัย

### 4.3 ด้านความพร้อมใช้งาน (Availability)

| ID | ความต้องการ | วิธีการ |
|----|------------|--------|
| **NFR-AVL-01** | Docker Compose deployment | ✅ docker-compose.yml |
| **NFR-AVL-02** | Health check endpoints | ✅ GET /api/health (DB + MinIO + pgvector) |
| **NFR-AVL-03** | Graceful shutdown | ✅ Lifespan handler closes pools |
| **NFR-AVL-04** | Connection pool management | ✅ asyncpg (2-10) + psycopg2 (1-5) |

### 4.4 ด้านรองรับการขยาย (Scalability)

| ID | ความต้องการ | วิธีการ |
|----|------------|--------|
| **NFR-SCL-01** | Phase-based domain expansion | ✅ Migration-based schema |
| **NFR-SCL-02** | Multi-domain agent tools | ✅ Pluggable tool architecture |
| **NFR-SCL-03** | Connection pooling | ✅ แยก async/sync pools |
| **NFR-SCL-04** | Horizontal scaling (อนาคต) | Docker + load balancer |

### 4.5 ด้านการบำรุงรักษา (Maintainability)

| ID | ความต้องการ | วิธีการ |
|----|------------|--------|
| **NFR-MNT-01** | Modular agent architecture | ✅ แยก file per agent + tool |
| **NFR-MNT-02** | Config management | ✅ Pydantic Settings + .env |
| **NFR-MNT-03** | Test suite | ✅ pytest (API + tools + schemas) |
| **NFR-MNT-04** | Structured logging | ✅ Python logging + step callbacks |
| **NFR-MNT-05** | API documentation | ✅ FastAPI Swagger auto-docs |

---

## 5. ขอบเขตรายเฟส (Phase Scope)

### Phase 1: อุบัติเหตุทางถนน ✅ ดำเนินการแล้ว

**ขอบเขตข้อมูล**:
- ข้อมูลอุบัติเหตุทางถนน ปี 2020-2026
- 77 จังหวัดทั่วประเทศ
- Star schema: fact_accident_event + dim tables + mart tables

**ฟีเจอร์ที่พร้อม**:
- ✅ 6-agent pipeline
- ✅ 7 chart tools + 7 data tools + 3 SQL tools
- ✅ Document RAG (pgvector — PostgreSQL native)
- ✅ SSE streaming
- ✅ Health check

### Phase 2: ย้ายความสามารถจาก Chat- 🔄 กำลังดำเนินการ

**สิ่งที่ต้องย้าย** (จาก Chat- client-side → Agent backend):

| ความสามารถ | Chat- Source | Agent Target | ข้อดีที่ได้ |
|-----------|-------------|--------------|------------|
| Tool Detection | `aiDetectTool()` (client) | `POST /api/ai/detect-tool` | API key ปลอดภัย |
| API Planning | `aiPlanAdminApiCalls()` (client) | `POST /api/ai/plan-apis` | API key ปลอดภัย |
| File Selection | `searchRelevantFiles()` (client) | `POST /api/ai/select-files` | API key ปลอดภัย |
| Accident Query | `POST /api/admin/accident` | `POST /api/domain/accident` | ใช้ mart tables + readonly pool |
| Diabetes Query | `POST /api/admin/diabetes` | `POST /api/domain/diabetes` | ใช้ readonly pool |
| Mental Query | `POST /api/admin/mental` | `POST /api/domain/mental` | ใช้ readonly pool |
| Weather | `GET /api/weather` | `GET /api/external/weather` | Centralized |
| ThaiJO | `POST /api/admin/thaijo` | `POST /api/external/thaijo` | Centralized |
| APA Extract | `POST /api/files/apa` | `POST /api/document/extract-apa` | Centralized |
| 12 Prompts (.js) | `app/components/chat/prompts/*` | `src/prompts/*.py` | Version-controlled |

### Phase 3: สุขภาพจิต (วางแผน)
- สร้าง dimension + fact tables สำหรับสุขภาพจิต
- เพิ่ม Agent tools สำหรับ mental health domain
- สร้าง mart tables สำหรับ aggregation

### Phase 4: โภชนาการ/โรคเรื้อรัง (วางแผน)
- สร้าง star schema สำหรับ diabetes/nutrition domain
- เพิ่ม Agent tools + chart tools
- สร้าง mart tables

### Phase 5: Report Engine (วางแผน)
- DOCX generation ตามรูปแบบราชการไทย
- PDF generation
- Template management

---

## 6. Feature Parity: Chat- vs Agent

ตารางเปรียบเทียบความสามารถ Chat- (เดิม) กับ Agent (ใหม่):

| Feature | Chat- (client-side) | Agent (server-side) | Action |
|---------|---------------------|---------------------|--------|
| Gemini Chat (streaming) | ✅ Direct Gemini API | ✅ SSE streaming | — |
| 6-Agent Pipeline | ❌ | ✅ CrewAI sequential | — |
| Tool Detection | ✅ client-side Gemini Flash | 🔄 ต้องย้ายมา | `POST /api/ai/detect-tool` |
| API Planning | ✅ client-side Gemini Flash | 🔄 ต้องย้ายมา | `POST /api/ai/plan-apis` |
| File Relevance | ✅ client-side Gemini Flash | 🔄 ต้องย้ายมา | `POST /api/ai/select-files` |
| Accident NL→SQL | ✅ server-side (ไม่มี validation) | 🔄 ต้องปรับปรุง | ใช้ readonly pool + mart tables |
| Diabetes NL→SQL | ✅ server-side | 🔄 ต้องย้ายมา | — |
| Mental NL→SQL | ✅ server-side (dynamic table) | 🔄 ต้องย้ายมา | — |
| Document RAG | ❌ | ✅ pgvector | — |
| Chart Generation | ❌ (Gemini outputs JSON inline) | ✅ 7 chart tools → ChartSpec | — |
| 12 Prompt Templates | ✅ (.js files) | 🔄 ต้องย้ายมา (.py) | Convert JS→Python |
| APA Extraction | ✅ server-side | 🔄 ต้องย้ายมา | — |
| Weather (Open-Meteo) | ✅ server-side | 🔄 ต้องย้ายมา | — |
| ThaiJO Search | ✅ server-side | 🔄 ต้องย้ายมา | — |
| Map Rendering | ✅ Leaflet (frontend only) | N/A | Frontend responsibility |
| DOCX Export | ✅ docx library (frontend) | 📋 วางแผน | Move to server-side |
| PDF Export | ✅ jspdf (frontend) | 📋 วางแผน | Move to server-side |
| CSV Import | ✅ server-side | 🔄 ต้องย้ายมา | — |
| SQL Safety (readonly pool) | ❌ | ✅ | Improvement |
| API Key Protection | ❌ (exposed in browser) | ✅ (server-side only) | Improvement |

---

## 7. Traceability Matrix

### FR → API Endpoint → Source File

| FR ID | Target API Endpoint (Agent) | Source File (Agent) | Source File (Chat- เดิม) |
|-------|---------------------------|--------------------|-----------------------|
| FR-AGT-01 | `POST /api/chat` | `src/routers/chat.py` → `src/agents/orchestrator.py` | — |
| FR-AGT-02 | (internal) | `src/rag/document_rag.py` → `src/rag/vector_store.py` | — |
| FR-AGT-04 | (internal) | `src/tools/sql_tools.py` | — |
| FR-AGT-05 | (internal) | `src/tools/chart_builder.py` | — |
| FR-AGT-07 | `POST /api/chat/stream` | `src/routers/chat.py` | — |
| FR-AGT-08 | `POST /api/ingest` | `src/routers/ingest.py` | — |
| FR-AGT-09 | `GET /api/health` | `src/routers/health.py` | — |
| FR-UTL-01 | `POST /api/ai/detect-tool` | (ต้องสร้าง) | `ChatInterface.tsx → aiDetectTool()` |
| FR-UTL-02 | `POST /api/ai/plan-apis` | (ต้องสร้าง) | `ChatInterface.tsx → aiPlanAdminApiCalls()` |
| FR-UTL-03 | `POST /api/ai/select-files` | (ต้องสร้าง) | `ChatInterface.tsx → searchRelevantFiles()` |
| FR-UTL-04 | `POST /api/domain/query` | (ต้องสร้าง) | `app/api/admin/accident/route.ts` |
| FR-DOM-01 | `POST /api/domain/accident` | (ต้องสร้าง) | `app/api/admin/accident/route.ts` |
| FR-DOM-02 | `POST /api/domain/diabetes` | (ต้องสร้าง) | `app/api/admin/diabetes/route.ts` |
| FR-DOM-03 | `POST /api/domain/mental` | (ต้องสร้าง) | `app/api/admin/mental/route.ts` |
| FR-DOM-05 | `POST /api/domain/csv-import` | (ต้องสร้าง) | `app/api/admin/csv-import/route.ts` |
| FR-DOC-03 | `POST /api/document/extract-apa` | (ต้องสร้าง) | `app/api/files/apa/route.ts` |
| FR-EXT-01 | `GET /api/external/weather` | (ต้องสร้าง) | `app/api/weather/route.ts` |
| FR-EXT-02 | `POST /api/external/thaijo` | (ต้องสร้าง) | `app/api/admin/thaijo/route.ts` |

---

## 8. ภาคผนวก

### A. Security Improvement Summary (Chat- → Agent)

| ปัญหาใน Chat- | แก้ไขใน Agent |
|---------------|--------------|
| API key exposed ใน browser (client-side Gemini calls) | ✅ เรียก Gemini จาก server-side เท่านั้น |
| AI-generated SQL ไม่ validate ก่อนรัน | ✅ SELECT/WITH only + LIMIT 1000 + readonly pool |
| ไม่มี readonly DB pool สำหรับ AI queries | ✅ แยก sync pool (psycopg2) สำหรับ tools |
| Pool ถูก instantiate ใหม่ทุก route (15 copies) | ✅ Singleton pools (lifespan managed) |

### B. Prompt Migration Guide (Chat- JS → Agent Python)

```
Chat- (JavaScript .js files)          Agent (Python .py files)
─────────────────────────             ─────────────────────────
app/components/chat/prompts/          src/prompts/
├── promptchat.js            →        ├── prompt_chat.py
├── promptplan.js            →        ├── prompt_plan.py
├── promptsearch.js          →        ├── prompt_search.py
├── promptsummary.js         →        ├── prompt_summary.py
├── promptconsult.js         →        ├── prompt_consult.py
├── promptcompare.js         →        ├── prompt_compare.py
├── promptchart_doc.js       →        ├── prompt_chart.py
├── prompta.js               →        ├── prompt_article.py
├── promptb.js               →        ├── prompt_disease_surveillance.py
├── promptc.js               →        ├── prompt_situation.py
├── promptdeepresearch.js    →        ├── prompt_deep_research.py
└── promptstepRead.js        →        └── prompt_step_read.py

⚠️ ใช้ .replace() ไม่ใช่ .format() เพราะ JSON curly braces
```

### C. Data Dictionary สรุป (ดูรายละเอียดเต็มใน DATABASE_API.md)

| กลุ่ม | ตาราง | เจ้าของ |
|-------|-------|---------|
| **Application** | users, chat_sessions, chat_messages, planning_history, file_apa_metadata | Chat-/ChatV1 |
| **Dimension** | dim_geography, dim_time, dim_road_segment, dim_source, dim_population_group, dim_facility | Agent |
| **Fact** | fact_accident_event, fact_accident_person | Agent |
| **Mart** | mart_accident_summary, mart_accident_hotspot, mart_province_year, mart_province_road | Agent |
| **Document RAG** | document_registry, document_chunks, indicator_catalog | Agent |
| **Domain Data** | accident (Thai cols), diabetes, bipola | Chat- (CSV import) |
