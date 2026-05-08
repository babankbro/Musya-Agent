# P04 — ThaiJO Evidence Sync Agent

**Date**: 2026-04-19  
**Status**: IMPLEMENTED (v3 — added Phase 1.5 API re-fetch)

---

## 1. เป้าหมาย

สร้าง **single agent** ที่ทำ 2 งานใน pass เดียว:

| งาน | รายละเอียด |
|-----|-----------|
| **Cache Enrichment** | เติม null fields (title/apa_*) ใน `thaijo_search_cache` — rule-based ก่อน LLM fallback |
| **Evidence Registration** | เขียน article ทุกชิ้นลง `evidence_registry` พร้อม APA bibliography_text และ summary data |

### สิ่งที่ทำ / ไม่ทำ

| ✅ ทำ | ❌ ไม่ทำ |
|-------|---------|
| อ่าน `thaijo_search_cache` (PostgreSQL) | normalize URL (ทำแล้วตอน write cache) |
| อ่าน `Redis pdf_cache` (full summary) | เขียนทับ evidence_registry ที่มีอยู่แล้ว (idempotent) |
| LLM extract fields ที่ rule-based ล้มเหลว | reset cache TTL |
| เขียน `thaijo_search_cache` (JSONB patch) | |
| เรียก ThaiJO API ใหม่ ถ้าบทความ < 5 (Phase 1.5) | |
| เขียน `evidence_registry` พร้อม APA | |
| สร้าง APA bibliography_text (LLM) | |

---

## 2. Data Sources & Targets

```
SOURCE 1: thaijo_search_cache (PostgreSQL)
├── results_json[i].pdf_url       ← article URL (view format, validated)
├── results_json[i].title         ← อาจ null
├── results_json[i].summary       ← ตัด 300 chars (อาจขาด title header)
├── results_json[i].reference     ← Vancouver/APA text (อาจ null)
├── results_json[i].apa_authors   ← อาจ null
├── results_json[i].apa_year      ← อาจ null
└── results_json[i].apa_journal   ← อาจ null

SOURCE 2: Redis pdf_cache (key: pdf_cache:<sha256(pdf_url)>)
└── FULL GPT-4.1 summary (ไม่ตัด):
    """
    **สรุปบทความวิชาการ: "ชื่อบทความจริง"**
    เนื้อหาสรุป 2-3 ย่อหน้า...
    อ้างอิงจาก: https://he05.tci-thaijo.org/.../view/3802/6365
    """

TARGET 1: thaijo_search_cache (JSONB patch — null fields only)
TARGET 2: evidence_registry (INSERT ... ON CONFLICT DO NOTHING)
```

---

## 3. Architecture — Single Agent, 2-Phase

```
POST /api/thaijo/evidence-sync
        │
        ▼
ThaiJO Evidence Sync Agent  [src/agents/thaijo_evidence_sync.py]
        │
        ├─ PHASE 1: CACHE ENRICHMENT
        │    │
        │    ├─ scan: SELECT cache_key, results_json
        │    │         FROM thaijo_search_cache WHERE expires_at > NOW()
        │    │         AND results_json::text LIKE '%null%'
        │    │
        │    └─ for each null article:
        │         ├─ Step 1: rule-based _extract_article_fields(reference, full_redis_summary)
        │         ├─ Step 2: ถ้ายัง null → LLM extraction (claude-haiku-4-5)
        │         │           Input: full_summary + reference
        │         │           Output: {title, apa_authors, apa_year, apa_journal, bibliography_text}
        │         └─ JSONB patch → UPDATE thaijo_search_cache WHERE field IS NULL
        │
        ├─ PHASE 1.5: API RE-FETCH (ถ้าบทความที่มี title < 5)
        │    │
        │    └─ for each cache row with usable < 5:
        │         ├─ _search_thaijo_impl(search_term, size=10, strict=False)
        │         ├─ merge new unique articles (dedup by pdf_url)
        │         └─ write back merged list → UPDATE thaijo_search_cache
        │
        └─ PHASE 2: EVIDENCE REGISTRATION
             │
             ├─ scan: SELECT cache_key, results_json
             │         FROM thaijo_search_cache WHERE expires_at > NOW()
             │         (all articles — not just null ones)
             │
             └─ for each article:
                  ├─ check evidence_registry: already exists? → skip (ON CONFLICT DO NOTHING)
                  ├─ LLM generate APA bibliography_text (ถ้าไม่มี reference field)
                  │   หรือ rule-based format ถ้ามี reference
                  └─ INSERT evidence_registry {
                         evidence_id = sha256(pdf_url)[:16]
                         evidence_type = 'thaijo_article'
                         title, text_snippet (summary 500 chars), open_url
                         apa_authors, apa_year, apa_journal
                         bibliography_text (APA 7th)
                         thaijo_search_term = search_term จาก cache row
                     }
```

