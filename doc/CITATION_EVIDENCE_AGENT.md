# เอกสารออกแบบสถาปัตยกรรม: Citation & Evidence Agent
# สำหรับ Musya-Agent — Trust Layer สำหรับรายงานที่ตรวจสอบย้อนกลับได้

> **เวอร์ชัน**: 1.0  
> **วันที่**: 2026-04-13  
> **ขอบเขต**: สถาปัตยกรรม, data flow, schema, open_url contract, แนวทางเชื่อมกับระบบรายงาน  
> **วัตถุประสงค์**: ออกแบบส่วนกลางที่แปลงผล retrieval ให้เป็นหลักฐานที่ตรวจสอบย้อนกลับได้ พร้อมสร้าง citation, source note และ reference list สำหรับข้อความ ตาราง และกราฟ

---

## 1. บทนำและแนวคิดหลัก

### 1.1 ปัญหาที่ต้องแก้

Citation & Evidence Agent เป็นสถาปัตยกรรมย่อยที่ทำหน้าที่เป็น **trust layer** ของ Musya-Agent โดยอยู่กึ่งกลางระหว่าง Retrieval/SQL กับ Domain Analyst, Chart Builder และ Report Writer เพื่อให้ทุกข้อสรุปที่ออกสู่รายงานสามารถตรวจสอบย้อนกลับถึงหลักฐานต้นทางได้

เป้าหมายของส่วนนี้ไม่ใช่เพียงการแสดงรายการอ้างอิงท้ายรายงาน แต่รวมถึง:
- **Normalize** หลักฐานจากหลายแหล่ง (document chunk, database query, external API)
- **สร้าง citation code** ที่ใช้ inline ในเนื้อหารายงาน
- **ผูก claim กับ evidence** เพื่อตรวจสอบว่าข้อสรุปทุกข้อมีหลักฐานรองรับ
- **เติม source note** ให้กราฟและตารางอัตโนมัติ
- **ตรวจ coverage** ก่อนส่งต่อไปยัง Report Engine
- **สร้าง open_url** เพื่อให้คลิกกลับไปยังเอกสารต้นฉบับได้จริง (NotebookLM-style)

### 1.2 ปัญหาปัจจุบันของระบบ

| ปัญหา | รายละเอียด | ผลกระทบ |
|--------|-----------|---------|
| **citations ว่างเปล่า** | `_parse_crew_result()` ใน `orchestrator.py` ส่ง `citations=[]` เสมอ | รายงานไม่มีแหล่งอ้างอิง |
| **search_documents คืน string** | tool คืนข้อความ string ไม่ใช่ structured object | metadata (source, chunk_index) ถูกฝังใน text หาย |
| **pgvector metadata จำกัด (legacy)** | เดิมเก็บเฉพาะ source, chunk_index, total_chunks | ไม่มี page_ref, section_label, title (ปัจจุบันเก็บครบแล้ว) |
| **ไม่มี evidence registry** | ไม่มีการลงทะเบียนหลักฐานที่ค้นมาได้ | ไม่สามารถ trace ว่าข้อสรุปมาจากไหน |
| **source_note ไม่ systematic** | ChartSpec/TableSpec มี field แต่ไม่ได้เติมจาก evidence | กราฟ/ตารางไม่บอกแหล่งที่มา |
| **ไม่มี open_url** | ไม่มี contract สำหรับเปิดไฟล์ต้นฉบับ | ผู้ใช้ไม่สามารถกดดูเอกสารอ้างอิงได้ |
| **Citation schema ไม่สมบูรณ์** | มีเฉพาะ citation_code, source_type, source_ref, citation_text | ขาด evidence_id, open_url, bibliography_text, trust_level |

### 1.3 ผลลัพธ์ที่ต้องการ

- รายงานและหน้าจอ preview ที่ **คลิกกลับไปยังไฟล์ต้นฉบับได้จริง**
- **ลด hallucination** โดยบังคับให้ข้อสรุปต้องมี evidence รองรับ
- ทำให้ **review/compliance** ตรวจ coverage ของ citation ได้เป็นระบบ
- รองรับรูปแบบ **NotebookLM-style** — กดจาก citation ไปยังเอกสารต้นทาง

---

## 2. ภาพรวมสถาปัตยกรรมใหม่

### 2.1 Pipeline ใหม่ (8-step)

