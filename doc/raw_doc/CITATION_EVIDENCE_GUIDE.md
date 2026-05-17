# Citation & Evidence Agent — คู่มืออธิบายการทำงานและ Test UI

> อธิบาย Citation & Evidence Agent (Agent 4 ใน pipeline), การทำงานของ `citation_test_ui.html`,
> และความสัมพันธ์กับ workflow หลักใน [AGENT_WORKFLOW_UNIFIED.md](./AGENT_WORKFLOW_UNIFIED.md)

---

## 1. Citation & Evidence Agent คืออะไร?

Citation & Evidence Agent คือ **"ชั้นตรวจสอบความน่าเชื่อถือ" (Trust Layer)** ที่อยู่กลาง Pipeline  
ทำหน้าที่รับผลลัพธ์จาก Agent ที่ดึงข้อมูล (Agent 2 + 3) แล้วแปลงให้เป็นหลักฐานที่ตรวจสอบย้อนกลับได้  
ก่อนส่งต่อให้ Agent ที่วิเคราะห์และเขียนรายงาน (Agent 5–9)

### ปัญหาที่แก้ได้

| ปัญหา | ก่อนมี Agent นี้ | หลังมี Agent นี้ |
|-------|----------------|----------------|
| **Hallucination** | ข้อสรุปอาจไม่มีหลักฐานรองรับ | ทุก claim ต้องผูกกับ evidence |
| **ไม่มี citation** | `citations: []` เสมอ | สร้าง C-001, C-002, ... อัตโนมัติ |
| **กราฟไม่มีแหล่งที่มา** | `source_note` ว่างเปล่า | เติม source_note จาก evidence อัตโนมัติ |
| **ตรวจสอบย้อนกลับไม่ได้** | ไม่รู้ว่าข้อมูลมาจากไหน | มี `open_url` คลิกดูเอกสารต้นฉบับได้ |

---

## 2. ตำแหน่งใน Agent Pipeline

```
User Message
     │
     ▼
[Agent 1] Request Interpreter        → แปลความคำขอ
     │
     ▼
[Agent 2] Data Retrieval Specialist  → ค้นข้อมูล (pgvector + DB tools)
     │
     ▼
[Agent 3] SQL Specialist             → custom SQL query
     │
     ▼
╔═══════════════════════════════════════╗
║ [Agent 4] Citation & Evidence Agent   ║  ← อยู่ตรงนี้
║                                       ║
║  INPUT:  ผลจาก Agent 2 + Agent 3      ║
║  PROCESS: normalize → register →      ║
║           map claims → cite → check   ║
║  OUTPUT: EvidenceContext              ║
╚═══════════════════════════════════════╝
     │
     ▼
[Agent 5] Accident Data Analyst      → วิเคราะห์จาก EvidenceContext, Haddon Matrix
     │
     ▼
[Agent 6] Chart Builder              → สร้างกราฟ + source_note จาก evidence
     │
     ▼
[Agent 7] Research Synthesizer       → narrative prose (1,200-2,000 คำ)
     │
     ▼
[Agent 8] Deep Analyst               → root cause, policy gaps (1,000-1,500 คำ)
     │
     ▼
[Agent 9] Report Composer            → เขียนรายงาน + inline [C-001] + references (2,000-4,000 คำ)
     │
     ▼
AgentResponse → Frontend (Test UI)
```

---

## 3. กระบวนการภายใน 5 ขั้นตอน

### ขั้นที่ 1 — Normalize Evidence

รับข้อมูลดิบจาก Agent 2 และ 3 แล้วแปลงให้เป็น `EvidenceItem` รูปแบบเดียวกัน

```
ข้อมูลดิบ (string จาก tools)              →    EvidenceItem (structured)
─────────────────────────────────────────────────────────────────────
"source: road_safety.pdf, chunk: 3 ..."  →    evidence_id = "EV-001"
                                               evidence_type = "document"
                                               source_ref = "road_safety.pdf"
                                               page_ref = "12"
                                               trust_level = "high"
                                               open_url = "/api/documents/open/42?page=12"

"จ.เชียงใหม่ อุบัติเหตุ 920 ครั้ง"      →    evidence_id = "EV-002"
(จาก get_province_year_summary)                evidence_type = "database"
                                               source_ref = "mart_province_year"
                                               trust_level = "high"
                                               open_url = "/api/evidence/EV-002/query"
```

**Trust Level** กำหนดตามแหล่งข้อมูล:

| แหล่งข้อมูล | trust_level |
|------------|------------|
| รายงานตรวจราชการ NotebookLM PDF (notebooklm_pdf) | `high` |
| Document RAG (เอกสารที่ upload ผ่าน MinIO) | `high` |
| Mart tables (ข้อมูลสรุปแล้ว) | `high` |
| Fact tables (ข้อมูลดิบ) | `medium` |
| Custom SQL | `medium` |
| บทความวิชาการ ThaiJO (thaijo_article) | `medium` |
| External API | `low` |

---

### ขั้นที่ 2 — Register Evidence

บันทึก EvidenceItem ลงฐานข้อมูล `evidence_registry` (PostgreSQL) ผ่าน tool `register_evidence`

```sql
-- table: evidence_registry
INSERT INTO evidence_registry (
    evidence_id, evidence_type, source_ref, title,
    page_ref, section_label, text_snippet,
    trust_level, original_url, open_url, ...
) VALUES (...)
ON CONFLICT (evidence_id) DO NOTHING;
```

---

### ขั้นที่ 3 — Map Claims to Evidence

เชื่อมข้อสรุป (Claim) ที่จะพูดในรายงานกับ evidence ที่รองรับ:

```
Claim CL-001: "จ.เชียงใหม่มีอุบัติเหตุ 920 ครั้ง ปี 2025"
    claim_type    = statistic
    evidence_ids  = ["EV-002"]         ← มาจาก mart_province_year
    support_level = supported
    evidence_strength = strong

Claim CL-002: "เพิ่มขึ้น 15% จากปีก่อน"
    claim_type    = comparison
    evidence_ids  = ["EV-002", "EV-001"]
    support_level = partially_supported
    evidence_strength = moderate
```

บันทึกลง `claim_evidence_link` ผ่าน tool `register_claim_links`

---

### ขั้นที่ 4 — Generate Citations

สร้าง citation code และข้อความอ้างอิง:

```
EV-001 (document) → C-001
    citation_code      = "C-001"
    citation_text      = "นโยบายความปลอดภัยทางถนน 2025, ส่วนที่ 3.2, หน้า 12"
    bibliography_text  = "นโยบายความปลอดภัยทางถนน 2025. กรมทางหลวง. หน้า 12."
    open_url           = "/api/documents/open/42?page=12"

EV-002 (database) → C-002
    citation_code      = "C-002"
    citation_text      = "ฐานข้อมูลสรุปรายจังหวัดรายปี, 2025"
    bibliography_text  = "ฐานข้อมูลสรุปรายจังหวัดรายปี (mart_province_year). Musya Agent."
    open_url           = "/api/evidence/EV-002/query"
```

---

### ขั้นที่ 5 — Coverage Check

ตรวจสอบว่าทุก claim มีหลักฐานรองรับ:

```json
{
  "total_claims": 5,
  "supported": 4,
  "unsupported": 1,
  "coverage_score": 0.80,
  "flags": [
    "CL-005: ข้อสรุปนี้ไม่มีหลักฐานรองรับ — ต้องตรวจสอบ"
  ]
}
```

---

## 4. Output ที่ส่งต่อ (EvidenceContext)

Agent นี้ส่ง JSON object ไปยัง Agent 5–9 ผ่าน CrewAI task context:

```json
{
  "evidence_items": [
    {
      "evidence_id": "EV-001",
      "evidence_type": "document",
      "source_ref": "road_safety_policy_2025.pdf",
      "title": "นโยบายความปลอดภัยทางถนน 2025",
      "page_ref": "12",
      "section_label": "Section 3.2",
      "trust_level": "high",
      "text_snippet": "จังหวัดเชียงใหม่มีอัตราอุบัติเหตุสูงขึ้น...",
      "open_url": "/api/documents/open/42?page=12"
    },
    {
      "evidence_id": "EV-002",
      "evidence_type": "database",
      "source_ref": "mart_province_year",
      "title": "ข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี",
      "trust_level": "high",
      "open_url": "/api/evidence/EV-002/query"
    }
  ],
  "claims": [
    {
      "claim_id": "CL-001",
      "claim_text": "จ.เชียงใหม่มีอุบัติเหตุ 920 ครั้ง ปี 2025",
      "claim_type": "statistic",
      "support_level": "supported",
      "evidence_strength": "strong"
    }
  ],
  "citations": [
    {
      "citation_code": "C-001",
      "evidence_id": "EV-002",
      "source_type": "database",
      "citation_text": "ฐานข้อมูลสรุปรายจังหวัดรายปี, 2025",
      "open_url": "/api/evidence/EV-002/query",
      "trust_level": "high"
    }
  ],
  "source_notes": {
    "charts": "ที่มา: mart_province_year [C-001]",
    "tables": "ที่มา: mart_province_year [C-001]"
  },
  "coverage": {
    "coverage_score": 0.80,
    "flags": []
  }
}
```