---

## 4. Field Extraction Priority (Phase 1)

```
For each null field in article:

  title:
    P1 Rule: _SUMMARY_TITLE_RE จาก PostgreSQL summary
    P2 Rule: _SUMMARY_TITLE_RE จาก Redis full_summary
    P3 Rule: APA/Vancouver title parse จาก reference
    P4 Rule: _title_from_summary(full_summary) — first sentence
    P5 LLM:  ถ้า P1-P4 ล้มเหลว → LLM extract จาก full_summary
             Prompt: "จากสรุปนี้ ชื่อบทความภาษาไทยคืออะไร ตอบชื่อบทความเท่านั้น"

  apa_authors:
    P1 Rule: Vancouver parse (ก่อน ". " แรก) จาก reference
    P2 Rule: APA parse (_APA_AUTHORS_RE) จาก reference
    P3 LLM:  ถ้า reference null → LLM extract จาก full_summary
             Prompt: "จากสรุปนี้ ชื่อผู้แต่งบทความคืออะไร ตอบชื่อผู้แต่งเท่านั้น (Thai format)"

  apa_year:
    P1 Rule: _REF_YEAR_RE / _APA_YEAR_RE จาก reference
    P2 LLM:  ถ้า reference null → LLM extract จาก full_summary

  apa_journal:
    P1 Rule: Vancouver/APA journal parse จาก reference
    P2 LLM:  ถ้า reference null → LLM extract จาก full_summary
```

### LLM Call Strategy — Batch per article

**ไม่เรียก LLM ทีละ field** — batch ทุก null fields ใน 1 call ต่อ 1 article:

```
Input (1 LLM call per article):
  full_summary: "..." 
  reference: "..." หรือ null
  null_fields: ["title", "apa_authors", "apa_year", "apa_journal"]

Output JSON:
  {
    "title": "ผลของการออกกำลังกายต่อความดันโลหิต",
    "apa_authors": "วิชาญ มีสุข, สมหมาย ใจดี",
    "apa_year": "2565",
    "apa_journal": "วารสารสุขภาพ",
    "bibliography_text": "วิชาญ มีสุข, สมหมาย ใจดี. (2565). ผลของการออกกำลังกาย..."
  }
```

**Model**: `claude-haiku-4-5` (เร็ว ถูก เหมาะกับ extraction task)  
**Temperature**: 0 (deterministic)  
**ไม่เรียก LLM ถ้า**: rule-based ได้ครบทุก field แล้ว

---

## 5. APA Bibliography Format (Phase 2)

### Rule-based (ถ้า reference มีอยู่)

```python
def _format_apa_from_fields(title, apa_authors, apa_year, apa_journal, pdf_url) -> str:
    """สร้าง APA 7th bibliography จาก fields ที่มี."""
    authors = apa_authors or "[ไม่ระบุผู้แต่ง]"
    year    = apa_year    or "ไม่ระบุปี"
    title_  = title       or "[ไม่ระบุชื่อบทความ]"
    journal = apa_journal or "ThaiJO"
    return f"{authors}. ({year}). {title_}. *{journal}*. {pdf_url}"
```

### LLM-generated (ถ้า reference เป็น null และ fields ยัง null)

```
Prompt:
  "สร้าง APA 7th Edition bibliography สำหรับบทความต่อไปนี้:
   - จากสรุป: {full_summary[:500]}
   - URL: {pdf_url}
   ตอบเฉพาะ bibliography text เท่านั้น ภาษาไทย"
```

---

## 6. evidence_registry Schema (ThaiJO fields)

```sql
INSERT INTO evidence_registry (
    evidence_id,          -- sha256(pdf_url)[:16]
    evidence_type,        -- 'thaijo_article'
    topic,                -- normalized_term จาก cache row
    source_ref,           -- pdf_url (view URL)
    title,                -- enriched title
    text_snippet,         -- full_summary[:500] (จาก Redis)
                          -- ถ้า Redis miss → summary จาก cache[:500]
    trust_level,          -- 'medium'
    original_url,         -- pdf_url
    open_url,             -- pdf_url (same — already validated view URL)
    apa_type,             -- 'article'
    apa_authors,          -- enriched
    apa_year,             -- enriched
    apa_publisher,        -- apa_journal (ThaiJO journal name)
    thaijo_search_term,   -- search_term จาก cache row
    thaijo_pdf_url,       -- pdf_url (backup column — used by sync-evidence)
    bibliography_text     -- APA 7th full reference (rule-based or LLM)
) VALUES (...)
ON CONFLICT (evidence_id) DO NOTHING;  -- idempotent
```