```
User Message
  │
  ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 1: Request Interpreter                                      │
│ • แปลความคำขอ → structured JSON                                  │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 2: Data Retrieval Specialist                                │
│ • ค้นข้อมูลจาก Document RAG + DB tools                          │
│ ★ ปรับ: search_documents คืน structured EvidenceItem[]            │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 3: SQL Database Specialist                                  │
│ • เขียน/รัน custom SQL query                                     │
│ ★ ปรับ: ผลลัพธ์แนบ query_signature + source metadata             │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌══════════════════════════════════════════════════════════════════┐
║ Agent 4: ★ Citation & Evidence Agent (NEW)                       ║
║                                                                  ║
║  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ ║
║  │  Evidence    │→ │  Evidence    │→ │  Claim Mapper           │ ║
║  │  Ingestor   │  │  Registry    │  │  (claim ↔ evidence)     │ ║
║  │  (normalize)│  │  Manager     │  │                         │ ║
║  └─────────────┘  └──────────────┘  └────────────┬────────────┘ ║
║                                                   │              ║
║  ┌─────────────┐  ┌──────────────┐  ┌────────────▼────────────┐ ║
║  │  Coverage   │← │  Object      │← │  Citation Generator     │ ║
║  │  Validator  │  │  Linker      │  │  (C-001, C-002, …)      │ ║
║  │  (QA gate)  │  │  (chart/tbl) │  │                         │ ║
║  └─────────────┘  └──────────────┘  └─────────────────────────┘ ║
║                                                                  ║
║  Output: EvidenceContext {evidence_items, claims, citations,     ║
║          chart_source_notes, table_source_notes, coverage_report}║
╚══════════════════════════════════════════════════════════════════╝
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 5: Domain Analyst                                           │
│ • วิเคราะห์เฉพาะข้อมูลที่มี evidence รองรับ                     │
│ ★ ปรับ: ใช้ EvidenceContext → ทุก finding แนบ claim_id            │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 6: Chart & Table Builder                                    │
│ • สร้าง ChartSpec/TableSpec พร้อม source_note จาก evidence       │
│ ★ ปรับ: source_note = citation_text จาก Object Linker            │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 7: Report Writer                                            │
│ • เรียบเรียงรายงาน + inline citation [C-001] + references        │
│ ★ ปรับ: เติม inline citation code, สร้าง reference list          │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent 8: ★ Review & Compliance (Optional / Coverage Check)        │
│ • ตรวจ coverage: ทุก numeric claim มี citation?                   │
│ • ตรวจ chart/table: ทุกชิ้นมี source_note?                       │
│ • flag unsupported claims                                        │
└──────────────────────┬───────────────────────────────────────────┘
                       ▼
AgentResponse {content, charts, tables, citations, follow_ups, metadata, evidence_summary}
```

### 2.2 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Musya Agent Backend (port 8000)                │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────────┐  │
│  │Retrieval │→ │SQL       │→ │ Citation & Evidence Agent     │  │
│  │Agent     │  │Specialist│  │                               │  │
│  │          │  │          │  │  ┌─────────────────────────┐  │  │
│  │ Doc RAG  │  │ query_db │  │  │  Evidence Registry      │  │  │
│  │ DB tools │  │ custom   │  │  │  (PostgreSQL)           │  │  │
│  └──────────┘  └──────────┘  │  └─────────────────────────┘  │  │
│                              │                               │  │
│                              │  Output:                      │  │
│                              │   EvidenceContext → downstream │  │
│                              └───────────────┬───────────────┘  │
│                                              │                   │
│                              ┌───────────────▼───────────────┐  │
│                              │ Analyst → Chart → Report      │  │
│                              │ (ใช้ EvidenceContext)          │  │
│                              └───────────────────────────────┘  │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────────┐    │
│  │PostgreSQL│  │ pgvector │  │ MinIO (documents)           │    │
│  │evidence_ │  │doc_embed │  │ uploads/                    │    │
│  │registry  │  │3072-dim │  │ → original_url              │    │
│  │claim_link│  │Gemini API│  │ → open_url via /api/doc/open│    │
│  └──────────┘  └──────────┘  └────────────────────────────┘    
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. บทบาทของ Citation & Evidence Agent

| หน้าที่ | คำอธิบาย |
|---------|---------|
| **Normalize evidence** | แปลงผล retrieval จากเอกสาร ฐานข้อมูล และ API ให้เป็น EvidenceItem กลางรูปแบบเดียวกัน |
| **Register evidence** | ออก evidence_id, ลงทะเบียนใน evidence registry, เก็บ provenance |
| **Map claims** | เชื่อม claim/ข้อสรุป กับ evidence ที่รองรับ พร้อมระบุ evidence_strength |
| **Generate citations** | สร้าง citation_code (C-001, C-002) + display text + bibliography text |
| **Link to objects** | เชื่อม citation เข้ากับ section text, chart, table พร้อม source_note |
| **Validate coverage** | Quality gate — ตรวจว่าทุก numeric claim มี citation, ทุก chart/table มี source_note |

---

## 4. องค์ประกอบย่อยภายใน Agent

### 4.1 Evidence Ingestor

**หน้าที่**: รับผลลัพธ์จาก Retrieval Agent และ SQL Specialist แล้ว normalize เป็น `EvidenceItem`

**Input ที่ได้รับ (ปัจจุบัน)**:
```python
# จาก search_documents tool (string)
"--- ผลลัพธ์ 1 (source: road_safety.pdf, chunk: 3, relevance: 0.23) ---\n..."

# จาก accident tools (string)
"จังหวัด: เชียงใหม่, ปี: 2025, อุบัติเหตุ: 920, เสียชีวิต: 28"

# จาก execute_custom_sql (string)
"[{\"province_name\": \"เชียงใหม่\", \"accident_count\": 920}]"
```