---

## 5. Data Models (`src/schemas/evidence.py`)

```
EvidenceItem          — หลักฐาน 1 ชิ้น (ไม่ว่าจะเป็น document/database/api)
Claim                 — ข้อสรุป 1 ข้อที่จะพูดในรายงาน
ClaimEvidenceLink     — ความสัมพันธ์ระหว่าง claim กับ evidence
EnhancedCitation      — citation code + display text + bibliography + open_url
CoverageReport        — ผลการตรวจ coverage (คะแนน, flags)
EvidenceContext       — รวมทุกอย่างข้างต้นเป็น object เดียว
```

---

## 6. Tools ที่ Agent ใช้ (4 tools)

| Tool | ฟังก์ชัน | เขียนใน |
|------|---------|--------|
| `list_all_documents_apa` | แสดงรายการเอกสารทั้งหมดพร้อม APA citation | `citation_evidence.py` |
| `lookup_document_apa` | ค้นหา APA citation ของเอกสารเฉพาะ | `citation_evidence.py` |
| `register_evidence` | บันทึก EvidenceItem ลง `evidence_registry` | `citation_evidence.py` |
| `register_claim_links` | บันทึก Claim↔Evidence links ลง `claim_evidence_link` | `citation_evidence.py` |

### Citation Code Ranges

| Range | Source Type | Trust Level |
|-------|-----------|-------------|
| C-001 to C-099 | Reports (notebooklm_pdf / document) | High |
| C-100 to C-199 | Database / dataset | High (mart) / Medium (fact) |
| C-200 to C-299 | ThaiJO academic articles | Medium |
| C-300+ | External sources | Variable |

### Evidence Types

| evidence_type | แหล่งข้อมูล |
|--------------|-------------|
| `document` | เอกสาร PDF/DOCX จาก MinIO |
| `database` | ข้อมูลจาก mart/fact tables |
| `api` | External API response |
| `thaijo_article` | บทความจาก TCI-THAIJO |
| `notebooklm_pdf` | เอกสารจาก NotebookLM |

---

## 7. Source Files

| ไฟล์ | บทบาท |
|------|------|
| `src/agents/citation_evidence.py` | Agent factory, CITATION_EVIDENCE_PROMPT, 4 tools, `parse_evidence_context()` |
| `src/schemas/evidence.py` | Pydantic models: EvidenceItem, Claim, ClaimEvidenceLink, EnhancedCitation, CoverageReport, EvidenceContext |
| `src/routers/evidence.py` | API endpoints: `GET /api/evidence/{id}`, `/api/evidence/session/{id}` |
| `database/010_evidence_citation.sql` | Migration สร้าง `evidence_registry` + `claim_evidence_link` |

---

## 8. `citation_test_ui.html` — Test UI สำหรับ Citation & Evidence

เข้าถึงได้ที่: **http://localhost:8000/static/citation_test_ui.html**

### ภาพรวม UI

