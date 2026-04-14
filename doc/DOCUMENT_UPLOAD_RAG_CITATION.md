# Document Upload & RAG Citation System — Implementation Spec

> **Phase**: 2B — Document Upload + APA Citation UI  
> **Date**: 2026-04-13  
> **Status**: Design / Ready for Implementation  
> **Dependencies**: Migration 011 (pgvector), Evidence Layer (Migration 010)

---

## 1. Overview

ระบบปัจจุบันรองรับ **document ingestion จาก MinIO** ผ่าน `POST /api/ingest` แต่ยังขาด:

1. **Direct File Upload API** — ผู้ใช้ต้อง upload ไฟล์เข้า MinIO เองก่อน เรียก ingest
2. **Document Management UI** — ไม่มีหน้าจัดการเอกสาร ดูสถานะ ลบ/แก้ไข metadata
3. **APA Citation Display** — citation ปัจจุบันเป็น short code (C-001) ไม่มี format มาตรฐาน APA
4. **Source Link Tracking** — ไม่มี UI แสดง link ย้อนกลับไปยัง MinIO หรือ external URL

เอกสารนี้ออกแบบระบบเพื่อแก้ทั้ง 4 จุด โดยต่อยอดจาก infrastructure ที่มีอยู่

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js / Test UI)                               │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────────────┐  │
│  │ Upload     │ │ Document     │ │ Citation Panel        │  │
│  │ Dropzone   │ │ Library      │ │ (APA + Source Links)  │  │
│  └─────┬──────┘ └──────┬───────┘ └──────────┬────────────┘  │
│        │               │                    │               │
└────────┼───────────────┼────────────────────┼───────────────┘
         │               │                    │
    ┌────▼────┐   ┌──────▼──────┐   ┌────────▼────────┐
    │ Upload  │   │ Documents   │   │ Citation        │
    │ API     │   │ List API    │   │ API             │
    └────┬────┘   └──────┬──────┘   └────────┬────────┘
         │               │                    │
    ┌────▼────────────────▼────────────────────▼──────────┐
    │  FastAPI Backend (port 8000)                        │
    │  ┌────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │ upload.py   │  │ documents.py │  │ citation.py│  │
    │  │ (new)       │  │ (new)        │  │ (new)      │  │
    │  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │
    │         │                │                 │         │
    │  ┌──────▼────────────────▼─────────────────▼──────┐  │
    │  │         document_registry (enhanced)           │  │
    │  │         document_embeddings (existing)         │  │
    │  │         evidence_registry (existing)           │  │
    │  └──────┬────────────────┬─────────────────┬──────┘  │
    │         │                │                 │         │
    │    ┌────▼────┐    ┌──────▼──────┐   ┌──────▼──────┐  │
    │    │ MinIO   │    │ pgvector    │   │ PostgreSQL  │  │
    │    │ Storage │    │ Embeddings  │   │ Metadata    │  │
    │    └─────────┘    └─────────────┘   └─────────────┘  │
    └─────────────────────────────────────────────────────┘
```

---

## 3. Database Changes

### 3.1 Migration 012: Enhanced Document Registry

```sql
-- database/012_document_upload_enhanced.sql

-- Enhance document_registry with upload tracking and APA metadata
ALTER TABLE document_registry
  ADD COLUMN IF NOT EXISTS file_size       BIGINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS content_type    VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS upload_method   VARCHAR(20) DEFAULT 'minio',   -- 'upload' | 'minio' | 'url'
  ADD COLUMN IF NOT EXISTS uploaded_by     VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS uploaded_at     TIMESTAMP DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'processing' | 'completed' | 'failed'
  ADD COLUMN IF NOT EXISTS chunk_count     INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_message   TEXT DEFAULT '',
  
  -- APA Metadata Fields
  ADD COLUMN IF NOT EXISTS apa_authors     TEXT DEFAULT '',         -- "Smith, J., & Doe, A."
  ADD COLUMN IF NOT EXISTS apa_year        VARCHAR(10) DEFAULT '', -- "2025"
  ADD COLUMN IF NOT EXISTS apa_publisher   VARCHAR(500) DEFAULT '',-- "กรมทางหลวง"
  ADD COLUMN IF NOT EXISTS apa_doi         VARCHAR(200) DEFAULT '',-- DOI if available
  ADD COLUMN IF NOT EXISTS apa_url         VARCHAR(1000) DEFAULT '',-- External URL source
  ADD COLUMN IF NOT EXISTS apa_accessed    DATE,                   -- Date accessed for web sources
  ADD COLUMN IF NOT EXISTS apa_edition     VARCHAR(100) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_volume      VARCHAR(50) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_pages       VARCHAR(50) DEFAULT '',
  ADD COLUMN IF NOT EXISTS apa_type        VARCHAR(50) DEFAULT 'report', -- 'report' | 'book' | 'article' | 'website' | 'dataset' | 'law'
  
  -- Source Link Tracking
  ADD COLUMN IF NOT EXISTS source_type     VARCHAR(20) DEFAULT 'internal', -- 'internal' (MinIO) | 'external' (URL)
  ADD COLUMN IF NOT EXISTS external_url    VARCHAR(2000) DEFAULT '',       -- Original external URL
  ADD COLUMN IF NOT EXISTS minio_path      VARCHAR(1000) DEFAULT '';       -- MinIO object path