**Output ที่ต้องสร้าง**:
```json
{
  "evidence_id": "EV-001",
  "evidence_type": "document",
  "topic": "accident",
  "source_ref": "road_safety_policy_2025.pdf",
  "title": "นโยบายความปลอดภัยทางถนน 2025",
  "section_label": "Section 3.2",
  "page_ref": "12",
  "chunk_id": "abc123",
  "chunk_index": 3,
  "text_snippet": "จังหวัดเชียงใหม่มีอัตราอุบัติเหตุสูงขึ้น 15% ...",
  "query_signature": null,
  "query_params": null,
  "geography_ref": "เชียงใหม่",
  "time_range_ref": "2025",
  "extracted_at": "2026-04-13T10:00:00Z",
  "trust_level": "high",
  "original_url": "minio://uploads/folder1/road_safety_policy_2025.pdf",
  "open_url": "/api/documents/open/42?page=12"
}
```

**การ normalize แต่ละประเภท**:

| Source Type | trust_level | original_url | open_url | page_ref | section_label |
|-------------|-------------|-------------|----------|----------|---------------|
| **Document RAG** | `high` (verified doc) | `minio://uploads/{path}` | `/api/documents/open/{doc_id}?page={n}` | จาก PDF page extraction | จาก heading detection |
| **Database (mart)** | `high` (aggregated data) | `postgresql://mart_{table}` | `/api/evidence/{ev_id}/query` | N/A | `{table}.{column}` |
| **Database (fact)** | `medium` (raw data) | `postgresql://fact_{table}` | `/api/evidence/{ev_id}/query` | N/A | `{table}` |
| **Custom SQL** | `medium` | `postgresql://custom_query` | `/api/evidence/{ev_id}/query` | N/A | query description |
| **External API** | `low-medium` | original API URL | proxy URL | N/A | API endpoint |

### 4.2 Evidence Registry Manager

**หน้าที่**: Deduplicate, ออก evidence_id, บันทึกลง DB, track usage

**Deduplication Strategy**:
```
document evidence  → hash(source_ref + chunk_index + page_ref)
database evidence  → hash(query_signature + table_name + params_json)
api evidence       → hash(api_url + params_json + response_hash)
```

**Usage Tracking**: เมื่อ evidence ถูกใช้ใน report/chart/table จะ update `used_in_objects[]` เพื่อให้ reference list แสดงเฉพาะ evidence ที่ถูกใช้จริง

### 4.3 Claim Mapper

**หน้าที่**: แปลงข้อสรุปเป็น claim แล้ว map กับ evidence

**Claim Types**:
| Type | ตัวอย่าง | ต้องมี evidence |
|------|---------|----------------|
| `statistic` | "อุบัติเหตุ 920 ครั้ง" | ✅ ต้องมี (numeric) |
| `comparison` | "สูงกว่าปีก่อน 15%" | ✅ ต้องมี |
| `trend` | "มีแนวโน้มลดลง" | ✅ ต้องมี |
| `recommendation` | "ควรเพิ่มไฟส่องสว่าง" | ⚠️ ควรมี basis |
| `general_finding` | "ช่วงเทศกาลเสี่ยงสูง" | ✅ ต้องมี |
| `opinion` | "ระบบมีประสิทธิภาพดี" | ❌ flag as unsupported |

**Evidence Strength**:
```json
{
  "claim_id": "CL-001",
  "evidence_ids": ["EV-001", "EV-003"],
  "support_level": "supported",         // supported | partially_supported | insufficient | conflicting
  "evidence_strength": "strong",         // strong | moderate | weak
  "confidence_note": "ข้อมูลจาก 2 แหล่ง: mart_province_year + road_safety_policy_2025.pdf"
}
```

### 4.4 Citation Generator

**หน้าที่**: สร้าง citation code และข้อความ citation ทั้ง display และ bibliography

**Citation Code Convention**:
```
C-001 ... C-NNN  (sequential per report session)
```

**Output**:
```json
{
  "citation_code": "C-001",
  "evidence_id": "EV-001",
  "source_type": "document",
  "source_ref": "road_safety_policy_2025.pdf",
  "citation_text": "นโยบายความปลอดภัยทางถนน 2025, ส่วนที่ 3.2, หน้า 12",
  "bibliography_text": "นโยบายความปลอดภัยทางถนน 2025. กรมทางหลวง. ส่วนที่ 3.2, หน้า 12.",
  "open_url": "/api/documents/open/42?page=12",
  "trust_level": "high"
}
```

**Citation Styles by Source Type**:

| Source Type | citation_text Example | bibliography_text Example |
|-------------|----------------------|--------------------------|
| **Document** | "นโยบายฯ 2025, ส่วน 3.2, น.12" | "นโยบายความปลอดภัยทางถนน 2025. กรมทางหลวง. หน้า 12." |
| **Database (mart)** | "ข้อมูลจาก mart_province_year, 2025" | "ฐานข้อมูลสรุปรายจังหวัดรายปี (mart_province_year). Musya Agent." |
| **Database (fact)** | "ข้อมูลอุบัติเหตุ, 2025" | "ฐานข้อมูลเหตุการณ์อุบัติเหตุ (fact_accident_event). Musya Agent." |
| **Custom SQL** | "ผลสืบค้น SQL, query Q-001" | "ผลการสืบค้นฐานข้อมูล (custom query). Musya Agent." |
| **External API** | "Open-Meteo Weather, 13 เม.ย. 2026" | "Open-Meteo Weather Forecast API. สืบค้น 13 เม.ย. 2026." |