```
┌──────────────────────────────────────────────────────────────────┐
│  🔍 Citation & Evidence Agent Test UI                            │
│  Test the 10-agent pipeline with evidence tracking                │
├──────────────────────────────────────────────────────────────────┤
│  [💬 Chat Test] [📚 Evidence API] [📄 Documents] [🏥 Health]    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tab ที่เลือก...                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

### Tab 1: 💬 Chat Test

**วัตถุประสงค์:** ทดสอบ 10-agent pipeline ทั้งหมด และดูผลลัพธ์ citation ที่ได้

```
┌──────────────────────────────────────────────────────┐
│ Message (ภาษาไทย):                                   │
│ ┌────────────────────────────────────────────────┐   │
│ │ สถิติอุบัติเหตุจังหวัดเชียงใหม่ปี 2025         │   │
│ └────────────────────────────────────────────────┘   │
│                          [🚀 Send to Agent Pipeline] │
│                                                      │
│ ────── ผลลัพธ์ ──────                                │
│ Pipeline: phase2_with_citation_evidence              │
│ Agents: 7                                            │
│ Time: 145.3s                                         │
│ Citations: 3                                         │
│ Evidence: 5                                          │
│ Coverage Score: 80%                                  │
│                                                      │
│ 📚 Citations                                         │
│ [C-001] mart_province_year                           │
│         ฐานข้อมูลสรุปรายจังหวัดรายปี, 2025          │
│ [C-002] road_safety_policy_2025.pdf                  │
│         นโยบายความปลอดภัยทางถนน, หน้า 12            │
│                                                      │
│ 📈 Charts: 2                                         │
│ • แนวโน้มอุบัติเหตุเชียงใหม่ 2020-2026              │
│   Source: mart_province_year [C-001]                 │
│                                                      │
│ 📝 Full Response (JSON)                              │
│ { "content": "...", "citations": [...], ... }        │
└──────────────────────────────────────────────────────┘
```

**JavaScript function:** `testChat()`
```javascript
// POST /api/chat  →  แสดง: citations, charts, coverage_score, elapsed_seconds
async function testChat() {
    const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        body: JSON.stringify({ message })
    });
    // แสดง citations พร้อม citation_code, source_ref, citation_text
    // แสดง charts พร้อม title, source_note
    // แสดง metadata: pipeline, agent_count, elapsed_seconds, coverage_score
}
```

---

### Tab 2: 📚 Evidence API

**วัตถุประสงค์:** ทดสอบ API endpoints ของ Evidence โดยตรง (ไม่ต้องรัน full pipeline)

```
┌──────────────────────┐  ┌────────────────────────┐  ┌─────────────────────┐
│ Get Evidence by ID   │  │ Session Evidence        │  │ Open Document       │
│                      │  │                         │  │                     │
│ Evidence ID:         │  │ Session ID:             │  │ Document ID:        │
│ [EV-001         ]    │  │ [test-session-123  ]    │  │ [1              ]   │
│                      │  │                         │  │ Page (optional):    │
│ [Get Evidence]       │  │ [Get Session Evidence]  │  │ [12             ]   │
│                      │  │ [Get Coverage Report]   │  │ [Open Document]     │
└──────────────────────┘  └────────────────────────┘  └─────────────────────┘

ผลลัพธ์:
┌─────────────────────────────────────────────────┐
│ Evidence Item                                    │
│ ID: EV-001                                       │
│ Type: database                                   │
│ Source: mart_province_year                       │
│ Trust Level: [HIGH]                              │
│ Open URL: /api/evidence/EV-001/query  [คลิกได้]  │
└─────────────────────────────────────────────────┘
```

**API Endpoints ที่ทดสอบ:**

| ปุ่ม | API Call | คำอธิบาย |
|-----|---------|---------|
| Get Evidence | `GET /api/evidence/{id}` | ดู evidence item 1 รายการ |
| Get Session Evidence | `GET /api/evidence/session/{session_id}` | ดู evidence ทั้งหมดใน session |
| Get Coverage Report | `GET /api/evidence/session/{id}/coverage` | ดูรายงาน coverage |
| Open Document | `GET /api/documents/open/{id}?page={n}` | เปิดไฟล์เอกสารต้นฉบับ |

**Trust Level Badges:**

| Badge | สี | ความหมาย |
|-------|----|---------|
| `[HIGH]` | 🟢 เขียว | แหล่งที่มาน่าเชื่อถือสูง (verified document, mart table) |
| `[MEDIUM]` | 🟡 ส้ม | แหล่งที่มาน่าเชื่อถือปานกลาง (fact table, custom SQL) |
| `[LOW]` | 🔴 แดง | แหล่งที่มาภายนอก (external API) |

---

### Tab 3: 📄 Documents

**วัตถุประสงค์:** จัดการเอกสารใน MinIO และ pgvector (`document_embeddings`)

```
┌────────────────────────────┐  ┌─────────────────────────────────┐
│ Ingest Documents           │  │ Search Documents                 │
│                            │  │                                  │
│ Ingest all documents from  │  │ Topic: [Accident ▼]              │
│ MinIO → pgvector with      │  │ Keywords: [อุบัติเหตุทางถนน    ] │
│ enhanced metadata          │  │                                  │
│                            │  │ [🔍 Search]                      │
│ [🔄 Start Ingestion]       │  │                                  │
└────────────────────────────┘  └─────────────────────────────────┘
```

| ปุ่ม | API Call | ผลลัพธ์ |
|-----|---------|--------|
| Start Ingestion | `POST /api/ingest` | นำเข้าเอกสารจาก MinIO bucket `uploads` ไปยัง pgvector (`document_embeddings`) |
| Search | (mock) | แสดงรูปแบบผลลัพธ์ที่ search_documents tool จะคืน |

> **หมายเหตุ:** Search ใน tab นี้เป็น mock — การค้นหาจริงเกิดใน Agent 2 ผ่าน tool `search_documents`

---

### Tab 4: 🏥 Health Check

**วัตถุประสงค์:** ตรวจสอบสถานะของ services ทั้งหมด

```
[🏥 Check System Health]