> **Note**: `bibliography_text` อาจยังไม่มี column ใน schema — ถ้าไม่มีให้ใส่ใน `text_snippet` ต่อท้ายด้วย `\n\nอ้างอิง: {bibliography_text}`

---

## 7. Tasks

### T1 — Core agent: `src/agents/thaijo_evidence_sync.py`

**Public API:**

```python
@dataclass
class SyncResult:
    # Phase 1 stats
    cache_rows_scanned: int
    articles_scanned: int
    fields_filled_rule: int      # จาก rule-based
    fields_filled_llm: int       # จาก LLM fallback
    llm_calls: int
    cache_patched: int           # articles ที่ถูก patch
    # Phase 1.5 stats
    api_refetched_rows: int      # cache rows ที่ re-fetch
    api_new_articles: int        # บทความใหม่จาก API
    # Phase 2 stats
    evidence_inserted: int       # new rows
    evidence_skipped: int        # already existed
    evidence_errors: int
    errors: int
    details: list[dict]

def run_evidence_sync(llm_model: str = "claude-haiku-4-5-20251001") -> SyncResult:
    """Phase 1: enrich cache fields. Phase 2: register in evidence_registry."""
```

**Internal helpers:**

```python
def _get_redis() -> Redis | None
def _lookup_redis_summary(pdf_url: str, redis) -> str | None
def _needs_enrichment(article: dict) -> bool
def _llm_extract_fields(full_summary: str, reference: str | None, null_fields: list[str], llm) -> dict
def _patch_article_in_jsonb(cache_key: str, idx: int, fields: dict) -> None
def _format_apa_from_fields(title, apa_authors, apa_year, apa_journal, pdf_url) -> str
def _register_evidence(article: dict, search_term: str, full_summary: str | None) -> bool
```

---

### T2 — FastAPI endpoint: `src/routers/thaijo.py`

```python
class EvidenceSyncResult(BaseModel):
    cache_rows_scanned: int
    articles_scanned: int
    fields_filled_rule: int
    fields_filled_llm: int
    llm_calls: int
    cache_patched: int
    evidence_inserted: int
    evidence_skipped: int
    evidence_errors: int
    errors: int
    details: list[dict] = []

@router.post("/evidence-sync", response_model=EvidenceSyncResult)
async def evidence_sync(model: str = "claude-haiku-4-5-20251001") -> EvidenceSyncResult:
    """Sync ThaiJO cache → enrich null fields (rule + LLM) → register in evidence_registry.
    
    Idempotent: existing evidence_registry entries are not overwritten.
    Only articles in non-expired thaijo_search_cache are processed.
    """
    from src.agents.thaijo_evidence_sync import run_evidence_sync
    result = run_evidence_sync(llm_model=model)
    return EvidenceSyncResult(**asdict(result))
```

---

### T3 — UI Section E: `static/thaijo_research_ui.html`

เพิ่มใน `panel-agent-test` หลัง Section D:

```
Section E — ThaiJO Evidence Sync
  [model selector: haiku / sonnet]
  [🔄 Sync Evidence] button
  
  Result chips:
    Phase 1: cache_patched | fields rule | fields LLM | LLM calls
    Phase 2: evidence_inserted | evidence_skipped | errors
  
  Detail table:
    pdf_url (truncated, clickable) | title | fields_filled | evidence action
```

---

## 8. LLM Prompt — Field Extraction

```python
FIELD_EXTRACTION_PROMPT = """คุณเป็นผู้เชี่ยวชาญด้านข้อมูลบรรณานุกรมบทความวิชาการไทย

จากข้อมูลต่อไปนี้ กรุณาดึงข้อมูลบรรณานุกรม:

## สรุปบทความ:
{full_summary}

## Reference text (ถ้ามี):
{reference}

## Fields ที่ต้องการ:
{null_fields}

ตอบเป็น JSON เท่านั้น (ห้ามมีข้อความอื่น):
{{
    "title": "ชื่อบทความภาษาไทยเต็ม (null ถ้าไม่พบ)",
    "apa_authors": "ชื่อผู้แต่ง APA format (null ถ้าไม่พบ)",
    "apa_year": "ปี พ.ศ. 4 หลัก เช่น 2565 (null ถ้าไม่พบ)",
    "apa_journal": "ชื่อวารสาร (null ถ้าไม่พบ)",
    "bibliography_text": "APA 7th Edition full reference (null ถ้าข้อมูลไม่เพียงพอ)"
}}

กฎ:
- ถ้าไม่พบข้อมูลจริงๆ ให้ใส่ null ไม่ใช่เดาหรือแต่งเพิ่ม
- ปีให้เป็น พ.ศ. (ถ้าเป็น ค.ศ. ให้บวก 543)
- bibliography_text รูปแบบ: "ผู้แต่ง. (ปี). ชื่อบทความ. *ชื่อวารสาร*. URL"
"""
```