### 4.5 Object Linker

**หน้าที่**: เชื่อม citation กับ content objects

**สำหรับ Report Text**:
```markdown
จังหวัดเชียงใหม่มีอุบัติเหตุ 920 ครั้ง ในปี 2025 [C-001] ซึ่งลดลงจากปีก่อน 15% [C-002]
ถนนที่มีความเสี่ยงสูงสุดคือทางหลวงหมายเลข 11 [C-003]
```

**สำหรับ ChartSpec**:
```json
{
  "type": "line",
  "title": "แนวโน้มอุบัติเหตุจังหวัดเชียงใหม่",
  "data": { "labels": [...], "datasets": [...] },
  "source_note": "ที่มา: mart_province_year [C-001]; road_safety_policy_2025.pdf, หน้า 12 [C-002]",
  "evidence_ids": ["EV-001", "EV-002"]
}
```

**สำหรับ TableSpec**:
```json
{
  "table_name": "สรุปรายจังหวัด",
  "columns": ["จังหวัด", "อุบัติเหตุ", "เสียชีวิต"],
  "rows": [...],
  "source_note": "ที่มา: mart_province_year, ปี 2025 [C-001]",
  "evidence_ids": ["EV-001"]
}
```

### 4.6 Coverage Validator

**หน้าที่**: Quality gate ก่อนส่งออกรายงาน

**กฎการตรวจ**:

| Rule | Condition | Severity | Action |
|------|-----------|----------|--------|
| **CV-01** | Numeric claim ไม่มี citation | 🔴 Error | Flag claim, เพิ่ม "[ต้องตรวจสอบ]" |
| **CV-02** | Chart ไม่มี source_note | 🟠 Warning | Auto-fill จาก evidence ที่เกี่ยวข้อง |
| **CV-03** | Table ไม่มี source_note | 🟠 Warning | Auto-fill จาก evidence ที่เกี่ยวข้อง |
| **CV-04** | Reference list มี evidence ที่ไม่ได้ใช้ | 🟡 Info | ลบออกจาก reference list |
| **CV-05** | Claim มี conflicting evidence | 🟠 Warning | เพิ่ม caveat note |
| **CV-06** | Evidence trust_level = "low" | 🟡 Info | เพิ่ม disclaimer |

**Output**: `CoverageReport`
```json
{
  "total_claims": 12,
  "supported_claims": 10,
  "partially_supported": 1,
  "unsupported_claims": 1,
  "total_charts": 3,
  "charts_with_source": 3,
  "total_tables": 1,
  "tables_with_source": 1,
  "coverage_score": 0.92,
  "flags": [
    {"rule": "CV-01", "severity": "error", "claim_id": "CL-008", "message": "ข้อสรุปเชิงตัวเลขไม่มีหลักฐานรองรับ"}
  ]
}
```

---

## 5. Canonical Data Models

### 5.1 EvidenceItem

เป็น representation กลางของหลักฐาน 1 ชิ้น:

```python
class EvidenceItem(BaseModel):
    """Normalized evidence from any source."""
    evidence_id: str = Field(..., description="Unique ID, e.g. EV-001")
    evidence_type: str = Field(..., description="document | database | api")
    topic: str = Field("general", description="accident | mental_health | nutrition")
    
    # Source identification
    source_ref: str = Field(..., description="Document name or table/view name")
    title: str = Field("", description="Human-readable title")
    section_label: str = Field("", description="Section/heading within document")
    page_ref: str = Field("", description="Page number for documents")
    chunk_id: str = Field("", description="pgvector chunk ID (document_embeddings.id)")
    chunk_index: int = Field(-1, description="Chunk position in document")
    
    # For database evidence
    query_signature: str = Field("", description="SHA-256 of the SQL query")
    query_params: dict = Field(default_factory=dict, description="Query parameters")
    
    # Context
    geography_ref: str = Field("", description="Province/district referenced")
    time_range_ref: str = Field("", description="Year/month/period referenced")
    text_snippet: str = Field("", description="Key text excerpt (max 500 chars)")
    
    # Trust & provenance
    extracted_at: str = Field(..., description="ISO timestamp of extraction")
    trust_level: str = Field("medium", description="high | medium | low")
    
    # URLs for traceability
    original_url: str = Field("", description="Original source URL (MinIO, PostgreSQL, API)")
    open_url: str = Field("", description="Clickable URL for frontend: /api/documents/open/{id}")
```

### 5.2 Claim

ข้อสรุป 1 ข้อที่ระบบกำลังจะพูดออกมา:

```python
class Claim(BaseModel):
    """A single factual claim that needs evidence backing."""
    claim_id: str = Field(..., description="Unique ID, e.g. CL-001")
    claim_text: str = Field(..., description="The claim statement")
    claim_type: str = Field(..., description="statistic | comparison | trend | recommendation | general_finding")
    section_id: str = Field("", description="Report section this claim belongs to")
    object_type: str = Field("text", description="text | chart | table")
    object_id: str = Field("", description="ID of the chart/table/paragraph")
```

### 5.3 ClaimEvidenceLink

ความสัมพันธ์ระหว่าง claim กับ evidence:

```python
class ClaimEvidenceLink(BaseModel):
    """Maps a claim to its supporting evidence."""
    claim_id: str
    evidence_id: str
    support_level: str = Field(..., description="supported | partially_supported | insufficient | conflicting")
    evidence_strength: str = Field("moderate", description="strong | moderate | weak")
    confidence_note: str = Field("", description="Human-readable explanation")
```

### 5.4 Citation (Enhanced)

เวอร์ชันใหม่ที่เพิ่มจากเดิม:

```python
class Citation(BaseModel):
    """Enhanced citation for display in UI and DOCX."""
    citation_code: str = Field(..., description="e.g. C-001")
    evidence_id: str = Field(..., description="Link to EvidenceItem")
    source_type: str = Field(..., description="document | database | api")
    source_ref: str = Field("", description="Document name or table name")
    citation_text: str = Field("", description="Short display citation (inline)")
    bibliography_text: str = Field("", description="Full bibliography entry for reference list")
    open_url: str = Field("", description="Clickable URL: /api/documents/open/{id}")
    trust_level: str = Field("medium", description="Inherited from evidence")
```

### 5.5 EvidenceContext

ผลรวมที่ Citation & Evidence Agent ส่งต่อให้ downstream agents:

```python
class EvidenceContext(BaseModel):
    """Complete evidence context passed to downstream agents."""
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    claim_links: list[ClaimEvidenceLink] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    chart_source_notes: dict[str, str] = Field(default_factory=dict, description="chart_id → source_note")
    table_source_notes: dict[str, str] = Field(default_factory=dict, description="table_id → source_note")
    coverage_report: dict = Field(default_factory=dict)
```

---

## 6. Database Schema (Migration 010)

### 6.1 `evidence_registry` — ทะเบียนหลักฐาน

```sql
CREATE TABLE IF NOT EXISTS evidence_registry (
    evidence_id     VARCHAR(20) PRIMARY KEY,       -- EV-001
    session_id      VARCHAR(255),                   -- chat session ที่สร้าง
    evidence_type   VARCHAR(20) NOT NULL,           -- document | database | api
    topic           VARCHAR(100) DEFAULT 'general',
    
    -- Source identification
    source_ref      VARCHAR(500) NOT NULL,          -- filename or table name
    title           VARCHAR(500),
    section_label   VARCHAR(200),
    page_ref        VARCHAR(50),
    chunk_id        VARCHAR(255),                   -- pgvector chunk ID (document_embeddings.id)
    chunk_index     INTEGER,
    
    -- For database evidence
    query_signature VARCHAR(64),                    -- SHA-256
    query_params    JSONB,
    
    -- Context
    geography_ref   VARCHAR(200),
    time_range_ref  VARCHAR(100),
    text_snippet    TEXT,
    
    -- Trust & provenance
    trust_level     VARCHAR(20) DEFAULT 'medium',   -- high | medium | low
    original_url    VARCHAR(1000),                   -- minio://... or postgresql://...
    open_url        VARCHAR(1000),                   -- /api/documents/open/{id}
    
    -- Tracking
    extracted_at    TIMESTAMP DEFAULT NOW(),
    used_in_objects TEXT[] DEFAULT '{}',             -- array of object IDs
    
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ev_session ON evidence_registry(session_id);
CREATE INDEX IF NOT EXISTS idx_ev_source ON evidence_registry(source_ref);
CREATE INDEX IF NOT EXISTS idx_ev_topic ON evidence_registry(topic);
CREATE INDEX IF NOT EXISTS idx_ev_query_sig ON evidence_registry(query_signature);
```

### 6.2 `claim_evidence_link` — ความสัมพันธ์ claim↔evidence

```sql
CREATE TABLE IF NOT EXISTS claim_evidence_link (
    link_id         BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(255),
    claim_id        VARCHAR(20) NOT NULL,           -- CL-001
    claim_text      TEXT,
    claim_type      VARCHAR(50),                    -- statistic | comparison | trend | ...
    section_id      VARCHAR(100),
    object_type     VARCHAR(20) DEFAULT 'text',     -- text | chart | table
    object_id       VARCHAR(100),
    
    evidence_id     VARCHAR(20) NOT NULL REFERENCES evidence_registry(evidence_id),
    support_level   VARCHAR(30) DEFAULT 'supported', -- supported | partially_supported | insufficient | conflicting
    evidence_strength VARCHAR(20) DEFAULT 'moderate', -- strong | moderate | weak
    confidence_note TEXT,
    
    citation_code   VARCHAR(20),                    -- C-001
    
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cel_session ON claim_evidence_link(session_id);
CREATE INDEX IF NOT EXISTS idx_cel_claim ON claim_evidence_link(claim_id);
CREATE INDEX IF NOT EXISTS idx_cel_evidence ON claim_evidence_link(evidence_id);
CREATE INDEX IF NOT EXISTS idx_cel_citation ON claim_evidence_link(citation_code);
```