● PostgreSQL: ✅ Connected
● MinIO:      ✅ Connected
● pgvector:   ✅ Connected
```

**API:** `GET /api/health`

---

## 9. ความสัมพันธ์กับ `test_ui.html` (Test UI หลัก)

| คุณสมบัติ | `test_ui.html` | `citation_test_ui.html` |
|----------|---------------|------------------------|
| **จุดประสงค์หลัก** | ทดสอบการแชทและดูกราฟ | ทดสอบ Citation & Evidence โดยเฉพาะ |
| **UI Framework** | TailwindCSS + Chart.js + marked.js | Plain CSS |
| **Chat Tab** | ✅ มี (rich: bubble UI, markdown render, charts) | ✅ มี (simple: JSON output) |
| **แสดงกราฟ** | ✅ Chart.js render กราฟจริง | ❌ แสดงเฉพาะ chart metadata |
| **แสดง Markdown** | ✅ render ด้วย marked.js | ❌ แสดงเป็น JSON |
| **Evidence API tab** | ❌ ไม่มี | ✅ มี (Get Evidence, Session, Coverage) |
| **Document tab** | ❌ ไม่มี | ✅ มี (Ingest + Search) |
| **Quick Questions** | ✅ มี (คำถามตัวอย่างคลิกเดียว) | ❌ ไม่มี |
| **Follow-up suggestions** | ✅ มี | ❌ ไม่มี |
| **ใช้เมื่อ** | ทดสอบ UX + กราฟ + รายงาน | debug citation + evidence pipeline |

---

## 10. Flow เต็มจาก Test UI ถึง Database

```
citation_test_ui.html                  Backend                     PostgreSQL
──────────────────────────────────────────────────────────────────────────────

[Tab: Chat Test]
  User types message
  ↓
  testChat() → POST /api/chat
               ↓
               orchestrator.run_chat()
               ↓
               [Agent 1] Request Interpreter
               ↓
               [Agent 2] Retrieval (pgvector + DB tools)
               ↓
               [Agent 3] SQL Specialist (PostgreSQL)
               ↓
               [Agent 4] Citation & Evidence ──────────► INSERT evidence_registry
                         ↓                               INSERT claim_evidence_link
                         EvidenceContext
               ↓
               [Agent 5] Accident Analyst
               ↓
               [Agent 6] Chart Builder
               ↓
               [Agent 7] Research Synthesizer
               ↓
               [Agent 8] Deep Analyst
               ↓
               [Agent 9] Report Composer
               ↓
               AgentResponse {
                 content, charts,
                 citations: [C-001, C-002],
                 metadata: { coverage_score }
               }
               ↓
  แสดงผล citations, charts, coverage_score

──────────────────────────────────────────────────────────────────────────────

[Tab: Evidence API]
  User types EV-001
  ↓
  getEvidence() → GET /api/evidence/EV-001
                  ↓
                  SELECT * FROM evidence_registry WHERE evidence_id = 'EV-001'
                  ↓
                  แสดง: type, source, trust_level, open_url

  User types session_id
  ↓
  getSessionEvidence() → GET /api/evidence/session/{id}
                         ↓
                         SELECT * FROM evidence_registry WHERE session_id = ?
                         ↓
                         แสดง: รายการ evidence ทั้งหมดใน session

  getSessionCoverage() → GET /api/evidence/session/{id}/coverage
                         ↓
                         SELECT COUNT(*) ... FROM claim_evidence_link
                         ↓
                         แสดง: total_claims, supported, coverage_score

──────────────────────────────────────────────────────────────────────────────

[Tab: Documents]
  ingestDocuments() → POST /api/ingest
                      ↓
                      MinIO bucket 'uploads' → download files
                      ↓
                      split into chunks (langchain_text_splitters)
                      ↓
                      pgvector.add_documents() → INSERT document_embeddings
                      ↓
                      INSERT document_registry
                      ↓
                      แสดง: จำนวนเอกสารที่ ingest สำเร็จ