---

## 9. LLM Integration — ใช้ Anthropic SDK โดยตรง

```python
from anthropic import Anthropic

def _llm_extract_fields(full_summary: str, reference: str | None, 
                         null_fields: list[str], model: str) -> dict:
    """Call LLM to extract missing bibliography fields. Returns dict with extracted values."""
    client = Anthropic()
    prompt = FIELD_EXTRACTION_PROMPT.format(
        full_summary=full_summary[:1500],
        reference=reference or "(ไม่มี reference text)",
        null_fields=", ".join(null_fields),
    )
    msg = client.messages.create(
        model=model,
        max_tokens=400,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    import json as _json
    text = msg.content[0].text.strip()
    # Extract JSON from response
    start = text.find("{")
    end = text.rfind("}") + 1
    return _json.loads(text[start:end]) if start >= 0 else {}
```

---

## 10. ลำดับ Implementation

```
T1 (core agent)    → T2 (endpoint)    → T3 (UI Section E)

T1 sub-steps:
  T1a: _get_redis + _lookup_redis_summary + _needs_enrichment
  T1b: Phase 1 — rule-based enrichment + JSONB patch
  T1c: _llm_extract_fields + LLM fallback integration
  T1d: Phase 2 — _register_evidence + _format_apa_from_fields
```

---

## 11. Files

| File | Task | Change |
|------|------|--------|
| `src/agents/thaijo_evidence_sync.py` | T1 | **NEW** — core sync agent |
| `src/routers/thaijo.py` | T2 | `POST /api/thaijo/evidence-sync` |
| `static/thaijo_research_ui.html` | T3 | Section E — Evidence Sync panel |

---

## 12. Expected Outcome

```
BEFORE:
  thaijo_search_cache:
    {pdf_url: ".../view/3802/6365", title: null, apa_year: null, ...}
  evidence_registry:
    (ไม่มี row นี้)

AFTER run_evidence_sync():
  thaijo_search_cache:
    {pdf_url: ".../view/3802/6365", 
     title: "ผลของการออกกำลังกายต่อความดันโลหิต",
     apa_year: "2565", apa_authors: "วิชาญ มีสุข",
     apa_journal: "วารสารสุขภาพ"}   ← filled

  evidence_registry:
    evidence_id:     "3f9a2b..."
    evidence_type:   "thaijo_article"
    title:           "ผลของการออกกำลังกายต่อความดันโลหิต"
    text_snippet:    "**สรุปบทความวิชาการ: ..."  (full Redis summary 500 chars)
    open_url:        "https://he05.tci-thaijo.org/.../view/3802/6365"
    apa_authors:     "วิชาญ มีสุข"
    apa_year:        "2565"
    apa_publisher:   "วารสารสุขภาพ"
    bibliography_text: "วิชาญ มีสุข. (2565). ผลของการออกกำลังกาย...
                        *วารสารสุขภาพ*. https://he05.tci-thaijo.org/..."
    thaijo_search_term: "ออกกำลังกาย ความดันโลหิต"
```

---

## 13. ความสัมพันธ์กับ Tab สร้างรายงานวิจัย

```
เดิม (Tab 2 Pipeline):
  Agent 4 Citation → lookup_thaijo_evidence() → register_evidence()
  ปัญหา: URL mismatch, field null, bibliography hallucinate

หลัง P04:
  evidence-sync เติม evidence_registry ล่วงหน้า (pre-populate)
  Agent 4 Citation → lookup_thaijo_evidence():
    ├─ Step 1: cache hit (exact)     ← พบ เพราะ enriched แล้ว
    ├─ Step 2: prefix fallback       ← (F2 fix) handle URL mismatch
    └─ found=True + all fields set   ← ไม่ต้อง hallucinate!

  register_evidence(): ON CONFLICT DO NOTHING
    └─ row มีอยู่แล้ว (จาก evidence-sync) ← skip, ไม่ overwrite
```