### 6.3 Enhanced `document_registry` (ปรับปรุง)

เพิ่ม columns ใหม่เข้า `document_registry` ที่มีอยู่แล้ว:

```sql
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000);
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS total_pages INTEGER;
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS original_url VARCHAR(1000);
ALTER TABLE document_registry ADD COLUMN IF NOT EXISTS open_url VARCHAR(1000);
```

### 6.4 Enhanced `document_chunks` (ปรับปรุง)

เพิ่ม metadata ที่จำเป็นสำหรับ citation:

```sql
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS section_label VARCHAR(200);
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS heading_text VARCHAR(500);
```

---

## 7. open_url / original_url Contract

### 7.1 URL Types

| Field | ตัวอย่าง | วัตถุประสงค์ |
|-------|---------|-------------|
| `original_url` | `minio://uploads/folder1/report.pdf` | Permanent reference ของแหล่งต้นทาง |
| `open_url` | `/api/documents/open/42?page=12` | Clickable URL ที่ frontend เรียกเพื่อเปิดดูเอกสาร |

### 7.2 API Endpoints สำหรับเปิดเอกสาร

```
GET /api/documents/open/{document_id}
  Query params: ?page=12 (optional)
  Response: File stream (PDF/DOCX) หรือ redirect ไป MinIO presigned URL
  Content-Disposition: inline

GET /api/documents/open/{document_id}/info
  Response: { document_id, title, file_path, total_pages, mime_type, open_url }

GET /api/evidence/{evidence_id}
  Response: EvidenceItem JSON พร้อม open_url ที่คลิกได้

GET /api/evidence/{evidence_id}/query
  Response: สำหรับ database evidence — แสดง SQL query + result rows
```

### 7.3 Frontend Integration (Chat-/ChatV1)

**Citation Click Flow**:
```
User clicks [C-001] in report
  → Frontend reads citation.open_url
  → IF document: open in new tab → /api/documents/open/42?page=12
  → IF database: open modal → show SQL query + result table
  → IF API: open external link
```

**ChartRenderer source_note Click Flow**:
```
User clicks source_note under chart
  → Parse evidence_ids from ChartSpec
  → Open evidence detail modal
  → List all evidence items with open_url links
```

---

## 8. ลำดับการทำงานแบบ End-to-End

### 8.1 Sequence Diagram

```
Browser          Chat-/ChatV1         Agent Backend             PostgreSQL      pgvector      MinIO
  │                  │                      │                       │               │            │
  │  User sends msg  │                      │                       │               │            │
  ├─────────────────►│                      │                       │               │            │
  │                  │  POST /api/chat      │                       │               │            │
  │                  ├─────────────────────►│                       │               │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ①Request Interpreter  │               │            │
  │                  │                      │  → structured JSON    │               │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ②Retrieval Agent      │               │            │
  │                  │                      │  search_documents ────┼──────────────►│            │
  │                  │                      │  ◄── chunks + meta ───┼───────────────┤            │
  │                  │                      │  get_province_year ───┼──►            │            │
  │                  │                      │  ◄── mart rows ───────┼──┤            │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ③SQL Specialist       │               │            │
  │                  │                      │  execute_custom_sql ──┼──►            │            │
  │                  │                      │  ◄── query result ────┼──┤            │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ④★Citation & Evidence │               │            │
  │                  │                      │  normalize evidence   │               │            │
  │                  │                      │  register evidence ───┼──►            │            │
  │                  │                      │  map claims           │               │            │
  │                  │                      │  generate citations   │               │            │
  │                  │                      │  resolve open_url ────┼──────────────────────────►│
  │                  │                      │  validate coverage    │               │            │
  │                  │                      │  → EvidenceContext    │               │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ⑤Domain Analyst       │               │            │
  │                  │                      │  (uses EvidenceContext)│               │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ⑥Chart & Table Builder│               │            │
  │                  │                      │  + source_note from evidence           │            │
  │                  │                      │                       │               │            │
  │                  │                      │ ⑦Report Writer        │               │            │
  │                  │                      │  + inline citations [C-001]            │            │
  │                  │                      │  + reference list                      │            │
  │                  │                      │                       │               │            │
  │                  │  AgentResponse ◄─────┤                       │               │            │
  │                  │  {content, charts,   │                       │               │            │
  │                  │   citations, ...}    │                       │               │            │
  │  render +        │                      │                       │               │            │
  │  clickable links │                      │                       │               │            │
  │◄─────────────────┤                      │                       │               │            │
  │                  │                      │                       │               │            │
  │  User clicks     │                      │                       │               │            │
  │  [C-001]         │                      │                       │               │            │
  ├─────────────────►│  GET /api/documents/open/42?page=12          │               │            │
  │                  ├─────────────────────►│                       │               │            │
  │                  │                      │  download file ───────┼──────────────────────────►│
  │                  │  ◄── file stream ────┤  ◄── file bytes ──────┼──────────────────────────┤
  │  open PDF viewer │                      │                       │               │            │
  │◄─────────────────┤                      │                       │               │            │
```