-- Index for listing and filtering
CREATE INDEX IF NOT EXISTS idx_doc_registry_status ON document_registry(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_doc_registry_uploaded ON document_registry(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_registry_source_type ON document_registry(source_type);
```

---

## 4. API Endpoints

### 4.1 File Upload — `src/routers/upload.py` (NEW)

#### `POST /api/documents/upload`

Upload file -> MinIO -> register -> auto-ingest -> pgvector

```python
"""Document upload endpoint with auto-ingestion."""

# Request: multipart/form-data
# Fields:
#   file: UploadFile (required) — PDF, DOCX, TXT, MD
#   title: str (optional) — override auto-detected title
#   topic: str (optional) — "accident" | "mental_health" | "nutrition" | "general"
#   apa_authors: str (optional)
#   apa_year: str (optional)
#   apa_publisher: str (optional)
#   apa_doi: str (optional)
#   apa_url: str (optional)
#   apa_type: str (optional) — "report" | "book" | "article" | "website" | "dataset" | "law"
#   external_url: str (optional) — original source URL (for tracking provenance)

# Response:
{
    "status": "ok",
    "document_id": 42,
    "file_path": "uploads/2026/04/policy_2025.pdf",
    "title": "นโยบายความปลอดภัยทางถนน 2025",
    "chunks_ingested": 28,
    "ingestion_status": "completed",
    "apa_citation": "กรมทางหลวง. (2025). นโยบายความปลอดภัยทางถนน 2025. กระทรวงคมนาคม.",
    "source_link": {
        "type": "internal",
        "minio_url": "/api/documents/open/42",
        "external_url": ""
    }
}
```

**Implementation Flow:**

```python
@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile,
    title: str = Form(""),
    topic: str = Form("general"),
    apa_authors: str = Form(""),
    apa_year: str = Form(""),
    apa_publisher: str = Form(""),
    apa_doi: str = Form(""),
    apa_url: str = Form(""),
    apa_type: str = Form("report"),
    external_url: str = Form(""),
):
    # 1. Validate file type
    allowed = {".pdf", ".docx", ".txt", ".md"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # 2. Read file content
    content = await file.read()
    file_size = len(content)

    # 3. Upload to MinIO with structured path
    #    Pattern: uploads/{year}/{month}/{sanitized_filename}
    now = datetime.now()
    minio_path = f"uploads/{now.year}/{now.month:02d}/{file.filename}"
    upload_to_minio(minio_path, content, file.content_type)

    # 4. Register in document_registry
    doc_title = title or _extract_title_from_name(file.filename)
    doc_id = insert_document_registry(
        title=doc_title,
        file_path=minio_path,
        document_type=ext.lstrip("."),
        file_size=file_size,
        content_type=file.content_type,
        upload_method="upload",
        topic=topic,
        apa_authors=apa_authors,
        apa_year=apa_year,
        apa_publisher=apa_publisher,
        apa_doi=apa_doi,
        apa_url=apa_url,
        apa_type=apa_type,
        external_url=external_url,
        source_type="external" if external_url else "internal",
        minio_path=minio_path,
        ingestion_status="processing",
    )

    # 5. Auto-ingest: extract text -> chunk -> embed -> pgvector
    try:
        chunk_count = ingest_single_document(minio_path, content, doc_id, topic)
        update_ingestion_status(doc_id, "completed", chunk_count)
    except Exception as e:
        update_ingestion_status(doc_id, "failed", 0, str(e))
        raise HTTPException(500, f"Ingestion failed: {e}")

    # 6. Generate APA citation preview
    apa_text = generate_apa_citation(doc_id)

    return {
        "status": "ok",
        "document_id": doc_id,
        "file_path": minio_path,
        "title": doc_title,
        "chunks_ingested": chunk_count,
        "ingestion_status": "completed",
        "apa_citation": apa_text,
        "source_link": {
            "type": "external" if external_url else "internal",
            "minio_url": f"/api/documents/open/{doc_id}",
            "external_url": external_url,
        },
    }
```

#### `POST /api/documents/upload-url`

Register an external URL document (download + ingest).

```python
# Request JSON:
{
    "url": "https://example.go.th/report-2025.pdf",
    "title": "รายงานอุบัติเหตุ 2025",
    "topic": "accident",
    "apa_authors": "กรมทางหลวง",
    "apa_year": "2025",
    "apa_publisher": "กระทรวงคมนาคม",
    "apa_type": "report"
}

# Response: Same as /api/documents/upload
# Backend will:
#   1. Download file from URL
#   2. Store a copy in MinIO (backup)
#   3. Register with source_type="external", external_url=original URL
#   4. Auto-ingest into pgvector
```

### 4.2 Document Management — `src/routers/documents.py` (NEW)

#### `GET /api/documents`

List all registered documents with filters.

```python
# Query params:
#   status: str = "" — filter by ingestion_status
#   topic: str = "" — filter by topic
#   source_type: str = "" — "internal" | "external"
#   search: str = "" — title/filename search
#   page: int = 1
#   per_page: int = 20
#   sort: str = "uploaded_at" — sort field
#   order: str = "desc"

# Response:
{
    "total": 45,
    "page": 1,
    "per_page": 20,
    "documents": [
        {
            "document_id": 42,
            "title": "นโยบายความปลอดภัยทางถนน 2025",
            "document_type": "pdf",
            "file_size": 2048576,
            "topic": "accident",
            "uploaded_at": "2026-04-13T10:30:00",
            "ingestion_status": "completed",
            "chunk_count": 28,
            "source_type": "internal",
            "minio_url": "/api/documents/open/42",
            "external_url": "",
            "apa_citation": "กรมทางหลวง. (2025). นโยบายความปลอดภัยทางถนน 2025. กระทรวงคมนาคม.",
            "apa_type": "report"
        }
    ]
}
```

#### `GET /api/documents/{document_id}`

Get single document detail with full APA metadata.

```python
# Response:
{
    "document_id": 42,
    "title": "นโยบายความปลอดภัยทางถนน 2025",
    "document_type": "pdf",
    "file_path": "uploads/2026/04/policy_2025.pdf",
    "file_size": 2048576,
    "total_pages": 45,
    "topic": "accident",
    "uploaded_at": "2026-04-13T10:30:00",
    "uploaded_by": "admin",
    "upload_method": "upload",
    "ingestion_status": "completed",
    "chunk_count": 28,

    "source_type": "internal",
    "minio_url": "/api/documents/open/42",
    "external_url": "",

    "apa": {
        "authors": "กรมทางหลวง",
        "year": "2025",
        "title": "นโยบายความปลอดภัยทางถนน 2025",
        "publisher": "กระทรวงคมนาคม",
        "doi": "",
        "url": "",
        "accessed": null,
        "edition": "",
        "volume": "",
        "pages": "",
        "type": "report",
        "formatted": "กรมทางหลวง. (2025). นโยบายความปลอดภัยทางถนน 2025. กระทรวงคมนาคม."
    },

    "chunks_preview": [
        {"chunk_index": 0, "section_label": "บทที่ 1 บทนำ", "page_ref": "1", "text_preview": "..."},
        {"chunk_index": 1, "section_label": "บทที่ 1 บทนำ", "page_ref": "2", "text_preview": "..."}
    ]
}
```

#### `PATCH /api/documents/{document_id}`

Update document metadata (title, APA fields, topic).

```python
# Request JSON (partial update):
{
    "title": "Updated Title",
    "apa_authors": "สำนักงานตำรวจแห่งชาติ",
    "apa_year": "2025",
    "topic": "accident"
}

# Response: Updated document object
```

#### `DELETE /api/documents/{document_id}`

Delete document from registry, MinIO, and pgvector.

```python
# Response:
{
    "status": "deleted",
    "document_id": 42,
    "chunks_removed": 28,
    "minio_removed": true
}
```

#### `POST /api/documents/{document_id}/reingest`

Re-ingest a document (e.g., after embedding model change).

```python
# Response: Same as upload response
```

### 4.3 Citation API — `src/routers/citation.py` (NEW)

#### `GET /api/citations/session/{session_id}`

Get all citations for a chat session in APA format.

```python
# Response:
{
    "session_id": "abc-123",
    "citation_style": "APA7",
    "citations": [
        {
            "citation_code": "C-001",
            "inline_text": "(กรมทางหลวง, 2025, หน้า 12)",
            "reference_text": "กรมทางหลวง. (2025). นโยบายความปลอดภัยทางถนน 2025 (หน้า 12). กระทรวงคมนาคม.",
            "evidence_type": "document",
            "trust_level": "high",
            "source_link": {
                "type": "internal",
                "url": "/api/documents/open/42?page=12",
                "label": "เปิดเอกสาร หน้า 12"
            }
        },
        {
            "citation_code": "C-002",
            "inline_text": "(Musya Agent Database, 2025)",
            "reference_text": "Musya Agent. (2025). ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัด [Data set]. mart_province_year.",
            "evidence_type": "database",
            "trust_level": "high",
            "source_link": {
                "type": "database",
                "url": "/api/evidence/EV-002/query",
                "label": "ดู SQL Query"
            }
        },
        {
            "citation_code": "C-003",
            "inline_text": "(WHO, 2024)",
            "reference_text": "World Health Organization. (2024). Global status report on road safety 2024. https://www.who.int/publications/road-safety-2024",
            "evidence_type": "document",
            "trust_level": "high",
            "source_link": {
                "type": "external",
                "url": "https://www.who.int/publications/road-safety-2024",
                "label": "เปิดเว็บไซต์ต้นทาง"
            }
        }
    ],
    "reference_list_html": "<div class='apa-references'>...</div>"
}
```

---

## 5. APA Citation Generator

### 5.1 `src/utils/apa_formatter.py` (NEW)

APA 7th Edition formatter supporting Thai and English documents.

```python
"""APA 7th Edition citation formatter.

Supports document types:
  - report    : รายงาน/เอกสารราชการ
  - book      : หนังสือ
  - article   : บทความวิชาการ
  - website   : เว็บไซต์
  - dataset   : ชุดข้อมูล
  - law       : กฎหมาย/ประกาศราชกิจจาฯ
"""

def format_apa_reference(doc: dict) -> str:
    """Format a document_registry row into APA 7th reference string.

    APA 7 patterns:
      report:  Author. (Year). Title. Publisher.
      book:    Author. (Year). Title (Edition). Publisher.
      article: Author. (Year). Title. Journal, Volume(Issue), Pages. DOI
      website: Author. (Year, Month Day). Title. Site Name. URL
      dataset: Author. (Year). Title [Data set]. Source.
      law:     ชื่อกฎหมาย, พ.ศ. ปี. ราชกิจจานุเบกษา เล่ม x ตอนที่ y.
    """
    apa_type = doc.get("apa_type", "report")
    authors  = doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")
    year     = doc.get("apa_year", "") or "n.d."
    title    = doc.get("title", "ไม่ระบุชื่อ")
    publisher = doc.get("apa_publisher", "")
    doi      = doc.get("apa_doi", "")
    url      = doc.get("apa_url", "") or doc.get("external_url", "")
    edition  = doc.get("apa_edition", "")
    volume   = doc.get("apa_volume", "")
    pages    = doc.get("apa_pages", "")

    # --- Build by type ---
    if apa_type == "report":
        ref = f"{authors}. ({year}). {_italicize(title)}."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "book":
        ed = f" ({edition})" if edition else ""
        ref = f"{authors}. ({year}). {_italicize(title)}{ed}."
        if publisher:
            ref += f" {publisher}."

    elif apa_type == "article":
        ref = f"{authors}. ({year}). {title}."
        if publisher:  # journal name
            ref += f" {_italicize(publisher)}"
        if volume:
            ref += f", {volume}"
        if pages:
            ref += f", {pages}"
        ref += "."
        if doi:
            ref += f" https://doi.org/{doi}"
        elif url:
            ref += f" {url}"

    elif apa_type == "website":
        accessed = doc.get("apa_accessed", "")
        ref = f"{authors}. ({year}). {_italicize(title)}."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "dataset":
        ref = f"{authors}. ({year}). {_italicize(title)} [Data set]."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "law":
        ref = f"{title}, {authors} ({year})."
        if volume:
            ref += f" ราชกิจจานุเบกษา เล่ม {volume}."

    else:
        ref = f"{authors}. ({year}). {_italicize(title)}."

    return ref.strip()


def format_apa_inline(doc: dict, page_ref: str = "") -> str:
    """Format inline citation: (Author, Year, p. X)"""
    authors = doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")
    # Shorten to first author + et al. if multiple
    author_short = _shorten_author(authors)
    year = doc.get("apa_year", "") or "n.d."

    cite = f"({author_short}, {year}"
    if page_ref:
        cite += f", หน้า {page_ref}"
    cite += ")"
    return cite


def format_database_reference(table_name: str, year: str = "") -> str:
    """Format database source as APA dataset reference."""
    yr = year or "2025"
    table_labels = {
        "mart_province_year": "ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี",
        "mart_accident_summary": "ฐานข้อมูลสรุปอุบัติเหตุรายเดือน",
        "mart_accident_hotspot": "ฐานข้อมูลจุดเสี่ยงอุบัติเหตุ",
        "mart_province_road": "ฐานข้อมูลถนนเสี่ยงรายจังหวัด",
        "fact_accident_event": "ฐานข้อมูลเหตุการณ์อุบัติเหตุ",
    }
    label = table_labels.get(table_name, table_name)
    return f"Musya Agent. ({yr}). {label} [Data set]. {table_name}."


def _italicize(text: str) -> str:
    """Wrap in italic markers (Markdown)."""
    return f"*{text}*"


def _shorten_author(authors: str) -> str:
    """Shorten multi-author string to first + et al."""
    if "," in authors and "&" in authors:
        first = authors.split(",")[0].strip()
        return f"{first} et al."
    return authors
```

### 5.2 APA Formatting Rules (Thai context)

| Document Type | APA Format | Example |
|---|---|---|
| **report** | ผู้แต่ง. (ปี). *ชื่อเรื่อง*. สำนักพิมพ์. | กรมทางหลวง. (2025). *นโยบายความปลอดภัยทางถนน 2025*. กระทรวงคมนาคม. |
| **book** | ผู้แต่ง. (ปี). *ชื่อหนังสือ* (พิมพ์ครั้งที่ x). สำนักพิมพ์. | สมชาย ใจดี. (2024). *การวิเคราะห์อุบัติเหตุจราจร* (พิมพ์ครั้งที่ 2). สำนักพิมพ์ ABC. |
| **article** | ผู้แต่ง. (ปี). ชื่อบทความ. *วารสาร*, เล่ม(ฉบับ), หน้า. DOI | สมหญิง รักดี. (2024). แนวโน้มอุบัติเหตุ. *วารสารความปลอดภัย*, 12(3), 45-60. |
| **website** | ผู้แต่ง. (ปี). *ชื่อหน้า*. ชื่อเว็บ. URL | WHO. (2024). *Global road safety report*. https://who.int/... |
| **dataset** | ผู้แต่ง. (ปี). *ชื่อชุดข้อมูล* [Data set]. แหล่งข้อมูล. | Musya Agent. (2025). *ฐานข้อมูลสรุปอุบัติเหตุ* [Data set]. mart_accident_summary. |
| **law** | ชื่อกฎหมาย, พ.ศ. ปี. ราชกิจจาฯ | พ.ร.บ.จราจรทางบก, พ.ศ. 2522. ราชกิจจานุเบกษา เล่ม 96. |
| **inline** | (ผู้แต่ง, ปี, หน้า X) | (กรมทางหลวง, 2025, หน้า 12) |

---

## 6. Source Link System

### 6.1 Link Types

| Source Type | Storage | URL Pattern | UI Action |
|---|---|---|---|
| **internal** (MinIO) | MinIO bucket | `/api/documents/open/{doc_id}?page={n}` | Open inline PDF viewer / download |
| **external** (URL) | MinIO (cached copy) + original URL | Original URL stored in `external_url` | Open in new tab OR fallback to cached MinIO copy |
| **database** | PostgreSQL | `/api/evidence/{ev_id}/query` | Show SQL query + result preview |

### 6.2 Source Link Resolution Logic

```python
def resolve_source_link(evidence: dict) -> dict:
    """Resolve the best available link for an evidence item."""
    ev_type = evidence.get("evidence_type", "")
    source_type = evidence.get("source_type", "internal")

    if ev_type == "document":
        doc_id = evidence.get("document_id")
        page_ref = evidence.get("page_ref", "")
        external_url = evidence.get("external_url", "")

        if source_type == "external" and external_url:
            return {
                "type": "external",
                "primary_url": external_url,
                "fallback_url": f"/api/documents/open/{doc_id}" + (f"?page={page_ref}" if page_ref else ""),
                "label": "เปิดเว็บไซต์ต้นทาง",
                "icon": "external-link"
            }
        else:
            return {
                "type": "internal",
                "primary_url": f"/api/documents/open/{doc_id}" + (f"?page={page_ref}" if page_ref else ""),
                "fallback_url": None,
                "label": f"เปิดเอกสาร" + (f" หน้า {page_ref}" if page_ref else ""),
                "icon": "file-text"
            }

    elif ev_type == "database":
        ev_id = evidence.get("evidence_id", "")
        return {
            "type": "database",
            "primary_url": f"/api/evidence/{ev_id}/query",
            "fallback_url": None,
            "label": "ดู SQL Query และผลลัพธ์",
            "icon": "database"
        }

    return {"type": "unknown", "primary_url": "", "fallback_url": None, "label": "ไม่ทราบแหล่งที่มา", "icon": "help-circle"}
```

---

## 7. Test UI — Citation & Source Panel

### 7.1 File: `static/document_upload_ui.html` (NEW)

Standalone test UI for testing upload + citation + source links.

### 7.2 UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Musya Agent — Document & Citation Manager                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Tab: Upload] [Tab: Library] [Tab: Citations] [Tab: Chat Test] │
│                                                                 │
│  ═══════════════════════════════════════════════════════════════ │
│                                                                 │
│  ┌─── Upload Tab ───────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  ┌────────────────────────────────┐                      │   │
│  │  │        Drop files here         │  Supported:          │   │
│  │  │     or click to browse         │  PDF, DOCX, TXT, MD  │   │
│  │  │     [  Choose File  ]          │                      │   │
│  │  └────────────────────────────────┘                      │   │
│  │                                                          │   │
│  │  ── OR ──                                                │   │
│  │  External URL: [ https://example.com/doc.pdf    ] [Fetch]│   │
│  │                                                          │   │
│  │  ── Document Metadata ──                                 │   │
│  │  Title:     [ _____________________________________ ]    │   │
│  │  Topic:     [ accident ▼ ]                               │   │
│  │  Doc Type:  [ report ▼ ]  (report/book/article/web/...) │   │
│  │                                                          │   │
│  │  ── APA Metadata (Optional) ──                           │   │
│  │  Authors:   [ _____________________________________ ]    │   │
│  │  Year:      [ 2025  ]                                    │   │
│  │  Publisher:  [ _____________________________________ ]   │   │
│  │  DOI:       [ _____________________________________ ]    │   │
│  │  Edition:   [ _______ ]  Volume: [ ____ ] Pages: [ ___ ]│   │
│  │                                                          │   │
│  │  ── APA Preview ──                                       │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │ กรมทางหลวง. (2025). *นโยบายความปลอดภัยทาง       │    │   │
│  │  │ ถนน 2025*. กระทรวงคมนาคม.                        │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  [    Upload & Ingest    ]                               │   │
│  │                                                          │   │
│  │  ── Upload Progress ──                                   │   │
│  │  ████████████████░░░░  80% — Embedding chunks...         │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─── Library Tab ──────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  Filter: [All ▼] [accident ▼] [completed ▼] [Search___] │   │
│  │                                                          │   │
│  │  ┌────┬──────────────────────┬──────┬───────┬─────────┐  │   │
│  │  │ ID │ Title                │ Type │Chunks │ Status  │  │   │
│  │  ├────┼──────────────────────┼──────┼───────┼─────────┤  │   │
│  │  │ 42 │ นโยบายความปลอดภัยฯ  │ PDF  │  28   │ ✅ Done │  │   │
│  │  │    │ 📄 MinIO  |  🔗 -   │      │       │         │  │   │
│  │  ├────┼──────────────────────┼──────┼───────┼─────────┤  │   │
│  │  │ 43 │ WHO Road Safety 2024 │ PDF  │  56   │ ✅ Done │  │   │
│  │  │    │ 📄 MinIO  |  🔗 URL │      │       │         │  │   │
│  │  ├────┼──────────────────────┼──────┼───────┼─────────┤  │   │
│  │  │ 44 │ สรุปสถิติ 2568       │ DOCX │  12   │ ❌ Fail │  │   │
│  │  │    │ 📄 MinIO  |  🔗 -   │      │       │ [Retry] │  │   │
│  │  └────┴──────────────────────┴──────┴───────┴─────────┘  │   │
│  │                                                          │   │
│  │  Showing 1-20 of 45  [ < ] [ 1 ] [ 2 ] [ 3 ] [ > ]     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─── Citations Tab ────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  Session: [ abc-123______ ] [Load Citations]             │   │
│  │                                                          │   │
│  │  ── Reference List (APA 7th Edition) ──                  │   │
│  │                                                          │   │
│  │  [C-001] 🟢 High Trust                                  │   │
│  │  กรมทางหลวง. (2025). *นโยบายความปลอดภัยทางถนน 2025*     │   │
│  │    (หน้า 12). กระทรวงคมนาคม.                             │   │
│  │  📄 [เปิดเอกสาร หน้า 12]                                │   │
│  │                                                          │   │
│  │  [C-002] 🟢 High Trust                                  │   │
│  │  Musya Agent. (2025). *ฐานข้อมูลสรุปอุบัติเหตุราย       │   │
│  │    จังหวัด* [Data set]. mart_province_year.              │   │
│  │  🗄️ [ดู SQL Query]                                     │   │
│  │                                                          │   │
│  │  [C-003] 🟢 High Trust                                  │   │
│  │  WHO. (2024). *Global status report on road safety*.     │   │
│  │    https://www.who.int/publications/road-safety-2024     │   │
│  │  🔗 [เปิดเว็บไซต์ต้นทาง]                                │   │
│  │                                                          │   │
│  │  ── Coverage Report ──                                   │   │
│  │  Total Claims: 12  |  Supported: 10  |  Partial: 1      │   │
│  │  Unsupported: 1    |  Coverage: 83.3%                    │   │
│  │  ████████████████░░░░  83.3%                             │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Key UI Components

#### A. APA Reference Card

```html
<!-- Single citation reference card -->
<div class="citation-card">
  <div class="citation-header">
    <span class="citation-code">[C-001]</span>
    <span class="trust-badge trust-high">🟢 High Trust</span>
    <span class="evidence-type-badge">📄 Document</span>
  </div>
  <div class="citation-body apa-reference">
    <!-- APA formatted text with italic title -->
    กรมทางหลวง. (2025). <em>นโยบายความปลอดภัยทางถนน 2025</em>
    (หน้า 12). กระทรวงคมนาคม.
  </div>
  <div class="citation-footer">
    <!-- Source link with icon -->
    <a href="/api/documents/open/42?page=12" target="_blank" class="source-link">
      📄 เปิดเอกสาร หน้า 12
    </a>
    <!-- Fallback link if external -->
    <a href="https://original-source.com" target="_blank" class="source-link external">
      🔗 เปิดเว็บไซต์ต้นทาง
    </a>
  </div>
</div>
```

#### B. Source Link Badge

```html
<!-- Internal MinIO document -->
<span class="source-badge internal" title="เก็บใน MinIO">
  📄 <a href="/api/documents/open/42">MinIO</a>
</span>

<!-- External URL source -->
<span class="source-badge external" title="แหล่งภายนอก">
  🔗 <a href="https://who.int/..." target="_blank">URL</a>
</span>

<!-- Database source -->
<span class="source-badge database" title="ฐานข้อมูล">
  🗄️ <a href="/api/evidence/EV-002/query">mart_province_year</a>
</span>
```

---

## 8. Integration with Existing Agent Pipeline

### 8.1 Changes to `search_documents` Tool

Update `src/tools/common.py` to include `document_id` and APA data in search results:

```python
# In search_documents tool, add to returned evidence_items:
{
    "evidence_id": "EV-XXX",
    "source_ref": "policy_2025.pdf",
    "document_id": 42,                    # NEW: for source link
    "apa_citation": "กรมทางหลวง. (2025)...",  # NEW: pre-formatted APA
    "source_link": {                       # NEW: resolved link
        "type": "internal",
        "url": "/api/documents/open/42?page=12",
    },
    # ... existing fields
}
```

### 8.2 Changes to Citation & Evidence Agent

Update `src/agents/citation_evidence.py` to use APA formatter:

```python
# In citation generation, replace simple bibliography_text with APA:
from src.utils.apa_formatter import format_apa_reference, format_apa_inline, format_database_reference

# For document evidence:
citation.bibliography_text = format_apa_reference(doc_registry_row)
citation.citation_text = format_apa_inline(doc_registry_row, page_ref=page)

# For database evidence:
citation.bibliography_text = format_database_reference(table_name, year)
citation.citation_text = f"(Musya Agent Database, {year})"
```

### 8.3 Changes to `EnhancedCitation` Schema

Update `src/schemas/evidence.py`:

```python
class EnhancedCitation(BaseModel):
    citation_code: str
    evidence_id: str
    source_type: str
    source_ref: str
    citation_text: str          # APA inline: (Author, Year, p. X)
    bibliography_text: str      # APA reference list entry
    open_url: str               # Primary source link
    trust_level: str

    # NEW fields for source link system
    source_link: dict = Field(default_factory=dict)  # {type, primary_url, fallback_url, label, icon}
    document_id: int | None = Field(None)             # Link back to document_registry
    apa_type: str = Field("report")                   # APA document type
```

---

## 9. Implementation Plan

### Phase 1: Backend APIs (Priority: High)

| # | Task | File | Effort |
|---|------|------|--------|
| 1 | Create migration 012 | `database/012_document_upload_enhanced.sql` | S |
| 2 | Create upload router | `src/routers/upload.py` | M |
| 3 | Create documents router | `src/routers/documents.py` | M |
| 4 | Create APA formatter utility | `src/utils/apa_formatter.py` | M |
| 5 | Create citation router | `src/routers/citation.py` | S |
| 6 | Add `ingest_single_document()` to document_rag.py | `src/rag/document_rag.py` | S |
| 7 | Add `upload_to_minio()` to minio_client.py | `src/db/minio_client.py` | S |
| 8 | Register new routers in main.py | `src/main.py` | S |

### Phase 2: UI (Priority: Medium)

| # | Task | File | Effort |
|---|------|------|--------|
| 9 | Build upload + library + citation test UI | `static/document_upload_ui.html` | L |
| 10 | Add document_upload_ui route to test_ui.py | `src/routers/test_ui.py` | S |

### Phase 3: Agent Integration (Priority: Medium)

| # | Task | File | Effort |
|---|------|------|--------|
| 11 | Update search_documents to include document_id & APA | `src/tools/common.py` | S |
| 12 | Update Citation Agent to use APA formatter | `src/agents/citation_evidence.py` | M |
| 13 | Update EnhancedCitation schema | `src/schemas/evidence.py` | S |
| 14 | Update orchestrator to pass APA data through pipeline | `src/agents/orchestrator.py` | S |

### Phase 4: Testing

| # | Task | File | Effort |
|---|------|------|--------|
| 15 | API tests for upload, documents, citation endpoints | `tests/test_upload.py` | M |
| 16 | APA formatter unit tests (Thai + English) | `tests/test_apa_formatter.py` | M |
| 17 | Integration test: upload → ingest → search → cite | `tests/test_integration_upload.py` | M |

**Effort**: S = ~1-2 hours, M = ~3-5 hours, L = ~1 day

---

## 10. File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `database/012_document_upload_enhanced.sql` | Migration: enhanced document_registry |
| `src/routers/upload.py` | File upload + URL import endpoints |
| `src/routers/documents.py` | Document CRUD + listing endpoints |
| `src/routers/citation.py` | APA citation retrieval endpoints |
| `src/utils/__init__.py` | Utils package init |
| `src/utils/apa_formatter.py` | APA 7th Edition formatter |
| `static/document_upload_ui.html` | Test UI for upload + library + citations |
| `tests/test_upload.py` | Upload API tests |
| `tests/test_apa_formatter.py` | APA formatter tests |

### Modified Files

| File | Change |
|------|--------|
| `src/main.py` | Register new routers (upload, documents, citation) |
| `src/db/minio_client.py` | Add `upload_to_minio()` function |
| `src/rag/document_rag.py` | Add `ingest_single_document()` for single-file ingestion |
| `src/tools/common.py` | Include document_id and APA data in search results |
| `src/schemas/evidence.py` | Add source_link, document_id, apa_type to EnhancedCitation |
| `src/agents/citation_evidence.py` | Use APA formatter for citation generation |
| `src/routers/test_ui.py` | Add route for document_upload_ui |

---

## 11. Example Flows

### Flow A: Upload PDF → RAG Search → APA Citation

```
1. User uploads "road_safety_2025.pdf" via UI
   → POST /api/documents/upload
   → file + metadata (authors, year, publisher, topic)

2. Backend:
   a. Upload to MinIO: uploads/2026/04/road_safety_2025.pdf
   b. Register in document_registry (id=42)
   c. Extract text (PyMuPDF), chunk (1000/200), embed (Gemini)
   d. Insert 28 chunks into document_embeddings
   e. Return: {document_id: 42, chunks: 28, apa_citation: "..."}

3. User asks: "นโยบายความปลอดภัยทางถนนปี 2025 มีอะไรบ้าง?"

4. Agent pipeline:
   a. Retrieval → search_documents("นโยบายความปลอดภัย 2025")
      → Returns chunks from doc_id=42, with APA metadata
   b. Citation Agent → format as APA:
      Inline: (กรมทางหลวง, 2025, หน้า 12)
      Reference: กรมทางหลวง. (2025). *นโยบายความปลอดภัยทางถนน 2025*. กระทรวงคมนาคม.
   c. Source link: {type: "internal", url: "/api/documents/open/42?page=12"}

5. Response includes:
   - Content with inline citations
   - Reference list in APA format
   - Clickable source links (open PDF at page 12)
```

### Flow B: Import External URL → Dual Source Link

```
1. User submits URL: https://www.who.int/report-2024.pdf
   → POST /api/documents/upload-url

2. Backend:
   a. Download PDF from URL
   b. Upload copy to MinIO (backup)
   c. Register with source_type="external", external_url=original
   d. Ingest into pgvector

3. Later citation shows:
   Reference: WHO. (2024). *Global status report on road safety 2024*.
              https://www.who.int/report-2024.pdf
   Links:
   - 🔗 [เปิดเว็บไซต์ต้นทาง] → original URL
   - 📄 [เปิด MinIO (สำเนา)] → /api/documents/open/43
```

---

## 12. Security Considerations

| Concern | Mitigation |
|---------|------------|
| File size | Max 50MB per upload; enforce in FastAPI `UploadFile` |
| File type | Allowlist: .pdf, .docx, .txt, .md only |
| Filename injection | Sanitize filename, strip path separators |
| MinIO path traversal | Prefix all paths with `uploads/` |
| External URL SSRF | Validate URL scheme (http/https only), block private IPs |
| SQL injection in search | All queries use parameterized statements (existing) |
| XSS in citation text | HTML-escape all user-provided metadata before rendering |

---

## 13. Configuration Changes

Add to `.env.example`:

```env
# Document Upload
MAX_UPLOAD_SIZE_MB=50
ALLOWED_FILE_TYPES=.pdf,.docx,.txt,.md
AUTO_INGEST_ON_UPLOAD=true

# External URL Import
ALLOW_EXTERNAL_URL_IMPORT=true
EXTERNAL_URL_TIMEOUT=30
```

Add to `src/config.py`:

```python
# Document Upload
MAX_UPLOAD_SIZE_MB: int = 50
ALLOWED_FILE_TYPES: str = ".pdf,.docx,.txt,.md"
AUTO_INGEST_ON_UPLOAD: bool = True

# External URL Import
ALLOW_EXTERNAL_URL_IMPORT: bool = True
EXTERNAL_URL_TIMEOUT: int = 30
```