```

---

## 11. วิธีทดสอบทีละขั้นตอน

### ขั้น 1: ตรวจสอบ Health
```
เปิด Tab: 🏥 Health Check
กด: Check System Health
ผลที่คาดหวัง: ● PostgreSQL: ✅ Connected
              ● MinIO:      ✅ Connected
              ● pgvector:   ✅ Connected
```

### ขั้น 2: Ingest เอกสาร (ครั้งแรก)
```
เปิด Tab: 📄 Documents
กด: 🔄 Start Ingestion
ผลที่คาดหวัง: { "ingested": 4, "failed": 0 }
```

### ขั้น 3: ทดสอบ Chat พร้อม Citation
```
เปิด Tab: 💬 Chat Test
พิมพ์: "สถิติอุบัติเหตุจังหวัดเชียงใหม่ ทุกปี 2020-2026"
กด: 🚀 Send to Agent Pipeline

รอ ~2-3 นาที (10 agents ทำงานต่อเนื่อง)

ผลที่คาดหวัง:
  Pipeline: phase2_with_citation_evidence
  Citations: [C-001] ... [C-002] ...
  Coverage Score: 70-90%
  Charts: 1-2 รายการ
```

### ขั้น 4: ดู Evidence จาก Tab Evidence API
```
เปิด Tab: 📚 Evidence API
ใส่ Evidence ID: EV-001
กด: Get Evidence

ผลที่คาดหวัง:
  ID: EV-001
  Type: database / document
  Trust Level: [HIGH]
  Open URL: /api/evidence/EV-001/query
```

---

## 12. ความสัมพันธ์กับ AGENT_WORKFLOW_UNIFIED.md

ดูเอกสาร [AGENT_WORKFLOW_UNIFIED.md](./AGENT_WORKFLOW_UNIFIED.md) สำหรับ workflow ภาพรวม

เอกสารนี้เจาะลึกเฉพาะ **Agent 4** และ **citation_test_ui.html** โดย:

| หัวข้อใน AGENT_WORKFLOW_UNIFIED.md | รายละเอียดใน เอกสารนี้ |
|------------------------------------|----------------------|
| Agent 4 — Citation & Evidence (ภาพรวม) | ส่วนที่ 2-6 (กระบวนการ 5 ขั้น, models, tools) |
| API Endpoints | ส่วนที่ 8 (Evidence API tab, endpoints table) |
| Test UI (`/static/citation_test_ui.html`) | ส่วนที่ 8-9 (ทุก tab อธิบายละเอียด) |
| Data Sources (PostgreSQL evidence tables) | ส่วนที่ 10 (flow เต็มถึง database) |
| วิธีเริ่มระบบ | ส่วนที่ 11 (วิธีทดสอบทีละขั้น) |

---

## 13. Troubleshooting

### Citation ว่างเปล่า (citations: [])
```
สาเหตุ: Agent 4 output ไม่ได้ถูก parse อย่างถูกต้อง
แก้: ดู server log หา "[TASK COMPLETE]" ของ Task 4
     ตรวจว่า JSON output ของ Agent 4 มี "citations" key หรือไม่
```

### Coverage Score = 0%
```
สาเหตุ: Agent 4 ไม่ได้สร้าง claims หรือ JSON parse ล้มเหลว
แก้: ดู log "Failed to parse Citation Agent output as JSON"
     ตรวจว่า GEMINI_API_KEY ถูกต้อง
```

### GET /api/evidence/EV-001 → 404
```
สาเหตุ: ยังไม่มีการรัน chat ที่สำเร็จ (evidence ยังไม่ถูก register)
แก้: รัน chat ก่อน 1 ครั้ง แล้วค้นหา EV-001 อีกครั้ง
```

### Ingestion ล้มเหลว
```
สาเหตุ: MinIO bucket ว่างหรือ pgvector ไม่พร้อม (ตรวจ document_embeddings table)
แก้: python scripts\prepare_sample_documents.py  ← อัปโหลด sample docs
     curl http://localhost:8000/api/health         ← ตรวจ services
```

---

*Last updated: 2026-04-16 | เกี่ยวข้องกับ: [AGENT_WORKFLOW_UNIFIED.md](./AGENT_WORKFLOW_UNIFIED.md), [CITATION_EVIDENCE_AGENT.md](./CITATION_EVIDENCE_AGENT.md)*