### 8.2 10-Step Narrative

| Step | Agent | Action | Output |
|------|-------|--------|--------|
| 1 | User | ส่งคำขอ: "สถิติอุบัติเหตุเชียงใหม่ปี 2025" | message |
| 2 | Request Interpreter | แปลง → {topics: ["accident"], geography: "เชียงใหม่", time_range: "2025"} | JSON |
| 3 | Retrieval Agent | ค้น Document RAG + DB tools → raw results + metadata | string + metadata |
| 4 | SQL Specialist | Custom SQL query → results with query_signature | rows + query metadata |
| 5 | **Citation & Evidence** | Normalize → register evidence → map claims → generate citations → link objects → validate coverage | EvidenceContext |
| 6 | Domain Analyst | วิเคราะห์เฉพาะ supported claims → findings with claim_id | analysis |
| 7 | Chart & Table Builder | สร้าง ChartSpec/TableSpec + source_note from evidence | specs |
| 8 | Report Writer | เขียนรายงาน + inline [C-001] + reference list | markdown |
| 9 | (optional) Review | ตรวจ coverage → flag unsupported claims | report |
| 10 | Frontend | Render + clickable citations → open source docs | UI |

---

## 9. Enhanced search_documents Tool Contract

### 9.1 ปัจจุบัน (string output)

```python
@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    # returns: "--- ผลลัพธ์ 1 (source: road_safety.pdf, chunk: 3, relevance: 0.23) ---\n..."
```

### 9.2 เป้าหมาย (structured output)

```python
@tool("search_documents_v2")
def search_documents_v2(topic: str, keywords: str, n_results: int = 5) -> str:
    """Search documents and return structured evidence items.
    
    Returns JSON array of EvidenceItem objects with full metadata.
    """
    results = doc_search(query=keywords, topic=topic, n_results=n_results)
    
    evidence_items = []
    for r in results:
        meta = r.get("metadata", {})
        evidence_items.append({
            "evidence_type": "document",
            "source_ref": meta.get("source", "unknown"),
            "title": meta.get("title", meta.get("source", "")),
            "section_label": meta.get("section_label", ""),
            "page_ref": str(meta.get("page_ref", "")),
            "chunk_id": r.get("id", ""),
            "chunk_index": meta.get("chunk_index", -1),
            "text_snippet": r["text"][:500],
            "trust_level": "high",
            "original_url": f"minio://uploads/{meta.get('source', '')}",
            "distance": r.get("distance"),
        })
    
    return json.dumps(evidence_items, ensure_ascii=False)
```

### 9.3 Document Ingestion Metadata Enrichment

เมื่อ ingest เอกสาร ต้องเก็บ metadata เพิ่ม:

```python
metadatas.append({
    "source": object_name,
    "chunk_index": i,
    "total_chunks": len(chunks),
    # ★ NEW metadata:
    "title": document_title,        # extracted from first heading or filename
    "page_ref": str(page_number),   # for PDF: which page this chunk is from
    "section_label": section_heading, # detected heading/section
    "document_id": doc_id,          # FK to document_registry
})
```

---

## 10. Integration กับ Reporting Layer

### 10.1 Web Preview

```
┌─────────────────────────────────────────────────────┐
│  Report Preview (Browser)                            │
│                                                      │
│  ## สรุปสาระสำคัญ                                    │
│  จ.เชียงใหม่มีอุบัติเหตุ 920 ครั้ง [C-001]          │◄── คลิก [C-001] เปิด source
│  ลดลงจากปี 2024 จำนวน 15% [C-002]                   │
│                                                      │
│  ┌───────────────────────────────────┐               │
│  │  📊 กราฟแนวโน้มอุบัติเหตุ         │               │
│  │  (Chart.js rendered)              │               │
│  │                                   │               │
│  │  ที่มา: mart_province_year [C-001] │◄── คลิกดู source
│  └───────────────────────────────────┘               │
│                                                      │
│  ## เอกสารอ้างอิง                                    │
│  [C-001] ฐานข้อมูลสรุปฯ (mart_province_year) 🔗     │◄── คลิกดู query
│  [C-002] นโยบายความปลอดภัยฯ 2025, น.12 🔗           │◄── คลิกเปิด PDF
│  [C-003] ข้อมูล mart_province_road 🔗                │◄── คลิกดู query
└─────────────────────────────────────────────────────┘
```

### 10.2 DOCX Export

เมื่อ export เป็น DOCX:
- Inline citation `[C-001]` → superscript footnote หรือ bracket reference
- Reference list → ท้ายเอกสาร ใช้ `bibliography_text` format
- Source note ใต้กราฟ/ตาราง → caption text

### 10.3 AgentResponse Schema (Enhanced)

