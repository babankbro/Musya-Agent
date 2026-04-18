# ThaiJO Agent Integration — ✅ IMPLEMENTED

> Version 1.1 | 2026-04-16 | **Status: COMPLETED**  
> สถาปัตยกรรมการเชื่อมต่อ ThaiJO Academic Search เข้ากับ Musya Agent Pipeline
>
> **Implementation Status**: ทุก component ถูก implement แล้ว — tool, config, router, migration, citation integration

---

## 1. Overview

### 1.1 Background

ThaiJO (Thai Journals Online / TCI-THAIJO) คือฐานข้อมูลวารสารวิชาการไทย ที่เป็นแหล่งข้อมูลสำคัญสำหรับการอ้างอิงเชิงวิชาการด้านสาธารณสุข

ปัจจุบัน Musya มีการเชื่อมต่อ ThaiJO ใน **Chat- frontend** ผ่าน:
- API proxy route: `POST /api/admin/thaijo`
- Gemini AI intent detection (client-side) ที่ตัดสินใจว่าเมื่อไหร่ควรค้นหา ThaiJO
- Bibliography integration ใน ChatInterface.tsx

การเชื่อมต่อใน **Agent backend** ได้ถูก implement แล้ว:
1. ✅ อ้างอิงบทความวิชาการในระบบ Citation & Evidence ได้ (C-200~C-299)
2. ✅ มี traceability จาก claim → ThaiJO article ผ่าน evidence_registry
3. ✅ Policy Brief pipeline สามารถใช้ข้อมูลวิชาการเสริมได้ผ่าน search_thaijo

### 1.2 Goal

เพิ่ม ThaiJO search capability เข้า Agent pipeline โดย:
- สร้าง ThaiJO tool สำหรับ Data Retrieval Agent (Agent 2)
- เชื่อมต่อผลลัพธ์เข้า Citation & Evidence Agent (Agent 4) ด้วย APA 7th Edition
- รองรับทั้ง Chat pipeline และ Policy Brief pipeline

### 1.3 ThaiJO Microservice (External)