```json
{
  "content": "## สรุป\nจ.เชียงใหม่มีอุบัติเหตุ 920 ครั้ง [C-001] ...",
  "topic": "accident",
  "charts": [{
    "type": "line",
    "title": "แนวโน้มอุบัติเหตุ",
    "data": { "labels": [...], "datasets": [...] },
    "source_note": "ที่มา: mart_province_year [C-001]",
    "evidence_ids": ["EV-001"]
  }],
  "tables": [{
    "table_name": "สรุปรายจังหวัด",
    "columns": [...],
    "rows": [...],
    "source_note": "ที่มา: mart_province_year [C-001]",
    "evidence_ids": ["EV-001"]
  }],
  "citations": [
    {
      "citation_code": "C-001",
      "evidence_id": "EV-001",
      "source_type": "database",
      "source_ref": "mart_province_year",
      "citation_text": "ฐานข้อมูลสรุปรายจังหวัดรายปี, 2025",
      "bibliography_text": "ฐานข้อมูลสรุปรายจังหวัดรายปี (mart_province_year). Musya Agent. 2025.",
      "open_url": "/api/evidence/EV-001/query",
      "trust_level": "high"
    }
  ],
  "follow_ups": [...],
  "metadata": {
    "elapsed_seconds": 52.3,
    "agent_count": 7,
    "evidence_count": 5,
    "citation_count": 3,
    "coverage_score": 0.95
  },
  "evidence_summary": {
    "total_evidence": 5,
    "by_type": { "document": 2, "database": 3, "api": 0 },
    "coverage_score": 0.95,
    "unsupported_claims": 0
  }
}
```

---

## 11. Implementation Roadmap

### Phase 2A: Foundation (Citation & Evidence Agent)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 1 | สร้าง migration 010 (evidence_registry, claim_evidence_link) | Must | S |
| 2 | สร้าง `src/schemas/evidence.py` (EvidenceItem, Claim, Citation enhanced, EvidenceContext) | Must | S |
| 3 | สร้าง `src/agents/citation_evidence.py` (CrewAI agent + prompt) | Must | M |
| 4 | ปรับ `orchestrator.py` เพิ่ม Citation & Evidence Agent ใน pipeline | Must | M |
| 5 | ปรับ `search_documents` tool ให้คืน structured output | Must | S |
| 6 | ปรับ document ingestion เพิ่ม metadata (page_ref, section_label, title) | Should | M |

### Phase 2B: Integration

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 7 | สร้าง `/api/documents/open/{id}` endpoint | Should | S |
| 8 | สร้าง `/api/evidence/{id}` endpoint | Should | S |
| 9 | ปรับ Report Writer prompt ใช้ inline citation | Must | S |
| 10 | ปรับ Chart Builder prompt เติม source_note from evidence | Must | S |
| 11 | ปรับ `_parse_crew_result()` populate citations จาก Evidence Agent output | Must | M |
| 12 | เพิ่ม Coverage Validator ใน pipeline | Should | M |

### Phase 2C: Frontend Integration

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 13 | ChatV1/Chat-: render clickable citation [C-001] → open source | Should | M |
| 14 | ChatV1/Chat-: ChartRenderer source_note with links | Should | S |
| 15 | ChatV1/Chat-: Reference list component | Should | M |
| 16 | DOCX export with citations | Could | L |

---

## 12. ภาคผนวก

### A. CrewAI Tool Contract Changes

**ปัจจุบัน** (tools คืน string):
```python
@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    # returns concatenated string
```

**เป้าหมาย** (tools คืน JSON string ที่ parse ได้):
```python
@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    # returns JSON array of { evidence_type, source_ref, title, page_ref, ... }
```

> **หมายเหตุ**: CrewAI tools ต้อง return string — ใช้ JSON.dumps() แล้วให้ Citation & Evidence Agent parse

### B. Evidence ID Convention

```
EV-{NNN}    → Evidence item (EV-001, EV-002, ...)
CL-{NNN}    → Claim (CL-001, CL-002, ...)
C-{NNN}     → Citation code (C-001, C-002, ...)
Q-{NNN}     → Query signature reference (Q-001, Q-002, ...)
```

IDs เป็น sequential per session — reset ทุก chat session ใหม่

### C. Trust Level Criteria

| Level | เกณฑ์ | ตัวอย่าง |
|-------|-------|---------|
| **high** | ข้อมูลจากแหล่งที่ verified แล้ว | Document RAG (uploaded by admin), mart tables (aggregated & reviewed) |
| **medium** | ข้อมูลจากแหล่งที่น่าเชื่อถือแต่ไม่ได้ verify | fact tables (raw import), custom SQL results |
| **low** | ข้อมูลจากแหล่งภายนอกที่ไม่ได้ควบคุม | External API (weather, ThaiJO), web scraping |

### D. เอกสารอ้างอิง

| เอกสาร | ตำแหน่ง |
|--------|---------|
| Agent Architecture | `Agent/doc/ARCHITECTURE.md` |
| Agent SRS | `Agent/doc/SRS.md` |
| Agent DB & API Reference | `Agent/doc/DATABASE_API_REFERENCE.md` |
| Agent Project Documentation | `Agent/doc/PROJECT_DOCUMENTATION.md` |
| Agent SQL Specialist | `Agent/doc/SQL_SPECIALIST_AGENT.md` |
| Chat- Architecture | `Chat-/doc/ARCHITECTURE.md` |