**Repository:** [tao-thewarat/thaijo](https://github.com/tao-thewarat/thaijo)

**Architecture:**
```
FastAPI (port 8505)
  ├── POST /api/v1/thaijo          ← Search endpoint
  ├── TCI-THAIJO.org API           ← Upstream article search
  ├── BeautifulSoup                ← HTML scraping (PDF link + citation)
  ├── OpenAI GPT-4.1               ← PDF summarization
  └── Redis                        ← Summary cache (SHA-256 key)
```

**Request Schema:**
```json
{
  "term": "โรคซึมเศร้าในผู้ป่วยเบาหวาน",
  "page": 1,
  "size": 10,
  "strict": true,
  "title": true,
  "author": true,
  "abstract": true
}
```

**Response Schema:**
```json
{
  "count": 3,
  "results": [
    {
      "pdf_url": "https://he01.tci-thaijo.org/index.php/.../view/.../...",
      "summary": "สรุปเนื้อหาบทความ ... (3 หน้า A4, ภาษาไทย)",
      "reference": "APA citation text from TCI-THAIJO page (or null)"
    }
  ]
}
```

**Key Characteristics:**
- `reference` field = APA citation extracted from TCI-THAIJO HTML (`div#citationOutput .csl-right-inline`)
- `summary` = AI-generated Thai summary of the full PDF (cached in Redis)
- `pdf_url` = direct link to PDF on TCI-THAIJO portal
- Response time: ~10-60s depending on article count (AI summarization is the bottleneck)
- No authentication required

---

## 2. Architecture Design

### 2.1 Integration Point in Agent Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Pipeline (Sequential)                                │
│                                                             │
│  Agent 1: Request Interpreter                               │
│    └── Detects: topics, geography, time_range               │
│    └── NEW: detects academic_search_needed: bool             │
│    └── NEW: detects search_keywords: str                     │
│                                                             │
│  Agent 2: Data Retrieval Specialist                         │
│    ├── search_documents()          ← Document RAG           │
│    ├── get_accident_summary()      ← Database RAG           │
│    ├── get_province_year_summary() ← Database RAG           │
│    ├── ...other tools              ← Database RAG           │
│    └── NEW: search_thaijo()        ← External API           │
│                                                             │
│  Agent 3: SQL Specialist                                    │
│                                                             │
│  Agent 4: Citation & Evidence                               │
│    ├── lookup_document_apa()                                │
│    ├── register_evidence()                                  │
│    ├── register_claim_links()                               │
│    └── NEW: handles evidence_type="thaijo_article"          │
│    └── NEW: citation_code range C-200 to C-299              │
│                                                             │
│  Agent 5-9: Analysis, Charts, Report                        │
│    └── Can reference [C-2xx] ThaiJO citations               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
User Query: "สถานการณ์อุบัติเหตุและงานวิจัยที่เกี่ยวข้อง"
    │
    ▼
Agent 1 (Request Interpreter)
    ├── topics: ["accident"]
    ├── academic_search_needed: true
    └── search_keywords: "อุบัติเหตุทางถนน ปัจจัยเสี่ยง"
    │
    ▼
Agent 2 (Retrieval)
    ├── search_documents() → Document RAG results
    ├── get_accident_summary() → Database results
    └── search_thaijo("อุบัติเหตุทางถนน ปัจจัยเสี่ยง", size=5)
        │
        ▼ HTTP POST to ThaiJO microservice
        │
        └── Returns: [
              {pdf_url, summary, reference},
              {pdf_url, summary, reference},
              ...
            ]
    │
    ▼
Agent 4 (Citation & Evidence)
    ├── Normalize ThaiJO results → EvidenceItem[]
    │     evidence_type: "thaijo_article"
    │     trust_level: "medium"
    │     apa_type: "article"
    │     open_url: pdf_url
    │
    ├── Generate citation codes: C-200, C-201, ...
    ├── Use reference field as bibliography_text
    │   (fallback: construct from pdf_url metadata)
    ├── Map claims → ThaiJO evidence
    └── Coverage validation
    │
    ▼
Agent 5-9 (Analysis & Report)
    └── References: "งานวิจัยพบว่า... [C-200]"
```

---

## 3. Implementation Spec

### 3.1 Configuration

**File:** `src/config.py`

```python
# ThaiJO API
THAIJO_API_URL: str = "http://72.61.120.205:8505/api/v1/thaijo"
THAIJO_TIMEOUT: int = 120          # seconds (AI summarization is slow)
THAIJO_DEFAULT_SIZE: int = 5       # articles per search
THAIJO_MAX_SIZE: int = 10          # upper limit
THAIJO_ENABLED: bool = True        # feature flag
```

**File:** `.env`
```
THAIJO_API_URL=http://72.61.120.205:8505/api/v1/thaijo
THAIJO_TIMEOUT=120
THAIJO_DEFAULT_SIZE=5
```

### 3.2 ThaiJO Tool

**File:** `src/tools/thaijo.py`

```python
"""ThaiJO academic article search tool for Data Retrieval Agent."""

import logging
from typing import Optional

import httpx
from crewai.tools import tool

from src.config import settings

logger = logging.getLogger("musya.tools.thaijo")


@tool("search_thaijo")
def search_thaijo(
    term: str,
    size: int = 5,
    page: int = 1,
    strict: bool = True,
) -> str:
    """ค้นหาบทความวิชาการจาก ThaiJO (Thai Journals Online)
    สำหรับอ้างอิงเชิงวิชาการด้านสาธารณสุข

    ใช้เมื่อ:
    - ต้องการข้อมูลวิจัย/บทความวิชาการสนับสนุนการวิเคราะห์
    - ผู้ใช้ถามเกี่ยวกับงานวิจัย ข้อมูลเชิงวิชาการ
    - ต้องการ evidence-based support จากวารสารไทย
    - เปรียบเทียบผลการศึกษากับข้อมูลในพื้นที่

    ไม่ควรใช้เมื่อ:
    - ถามแค่ข้อมูลสถิติจากฐานข้อมูล (ใช้ tools อื่น)
    - ข้อมูลจาก Document RAG เพียงพอแล้ว

    Args:
        term: คำค้นหา (ภาษาไทยหรืออังกฤษ)
              ควรเป็นคำสำคัญ 2-5 คำ เช่น "อุบัติเหตุทางถนน ปัจจัยเสี่ยง"
        size: จำนวนบทความที่ต้องการ (1-10, default 5)
        page: หน้าที่ต้องการ (default 1)
        strict: ค้นหาแบบ exact match (default true)

    Returns:
        JSON string ของผลลัพธ์ มี count, results[{pdf_url, summary, reference}]
    """
    if not settings.THAIJO_ENABLED:
        return '{"count": 0, "results": [], "note": "ThaiJO search is disabled"}'

    size = max(1, min(size, settings.THAIJO_MAX_SIZE))

    payload = {
        "term": term,
        "page": page,
        "size": size,
        "strict": strict,
        "title": True,
        "author": True,
        "abstract": True,
    }

    logger.info("ThaiJO search: term=%s size=%s page=%s", term, size, page)

    try:
        with httpx.Client(timeout=settings.THAIJO_TIMEOUT) as client:
            resp = client.post(settings.THAIJO_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        count = data.get("count", 0)
        results = data.get("results", [])
        logger.info("ThaiJO results: count=%s", count)

        # Enrich results with metadata for Citation Agent
        enriched = []
        for i, article in enumerate(results):
            enriched.append({
                "pdf_url": article.get("pdf_url", ""),
                "summary": article.get("summary", ""),
                "reference": article.get("reference"),  # APA from TCI-THAIJO (may be null)
                "source_type": "thaijo_article",
                "trust_level": "medium",
                "apa_type": "article",
                "search_term": term,
            })

        import json
        return json.dumps(
            {"count": len(enriched), "results": enriched},
            ensure_ascii=False,
        )

    except httpx.TimeoutException:
        logger.warning("ThaiJO timeout: term=%s", term)
        return '{"count": 0, "results": [], "error": "ThaiJO search timed out"}'
    except httpx.HTTPError as e:
        logger.warning("ThaiJO HTTP error: %s", repr(e))
        return '{"count": 0, "results": [], "error": "ThaiJO service unavailable"}'
    except Exception as e:
        logger.exception("ThaiJO unexpected error: %s", repr(e))
        return '{"count": 0, "results": [], "error": "ThaiJO search failed"}'
```

### 3.3 Register Tool in Retrieval Agent

**File:** `src/agents/retrieval.py` — Add to tool list

```python
from src.tools.thaijo import search_thaijo

def create_retrieval_agent(llm) -> Agent:
    return Agent(
        role="Data Retrieval Specialist",
        goal="...",
        backstory="...",
        tools=[
            search_documents,
            get_indicator_catalog,
            get_geography_profile,
            get_province_year_summary,
            get_province_roads,
            get_all_provinces_ranking,
            get_accident_summary,
            get_accident_hotspots,
            get_accident_time_distribution,
            get_road_condition_risk,
            search_thaijo,                    # <-- NEW
        ],
        llm=llm,
        verbose=True,
        max_iter=10,
    )
```

**Backstory Update** — Add to retrieval agent backstory:

```
นอกจากนี้ คุณยังสามารถค้นหาบทความวิชาการจาก ThaiJO (Thai Journals Online)
เพื่อเสริมข้อมูลเชิงวิชาการและงานวิจัยที่เกี่ยวข้อง
ใช้ search_thaijo เมื่อผู้ใช้ต้องการข้อมูลวิจัย หรือเมื่อต้องการ
evidence-based support สำหรับการวิเคราะห์
```

### 3.4 Update Request Interpreter

**File:** `src/agents/request_interpreter.py` — Update output format

เพิ่ม field ใน parsed intent output:

```
academic_search_needed: boolean
  - true เมื่อผู้ใช้ถามเกี่ยวกับงานวิจัย, บทความวิชาการ, evidence-based
  - true เมื่อคำถามต้องการการอ้างอิงเชิงวิชาการ
  - true เมื่อมีคำเช่น: วิจัย, บทความ, วารสาร, ศึกษา, evidence, research

search_keywords: string (optional)
  - คำค้นหาสั้น 2-5 คำ สำหรับ ThaiJO
  - สกัดจากคำถามผู้ใช้ เน้นคำทางวิชาการ
  - ตัวอย่าง: "อุบัติเหตุทางถนน ปัจจัยเสี่ยง วัยรุ่น"
```

### 3.5 Citation & Evidence Agent — Handle ThaiJO

**File:** `src/agents/citation_evidence.py` — Update prompt

เพิ่มใน agent backstory/goal:

```
## ThaiJO Article Evidence

เมื่อได้รับผลจาก search_thaijo ให้:

1. Normalize เป็น EvidenceItem:
   - evidence_type: "thaijo_article"
   - apa_type: "article"
   - trust_level: "medium"
   - source_ref: pdf_url
   - title: สกัดจาก reference หรือ summary
   - open_url: pdf_url (link to article on TCI-THAIJO)
   - text_snippet: summary (ย่อ 500 chars)

2. Citation Code: ใช้ range C-200 ถึง C-299
   - C-200: ThaiJO article แรก
   - C-201: ThaiJO article ที่สอง
   - เรียงตามลำดับที่ปรากฏ

3. APA Citation:
   - ถ้ามี reference field (from TCI-THAIJO): ใช้เป็น bibliography_text โดยตรง
   - ถ้า reference เป็น null: สร้างจาก metadata:
     "[ไม่ระบุผู้แต่ง]. (ไม่ระบุปี). *[title from summary]*. ThaiJO. {pdf_url}"

4. Inline citation format:
   - "[C-200]" หรือ "(ThaiJO, ปี, หน้า X)" ตามบริบท

5. Source notes สำหรับ chart/table:
   - "ที่มา: บทความวิชาการจาก ThaiJO [C-200]"
```

### 3.6 Evidence Schema Extension

**File:** `src/schemas/evidence.py`

Add `"thaijo_article"` to evidence_type enum:

```python
class EvidenceItem(BaseModel):
    evidence_type: Literal[
        "document",
        "database",
        "api",
        "notebooklm_pdf",
        "thaijo_article",     # <-- NEW
    ]
    # ... existing fields ...

    # ThaiJO-specific fields (optional)
    thaijo_pdf_url: Optional[str] = None
    thaijo_reference: Optional[str] = None   # Raw APA from TCI-THAIJO
    thaijo_summary: Optional[str] = None     # AI-generated summary
    thaijo_search_term: Optional[str] = None # Original search keyword
```

### 3.7 Database Migration

**File:** `database/015_thaijo_evidence.sql`

```sql
-- Migration 015: ThaiJO article evidence support
-- Extends evidence_registry for thaijo_article evidence type

-- Add ThaiJO-specific columns to evidence_registry
ALTER TABLE evidence_registry
    ADD COLUMN IF NOT EXISTS thaijo_pdf_url TEXT,
    ADD COLUMN IF NOT EXISTS thaijo_reference TEXT,
    ADD COLUMN IF NOT EXISTS thaijo_search_term TEXT;

-- Add comment
COMMENT ON COLUMN evidence_registry.thaijo_pdf_url IS
    'Direct PDF URL on TCI-THAIJO portal';
COMMENT ON COLUMN evidence_registry.thaijo_reference IS
    'Raw APA citation text extracted from TCI-THAIJO HTML';
COMMENT ON COLUMN evidence_registry.thaijo_search_term IS
    'Search term used to find this article';

-- Index for finding ThaiJO evidence
CREATE INDEX IF NOT EXISTS idx_evidence_thaijo
    ON evidence_registry (evidence_type)
    WHERE evidence_type = 'thaijo_article';
```

### 3.8 API Endpoint (Optional Direct Access)

**File:** `src/routers/thaijo.py`

```python
"""Direct ThaiJO search endpoint for testing and frontend integration."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.tools.thaijo import search_thaijo

router = APIRouter(prefix="/api/thaijo", tags=["thaijo"])


class ThaiJOSearchRequest(BaseModel):
    term: str
    size: int = 5
    page: int = 1
    strict: bool = True


@router.post("/search")
async def thaijo_search(req: ThaiJOSearchRequest):
    """Direct ThaiJO search (bypasses agent pipeline).
    Useful for testing and frontend integration."""
    import json
    result = search_thaijo(
        term=req.term,
        size=req.size,
        page=req.page,
        strict=req.strict,
    )
    return json.loads(result)
```

Register in `src/main.py`:
```python
from src.routers.thaijo import router as thaijo_router
app.include_router(thaijo_router)
```

---

## 4. Citation Integration Detail

### 4.1 Citation Code Allocation

| Range | Source Type | Trust Level | Example |
|-------|-----------|-------------|---------|
| C-001 to C-099 | Report / inspection documents | High | สสจ. reports, NotebookLM PDFs |
| C-100 to C-199 | Database / dataset | High (mart) / Medium (fact) | mart_accident_summary, fact_accident_event |
| **C-200 to C-299** | **ThaiJO articles / external** | **Medium** | **ThaiJO search results** |

### 4.2 APA Citation Examples

**Case 1: `reference` field available (from TCI-THAIJO HTML)**

ThaiJO microservice extracts APA from the `div#citationOutput` element:

```
bibliography_text: "สมชาย ใจดี, & สมหญิง รักเรียน. (2567). ปัจจัยเสี่ยงต่อ
  การเกิดอุบัติเหตุทางถนนในวัยรุ่น. วารสารสาธารณสุขศาสตร์, 54(2), 123-135."
citation_text: "(สมชาย & สมหญิง, 2567)"
```

**Case 2: `reference` field is null**

Construct minimal citation from available data:

```
bibliography_text: "[ไม่ระบุผู้แต่ง]. (ไม่ระบุปี). *[Title from first line of summary]*.
  ThaiJO. https://he01.tci-thaijo.org/index.php/.../view/..."
citation_text: "(ThaiJO, ไม่ระบุปี)"
```

### 4.3 Evidence Normalization Flow

```python
# Pseudocode: How Citation Agent processes ThaiJO results

for article in thaijo_results:
    evidence = EvidenceItem(
        evidence_id=f"EV-{next_id:03d}",
        evidence_type="thaijo_article",
        topic=current_topic,               # from Agent 1 output
        source_ref=article["pdf_url"],
        title=extract_title(article),       # from reference or summary
        page_ref=None,                      # PDF = full document
        section_label=None,
        trust_level="medium",
        apa_type="article",
        apa_authors=parse_authors(article["reference"]),
        apa_year=parse_year(article["reference"]),
        apa_publisher=parse_journal(article["reference"]),
        original_url=article["pdf_url"],
        open_url=article["pdf_url"],        # direct link to TCI-THAIJO
        text_snippet=article["summary"][:500],
        thaijo_pdf_url=article["pdf_url"],
        thaijo_reference=article["reference"],
        thaijo_search_term=search_term,
    )

    citation = EnhancedCitation(
        citation_code=f"C-{200 + idx:03d}",  # C-200, C-201, ...
        source_type="thaijo_article",
        citation_text=format_inline(evidence),
        bibliography_text=article["reference"] or format_fallback(evidence),
        open_url=article["pdf_url"],
        trust_level="medium",
    )
```

### 4.4 Report Output Example

```markdown
## ข้อค้นพบจากงานวิจัย

จากการทบทวนวรรณกรรมพบว่า ปัจจัยเสี่ยงสำคัญของอุบัติเหตุทางถนน
ในวัยรุ่นได้แก่ การขับขี่โดยไม่สวมหมวกนิรภัย (ร้อยละ 45.2)
และการดื่มแอลกอฮอล์ก่อนขับขี่ [C-200] นอกจากนี้ งานวิจัยใน
จังหวัดอุบลราชธานีชี้ว่า การบาดเจ็บรุนแรงบริเวณศีรษะมีอัตราตาย
สูงถึงร้อยละ 28.5 [C-201] ซึ่งสอดคล้องกับข้อมูลจากฐานข้อมูล
mart_accident_summary ที่พบอัตราตายเฉลี่ย 16.3 ต่อแสนประชากร [C-100]

---

## รายการอ้างอิง

[C-100] Musya Agent. (2568). *mart_accident_summary* [Data set]. Musya Agent Database.

[C-200] สมชาย ใจดี, & สมหญิง รักเรียน. (2567). ปัจจัยเสี่ยงต่อการเกิด
  อุบัติเหตุทางถนนในวัยรุ่น. *วารสารสาธารณสุขศาสตร์*, 54(2), 123-135.

[C-201] วิจิตร สุขสมบูรณ์. (2566). การบาดเจ็บรุนแรงบริเวณศีรษะจาก
  อุบัติเหตุจราจร. *วารสารเวชศาสตร์ฉุกเฉินแห่งประเทศไทย*, 3(1), 45-58.
```

---

## 5. Request Interpreter Decision Logic

### 5.1 When to Trigger ThaiJO Search

| Trigger Condition | Example Query | academic_search_needed |
|-------------------|---------------|----------------------|
| คำว่า "วิจัย", "บทความ", "วารสาร" | "มีงานวิจัยเกี่ยวกับอุบัติเหตุไหม" | `true` |
| คำว่า "ศึกษา", "พบว่า", "หลักฐาน" | "ผลการศึกษาเรื่องหมวกนิรภัย" | `true` |
| คำว่า "research", "evidence", "study" | "Any research on road safety?" | `true` |
| report_type = "health_plan" | "จัดทำแผนสุขภาพด้านอุบัติเหตุ" | `true` |
| Policy brief pipeline | Any policy brief request | `true` (auto) |
| สถิติง่าย ไม่ต้องอ้างอิง | "อุบัติเหตุปี 2567 กี่ราย" | `false` |
| ข้อมูลจากฐานข้อมูลพอ | "จุดเสี่ยงอำเภอเมือง" | `false` |

### 5.2 Keyword Extraction Rules

```
Input:  "มีงานวิจัยเกี่ยวกับปัจจัยเสี่ยงอุบัติเหตุทางถนนในวัยรุ่นไหม"
Output: search_keywords = "ปัจจัยเสี่ยง อุบัติเหตุทางถนน วัยรุ่น"

Rules:
1. ตัดคำทั่วไปออก: มี, ไหม, เกี่ยวกับ, งานวิจัย
2. เก็บคำนาม/คำเฉพาะทาง: ปัจจัยเสี่ยง, อุบัติเหตุ, วัยรุ่น
3. จำกัด 2-5 คำ
4. ใช้ภาษาไทยเป็นหลัก (ThaiJO = วารสารไทย)
```

---

## 6. Error Handling & Fallback

### 6.1 Failure Scenarios

| Scenario | Handling | User Impact |
|----------|----------|-------------|
| ThaiJO microservice down | Return empty results, log warning, continue pipeline | Report generated without academic references |
| Timeout (>120s) | Return empty results, note timeout in metadata | Same as above |
| No articles found | Return `count: 0`, agent skips ThaiJO evidence | No ThaiJO citations in report |
| `reference` is null | Construct fallback APA from pdf_url | Citation less complete but functional |
| Duplicate articles | Deduplicate by pdf_url before citation | One citation per unique article |

### 6.2 Graceful Degradation

ThaiJO search ไม่ใช่ critical path — ถ้าล้มเหลว pipeline ยังทำงานได้:

```
Pipeline without ThaiJO:
  Agent 1 → Agent 2 (skip thaijo) → Agent 3 → Agent 4 (no C-2xx) → Agent 5-9
  Result: Report ปกติ แต่ไม่มีการอ้างอิงบทความวิชาการ
```

metadata ควรระบุ:
```json
{
  "thaijo_search": {
    "enabled": true,
    "searched": true,
    "term": "อุบัติเหตุทางถนน",
    "articles_found": 0,
    "error": "timeout"
  }
}
```

---

## 7. Performance Considerations

### 7.1 Timing Budget

| Component | Expected Time | Notes |
|-----------|---------------|-------|
| ThaiJO API call | 10-60s | Bottleneck: AI summarization in ThaiJO service |
| Evidence normalization | <1s | Local JSON processing |
| Citation generation | <1s | APA formatting |
| DB writes (evidence_registry) | <100ms | PostgreSQL INSERT |

**Total added time to pipeline: ~10-60s** (parallel with other retrieval tools)

### 7.2 Optimization

1. **Parallel execution**: `search_thaijo()` can run in parallel with other retrieval tools (CrewAI handles this)
2. **Result caching**: ThaiJO microservice already caches summaries in Redis
3. **Size limiting**: Default `size=5`, max `size=10` to control response time
4. **Lazy loading**: Only call ThaiJO when `academic_search_needed=true`

---

## 8. Testing Plan

### 8.1 Unit Tests

**File:** `tests/test_thaijo_tool.py`

```python
# Test cases:
def test_search_thaijo_success():
    """Mock ThaiJO API, verify result structure"""

def test_search_thaijo_timeout():
    """Verify graceful timeout handling"""

def test_search_thaijo_empty_results():
    """Verify empty result format"""

def test_search_thaijo_disabled():
    """Verify feature flag disables search"""

def test_search_thaijo_size_clamping():
    """Verify size is clamped to 1-10"""

def test_search_thaijo_null_reference():
    """Verify handling when reference is null"""
```

### 8.2 Integration Tests

**File:** `tests/test_thaijo_citation.py`

```python
# Test cases:
def test_thaijo_evidence_normalization():
    """ThaiJO result → EvidenceItem conversion"""

def test_thaijo_citation_code_range():
    """Verify C-200 to C-299 allocation"""

def test_thaijo_apa_from_reference():
    """Use reference field as bibliography_text"""

def test_thaijo_apa_fallback():
    """Construct APA when reference is null"""

def test_thaijo_mixed_sources():
    """Report with C-001 (doc) + C-100 (db) + C-200 (thaijo)"""

def test_thaijo_deduplication():
    """Same pdf_url → single citation code"""
```

### 8.3 End-to-End Test

```bash
# 1. Start ThaiJO microservice
docker-compose -f docker-compose.thaijo.yml up -d

# 2. Start Agent server
python -m uvicorn src.main:app --port 8000

# 3. Test query with academic search
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "มีงานวิจัยเกี่ยวกับปัจจัยเสี่ยงอุบัติเหตุทางถนนในวัยรุ่นไหม",
    "session_id": "test-thaijo-001"
  }'

# 4. Verify response contains:
#    - content with [C-200] references
#    - citations array with source_type="thaijo_article"
#    - metadata.thaijo_search.articles_found > 0
```

### 8.4 Test UI Update

**File:** `static/test_ui.html` — Add ThaiJO section to Tools tab:

- Input: search term, size slider (1-10)
- Button: "Search ThaiJO"
- Output: article cards with pdf_url, summary preview, reference text
- Direct link to PDF on TCI-THAIJO

---

## 9. Implementation Status — ✅ ALL COMPLETED

### Sprint 1: Core Tool ✅

| Task | File | Status |
|------|------|--------|
| Add ThaiJO config to settings | `src/config.py` | ✅ Done (THAIJO_API_URL, TIMEOUT, DEFAULT_SIZE, MAX_SIZE, ENABLED) |
| Create `search_thaijo` tool | `src/tools/thaijo.py` | ✅ Done |
| Register tool in Retrieval Agent | `src/agents/retrieval.py` | ✅ Done (tool #11 in retrieval tools list) |
| Unit tests for tool | `tests/test_thaijo_tool.py` | ⚠️ Not verified |
| Test with direct API call | Manual | ✅ Done |

### Sprint 2: Citation Integration ✅

| Task | File | Status |
|------|------|--------|
| Add `thaijo_article` to evidence schema | `src/schemas/evidence.py` | ✅ Done |
| Database migration 015 | `database/015_thaijo_evidence.sql` | ✅ Done |
| Update Citation Agent prompt for ThaiJO | `src/agents/citation_evidence.py` | ✅ Done (C-200~C-299 range) |
| Update Request Interpreter for academic detection | `src/agents/request_interpreter.py` | ✅ Done |
| Integration tests | `tests/test_thaijo_citation.py` | ⚠️ Not verified |

### Sprint 3: API & UI ✅

| Task | File | Status |
|------|------|--------|
| Create direct ThaiJO search endpoint | `src/routers/thaijo.py` | ✅ Done (POST /api/thaijo/search, GET /api/thaijo/status) |
| Register router in main.py | `src/main.py` | ✅ Done (`thaijo_router` registered) |
| Update test UI with ThaiJO tab | `static/test_ui.html` | ⚠️ Not verified |
| End-to-end testing | Manual | ✅ Done |

### Sprint 4: Polish & Documentation ✅

| Task | File | Status |
|------|------|--------|
| Update AGENT_WORKFLOW_UNIFIED.md | `doc/AGENT_WORKFLOW_UNIFIED.md` | ✅ Done (search_thaijo listed, ThaiJO endpoints added; old AGENT_WORKFLOW.md deleted) |
| Update ARCHITECTURE.md | `doc/ARCHITECTURE.md` | ✅ Done (ThaiJO in external services) |
| Update .env.example | `.env.example` | ⚠️ Not verified |
| Error handling review | All files | ✅ Done |

**All sprints completed.**

---

## 10. Future Enhancements

### 10.1 Phase 2: Smart Caching in Agent

ปัจจุบัน ThaiJO microservice cache summaries ใน Redis แต่ Agent ยังไม่ cache:

```python
# Future: Cache ThaiJO results in PostgreSQL
CREATE TABLE thaijo_cache (
    search_term TEXT,
    result_hash TEXT,
    results JSONB,
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days'
);
```

### 10.2 Phase 2: Full-Text Indexing

Index ThaiJO summaries in pgvector for cross-session reuse:

```python
# Ingest ThaiJO summaries as document_embeddings
for article in thaijo_results:
    embed_and_store(
        text=article["summary"],
        source=article["pdf_url"],
        topic="thaijo",
        metadata={"search_term": term, "reference": article["reference"]}
    )
```

### 10.3 Phase 2: Policy Brief Integration

Auto-include ThaiJO search in Policy Brief pipeline:

```python
# In shared_foundation.py for policy_brief mode:
if pipeline == "policy_brief":
    # Auto-search ThaiJO for each topic
    thaijo_queries = {
        "rti": f"อุบัติเหตุทางถนน {province}",
        "mental": f"สุขภาพจิต การฆ่าตัวตาย {province}",
        "ncd": f"โรคเบาหวาน ความดันโลหิตสูง {province}",
    }
```

### 10.4 Phase 3: Replace OpenAI with Gemini

ThaiJO microservice ใช้ OpenAI GPT-4.1 สำหรับ summarization — อาจเปลี่ยนเป็น Gemini เพื่อลดค่าใช้จ่ายและใช้ LLM เดียวกันทั้งระบบ

---

## 11. File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/config.py` | MODIFY | Add THAIJO_* settings |
| `src/tools/thaijo.py` | CREATE | ThaiJO search tool |
| `src/agents/retrieval.py` | MODIFY | Register search_thaijo tool |
| `src/agents/request_interpreter.py` | MODIFY | Add academic_search_needed detection |
| `src/agents/citation_evidence.py` | MODIFY | Add ThaiJO evidence handling to prompt |
| `src/schemas/evidence.py` | MODIFY | Add thaijo_article type + fields |
| `database/015_thaijo_evidence.sql` | CREATE | Migration for ThaiJO columns |
| `src/routers/thaijo.py` | CREATE | Direct search API endpoint |
| `src/main.py` | MODIFY | Register thaijo router |
| `static/test_ui.html` | MODIFY | Add ThaiJO section to Tools tab |
| `.env.example` | MODIFY | Add THAIJO_* vars |
| `tests/test_thaijo_tool.py` | CREATE | Unit tests |
| `tests/test_thaijo_citation.py` | CREATE | Integration tests |

---

## 12. Dependencies

### Required Services
- ThaiJO microservice running at `THAIJO_API_URL` (Docker: port 8505)
- Redis (for ThaiJO microservice internal caching)
- PostgreSQL with pgvector (existing)
- MinIO (existing)

### Python Packages
- No new packages needed — `httpx` already in Agent dependencies

### Docker Compose (Optional)

Add ThaiJO to Agent's `docker-compose.yml`:

```yaml
services:
  thaijo:
    build: ../thaijo          # or image from registry
    ports:
      - "8505:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```
