# D01 — Citation Evidence Agent: ThaiJO Data Quality Investigation & Fix Plan

> **เวอร์ชัน**: 1.0
> **วันที่**: 2026-04-19
> **ประเภท**: Bug investigation + fix plan
> **Skill used**: debugging-and-error-recovery + planning-and-task-breakdown
> **อ้างอิง**: p01_plan_shared_agent_verify.md (parent plan)

---

## Evidence of the Bug

**Observed Citation Agent output (ThaiJO evidence items):**

```json
{
  "evidence_id": "EV-200",
  "evidence_type": "thaijo_article",
  "apa_type": "article",
  "trust_level": "medium",
  "source_ref": "https://he01.tci-thaijo.org/...",
  "title": "สรุปบทความที่ 1 เกี่ยวกับอุบัติเหตุทางถนนในจังหวัดยโสธร โดยเน้นที่ปัจจัยเสี่ยงด้านพฤติกรรมของผู้ขับขี่",
  "open_url": "https://he01.tci-thaijo.org/...",
  "text_snippet": "สรุปบทความที่ 1 เกี่ยวกับอุบัติเหตุทางถนนในจังหวัดยโสธร โดยเน้นที่ปัจจัยเสี่ยงด้านพฤติกรรมของผู้ขับขี่",
  "apa_authors": null,
  "apa_year": null,
  "apa_publisher": null,
  "page_ref": null,
  "section_label": null,
  "original_url": null
}
```

**สิ่งที่ผิดปกติ:**

| Field | สิ่งที่ควรเป็น | สิ่งที่ได้รับจริง | ปัญหา |
|-------|--------------|-----------------|-------|
| `title` | ชื่อบทความจริง เช่น "ปัจจัยที่มีความสัมพันธ์กับการเกิดอุบัติเหตุ..." | "สรุปบทความที่ 1 เกี่ยวกับ{topic}" | LLM-generated placeholder |
| `text_snippet` | ข้อความจาก `summary[:500]` | เหมือน title ทุกอักขระ | LLM reuses fake title |
| `apa_authors` | ชื่อผู้แต่ง เช่น "สมชาย ใจดี และคณะ" | null | ไม่มีข้อมูลให้ LLM parse |
| `apa_year` | "2566" หรือ "2023" | null | ไม่มีข้อมูลให้ LLM parse |
| `apa_publisher` | ชื่อวารสาร | null | ไม่มีข้อมูลให้ LLM parse |
| `original_url` | ควรมีค่า | null | ไม่มี instruction ให้ set |

**Pattern ที่บ่งชี้ว่าเป็น hallucination:**
- "สรุปบทความที่ **N** เกี่ยวกับ..." — เลข N เรียงลำดับ บ่งชี้ว่า LLM นับเอง
- เนื้อหาใน title อ้างอิง search topic ของผู้ใช้ ไม่ใช่ชื่อบทความจริง
- `text_snippet` == `title` ทุกตัวอักษร — LLM ไม่ได้ใช้ `summary` จริง

---

## Data Flow Trace — จากต้นทางถึง Citation Agent

```
ThaiJO microservice (:8505)
  scrapes TCI-THAIJO → GPT-4.1 summary
  API response (per article):
    {
      "pdf_url": "https://he01.tci-thaijo.org/.../view/12345",
      "title":   "ปัจจัยเสี่ยงอุบัติเหตุ..."   ← อาจมีหรือไม่มี (ขึ้นกับ microservice)
      "summary": "<3 A4 pages of Thai prose>",
      "reference": "ผู้แต่ง. (2565). ชื่อบทความ..." หรือ null
    }
              ↓
_search_thaijo_impl() [thaijo.py:199-212] — TOOL LEVEL (0 LLM hops)
  enriched.append({
      "pdf_url":   url,
      "summary":   article.get("summary", ""),
      "reference": article.get("reference"),   ← raw APA string or null
      "source_type": "thaijo_article",
      "trust_level": "medium",
      "apa_type":  "article",
      "search_term": term,
      # ❌ article.get("title") — NEVER CALLED
      # ❌ apa_authors/year — NOT EXTRACTED
  })
              ↓ [LLM HOP 1: Searcher LLM serializes tool results to JSON text]
Searcher output schema (THAIJO_SEARCHER_PROMPT):
  {
    "pdf_url":      "...",
    "summary":      "สรุปบทความ...",   ← full 3-page text
    "reference":    "APA text หรือ null",
    "source_queries": [...],
    "source_type":  "thaijo_article",
    "trust_level":  "medium"
    # ❌ no "title" field in schema
  }
              ↓ [LLM HOP 2: Screener LLM copies/filters]
Screener output schema (THAIJO_SCREENER_PROMPT):
  {
    "pdf_url":        "...",
    "summary":        "...",  ← may be truncated
    "reference":      "..." or null,
    "relevance_score": 8.5,
    "themes":         ["พฤติกรรมเสี่ยง"],
    "included":       true
    # ❌ no "title" field in schema
  }
              ↓ [LLM HOP 3: Citation Agent reads context as plain text]
Citation Agent must construct from context:
  {
    "title":       ← MUST PARSE from reference or summary first line
    "text_snippet" ← MUST EXTRACT from summary
    "apa_authors"  ← MUST PARSE from reference
    "apa_year"     ← MUST PARSE from reference
    "apa_publisher"← MUST PARSE from reference
  }

  ⚠️ When reference=null and summary is 3-page prose:
     LLM generates "สรุปบทความที่ N เกี่ยวกับ{topic}" ← HALLUCINATION
```

---

## Root Cause Analysis

### RC-CE-1 (CRITICAL): `_search_thaijo_impl()` ไม่อ่าน `title` จาก API response

**ไฟล์:** `src/tools/thaijo.py:199-212`

```python
enriched.append({
    "pdf_url": url,
    "summary": article.get("summary", ""),
    "reference": article.get("reference"),
    "source_type": "thaijo_article",
    "trust_level": "medium",
    "apa_type": "article",
    "search_term": term,
    # ❌ "title": article.get("title", "")  ← ไม่มีบรรทัดนี้
    # ❌ "apa_authors": ...                  ← ไม่มี
    # ❌ "apa_year": ...                     ← ไม่มี
})
```

**API payload ส่ง `"title": True`** (line 123) — ซึ่งบอก microservice ให้ค้นหาใน title field
ThaiJO microservice อาจ return `title` field ใน article objects ด้วย แต่ code ไม่เคย read

**Impact:**
- ตั้งแต่ HOP 1 ไม่มี `title` field ในข้อมูล
- LLM Citation Agent ที่ HOP 3 ไม่มี pre-extracted title → fallback → hallucinate

---

### RC-CE-2 (CRITICAL): ไม่มีการ pre-extract `apa_authors`, `apa_year` จาก `reference` ก่อน LLM เห็น

**`reference` field เป็น APA string เช่น:**
```
สมชาย ใจดี, วิไลวรรณ ทองดี, และ มานพ ศรีสุข. (2565).
ปัจจัยเสี่ยงต่อการเกิดอุบัติเหตุทางถนนในกลุ่มเยาวชน.
วารสารสาธารณสุขศาสตร์, 52(3), 301-315.
```

**Citation Agent prompt กำหนดให้ LLM parse ตรงนี้เอง:**
```
`apa_authors`, `apa_year`, `apa_publisher`: สกัดจาก `reference` ถ้ามี
```

**ปัญหา 2 กรณี:**
1. `reference = null` (หลาย journals ไม่ expose APA citation) → ทุก apa_* = null → **LLM ทำถูกแต่ข้อมูลว่าง**
2. `reference != null` → LLM ต้อง parse APA string → **unpredictable ที่ HOP 3**

---

### RC-CE-3 (HIGH): Citation Agent prompt สั่งให้ extract title ด้วย instruction ที่ผิด

**ไฟล์:** `src/agents/citation_evidence.py:58`

```
`title`: สกัดจาก `reference` (ชื่อบทความก่อนจุด) หรือจาก `summary` บรรทัดแรก
```

**ปัญหา:**
- "ก่อนจุด" (before the period) — ใน APA format, ชื่อบทความอยู่หลัง `(ปี). ` ไม่ใช่ "ก่อนจุด"
- Thai APA: `"ผู้แต่ง. (2565). **ชื่อบทความ**. วารสาร, ปีที่(ฉบับ), หน้า."`
- เลข N ที่ "ก่อนจุด" แรกคือ ชื่อผู้แต่ง ไม่ใช่ title
- LLM บางครั้งทำถูก บางครั้ง parse ผิด segment

---

### RC-CE-4 (HIGH): `summary` เป็น 3-page AI prose ไม่เหมาะเป็น `title` source

**`summary` field จาก ThaiJO microservice:**
```
บทความนี้ศึกษาปัจจัยที่มีความสัมพันธ์กับการเกิดอุบัติเหตุทางถนนในกลุ่มผู้ขับขี่มอเตอร์ไซค์
ในจังหวัดยโสธร โดยใช้แบบสอบถามเก็บข้อมูลจากกลุ่มตัวอย่าง 385 คน ระหว่างปี พ.ศ. 2564-2565...
[ต่ออีก 3 A4 pages]
```

**Prompt fallback:** `"จาก summary บรรทัดแรก"` → ได้ "บทความนี้ศึกษา..." → ไม่ใช่ title
LLM รู้ว่า "บทความนี้ศึกษา..." ไม่ใช่ title จึง fallback ไปสร้างเอง:
→ **"สรุปบทความที่ N เกี่ยวกับ{topic}"**

---

### RC-CE-5 (MEDIUM): `text_snippet` = `title` เพราะ LLM ไม่มี clear mapping

**Prompt:**
```
`text_snippet`: ใช้ `summary` (ย่อไว้ที่ 500 อักขระ)
```

แต่เมื่อ LLM ไม่สามารถดึง `summary` ที่ถูกต้องออกมาจาก context (long text, possibly truncated):
- LLM reuses title as text_snippet
- ไม่มี explicit enforcement ว่าต้องใช้ raw `summary[:500]`

---

## Dependency Graph

```
RC-CE-1 (ไม่ read title จาก API)
    │
    └──► RC-CE-3 (prompt บอก extract จาก reference — wrong)
    │           └──► RC-CE-4 (summary fallback ก็ไม่ใช่ title)
    │                       └──► HALLUCINATION "สรุปบทความที่ N"
    │
RC-CE-2 (ไม่ pre-extract apa_*) ──► apa_authors/year/publisher = null
    │
    └──► RC-CE-5 (text_snippet = title ซ้ำ)
```

**แก้ RC-CE-1 → ลด RC-CE-3, RC-CE-4, RC-CE-5 ทั้งหมด** (single fix ที่ tool level)

---

## Fix Architecture

```
ThaiJO microservice (:8505)
  returns: {pdf_url, title?, summary, reference, ...}
              ↓
_search_thaijo_impl() [TOOL LEVEL — แก้ที่นี่]
  ① article.get("title", "")           ← อ่าน title จาก API (RC-CE-1)
  ② _extract_apa_fields(reference)     ← parse apa_* ก่อน LLM เห็น (RC-CE-2)
     → title_from_ref, apa_authors, apa_year, apa_journal
  ③ title = title_api or title_from_ref or _title_from_summary(summary)
  ④ text_snippet = summary[:500]       ← map ตรง ไม่ผ่าน LLM (RC-CE-5)

  enriched.append({
      "pdf_url":       url,
      "title":         title,          ← NEW: pre-extracted, สะอาด
      "summary":       summary,
      "reference":     reference,
      "source_type":   "thaijo_article",
      "trust_level":   "medium",
      "apa_type":      "article",
      "apa_authors":   apa_authors,    ← NEW: pre-extracted
      "apa_year":      apa_year,       ← NEW: pre-extracted
      "apa_journal":   apa_journal,    ← NEW: journal name as publisher
      "search_term":   term,
  })
              ↓ [LLM HOP 1: Searcher — schema updated to include title]
Searcher output: {pdf_url, title, summary, reference, apa_authors, apa_year, ...}
              ↓ [LLM HOP 2: Screener — schema updated]
Screener output: {pdf_url, title, summary, reference, relevance_score, themes}
              ↓ [LLM HOP 3: Citation Agent — prompt updated]
Citation Agent:
  → ใช้ title โดยตรง (ไม่ต้อง parse)
  → ใช้ apa_authors, apa_year โดยตรง (ไม่ต้อง parse)
  → ใช้ summary[:500] เป็น text_snippet โดยตรง
```

---

## Fix Plan

### Task D1 (S): Pre-extract `title` และ `apa_*` ใน `_search_thaijo_impl()`

**Root causes:** RC-CE-1, RC-CE-2

**ไฟล์:** `src/tools/thaijo.py`

**เพิ่ม helper function:**

```python
_APA_YEAR_RE = re.compile(r'\((\d{4})\)')
_APA_TITLE_RE = re.compile(
    r'\(\d{4}\)\s*\.?\s+'          # after "(year)."
    r'(.+?)'                        # capture title (non-greedy)
    r'\.'                           # ends at next period
    r'\s+\S',                       # followed by non-space (journal start)
    re.DOTALL,
)


def _extract_apa_fields(reference: str | None) -> dict:
    """Parse a ThaiJO APA citation string into structured fields.

    Thai APA format:
        "ผู้แต่ง. (ปี). ชื่อบทความ. วารสาร, ปีที่(ฉบับ), หน้า."
    English APA format:
        "Author, A. B. (year). Article title. Journal, vol(issue), pages."

    Returns dict with keys: title, apa_authors, apa_year, apa_journal
    All values may be None if parsing fails or reference is None.
    """
    if not reference:
        return {"title": None, "apa_authors": None, "apa_year": None, "apa_journal": None}

    year_m = _APA_YEAR_RE.search(reference)
    apa_year = year_m.group(1) if year_m else None

    # Authors: everything before "(year)"
    apa_authors: str | None = None
    if year_m and year_m.start() > 0:
        raw_authors = reference[: year_m.start()].strip().rstrip(".")
        if raw_authors:
            apa_authors = raw_authors

    # Title: text between "(year). " and the next ". " segment
    title: str | None = None
    if year_m:
        after_year = reference[year_m.end():].lstrip(". \n")
        dot_pos = after_year.find(". ", 5)  # title must be at least 5 chars
        if dot_pos > 0:
            candidate = after_year[:dot_pos].strip()
            # Reject if looks like a journal name (very short, or all caps abbreviation)
            if len(candidate) >= 5:
                title = candidate

    # Journal / publisher: segment after title
    apa_journal: str | None = None
    if title and year_m:
        rest = reference[year_m.end():].lstrip(". \n")
        title_end = rest.find(title)
        if title_end >= 0:
            after_title = rest[title_end + len(title):].lstrip(". \n,")
            # Journal is up to next comma or end
            journal_end = after_title.find(",")
            apa_journal = after_title[:journal_end].strip() if journal_end > 0 else after_title.strip()
            if not apa_journal:
                apa_journal = None

    return {
        "title": title,
        "apa_authors": apa_authors,
        "apa_year": apa_year,
        "apa_journal": apa_journal,
    }


def _title_from_summary(summary: str) -> str | None:
    """Extract a usable title hint from the summary text.

    ThaiJO summaries start with academic prose, not a title.
    Strategy: look for a quoted title pattern, or return None.
    The LLM will use open_url as fallback label if title is None.
    """
    if not summary:
        return None
    # If summary contains a Thai quote-style title (between «» or " ") use it
    import re as _re
    m = _re.search(r'["\u201c\u201d\u00ab\u00bb](.{10,120})["\u201c\u201d\u00ab\u00bb]', summary)
    if m:
        return m.group(1).strip()
    # Otherwise return None — don't fabricate a title from prose
    return None
```

**แก้ enrichment loop:**

```python
for article in results:
    url = article.get("pdf_url", "")
    if not _is_valid_thaijo_url(url):
        logger.warning("ThaiJO: invalid pdf_url filtered out: %r", url[:80])
        continue

    reference = article.get("reference")
    raw_summary = article.get("summary", "")

    # Pre-extract structured fields before any LLM sees this data
    apa = _extract_apa_fields(reference)
    api_title = article.get("title", "")  # microservice may return title directly

    title = api_title or apa["title"] or _title_from_summary(raw_summary)

    enriched.append({
        "pdf_url":     url,
        "title":       title,                      # pre-extracted — no LLM needed
        "summary":     raw_summary,
        "reference":   reference,
        "source_type": "thaijo_article",
        "trust_level": "medium",
        "apa_type":    "article",
        "apa_authors": apa["apa_authors"],          # pre-extracted
        "apa_year":    apa["apa_year"],             # pre-extracted
        "apa_journal": apa["apa_journal"],          # pre-extracted (journal as publisher)
        "search_term": term,
    })
```

**Acceptance criteria:**
- [ ] `title` field present in enriched dict for every article
- [ ] `apa_authors`, `apa_year` populated from `reference` when reference is not null
- [ ] `api_title` (from microservice) takes priority over parsed title
- [ ] `title` is None (not a fake string) when extraction fails
- [ ] Cache stores new fields — cache entries after deploy have `title`, `apa_authors`, `apa_year`
- [ ] Existing tests still pass

**Verification:**
```bash
# Call Tab 1 search and verify response includes title
curl -s -X POST http://localhost:8000/api/thaijo/search \
  -H "Content-Type: application/json" \
  -d '{"term": "อุบัติเหตุทางถนน", "size": 3}' | python -m json.tool | grep -A2 '"title"'

# Verify helper function directly
python -c "
from src.tools.thaijo import _extract_apa_fields
ref = 'สมชาย ใจดี. (2565). ปัจจัยเสี่ยงต่อการเกิดอุบัติเหตุ. วารสารสาธารณสุข, 52(3), 301.'
print(_extract_apa_fields(ref))
"
```

**Scope:** S
**Fixes:** RC-CE-1, RC-CE-2

---

### Task D2 (XS): อัปเดต Searcher output schema ให้รวม `title` และ `apa_*`

**Root causes:** RC-CE-1 (downstream)

**ไฟล์:** `src/agents/thaijo_searcher.py`

**แก้ JSON schema ใน `THAIJO_SEARCHER_PROMPT`:**

```python
# เปลี่ยนจาก:
{
    "pdf_url": "https://he01.tci-thaijo.org/...",
    "summary": "สรุปบทความ...",
    "reference": "APA citation text หรือ null",
    "source_queries": ["คำค้นที่ 1"],
    "source_type": "thaijo_article",
    "trust_level": "medium"
}

# เป็น:
{
    "pdf_url": "https://he01.tci-thaijo.org/...",
    "title": "ชื่อบทความจริง (จาก tool) หรือ null",  ← ใหม่
    "summary": "สรุปบทความ...",
    "reference": "APA citation text หรือ null",
    "apa_authors": "ผู้แต่ง (จาก tool) หรือ null",   ← ใหม่
    "apa_year": "2565 (จาก tool) หรือ null",          ← ใหม่
    "apa_journal": "ชื่อวารสาร (จาก tool) หรือ null", ← ใหม่
    "source_queries": ["คำค้นที่ 1"],
    "source_type": "thaijo_article",
    "trust_level": "medium"
}
```

เพิ่มหมายเหตุ:
```
⚠️ สำคัญ: ห้ามเปลี่ยนค่า title, apa_authors, apa_year — ค่าเหล่านี้ pre-extracted จาก tool แล้ว
ให้ copy ค่าจาก search_thaijo tool output ตรงๆ เท่านั้น ห้ามแต่งหรือแก้ไข
```

**Acceptance criteria:**
- [ ] Searcher output JSON schema รวม `title`, `apa_authors`, `apa_year`, `apa_journal` fields
- [ ] มีหมายเหตุห้าม LLM แก้ค่าเหล่านี้

**Scope:** XS
**Fixes:** RC-CE-1 (prevents LLM from dropping title during HOP 1)

---

### Task D3 (XS): อัปเดต Screener output schema ให้ pass-through `title` และ `apa_*`

**Root causes:** RC-CE-1 (downstream)

**ไฟล์:** `src/agents/thaijo_screener.py`

**แก้ JSON schema ใน `THAIJO_SCREENER_PROMPT`:**

```python
# เปลี่ยน screened_articles item จาก:
{
    "pdf_url": "...",
    "summary": "...",
    "reference": "..." หรือ null,
    "relevance_score": 8.5,
    ...
}

# เป็น:
{
    "pdf_url": "...",
    "title": "...",       ← ใหม่: copy จาก Searcher, ห้ามแก้
    "summary": "...",
    "reference": "...",
    "apa_authors": "...", ← ใหม่: copy จาก Searcher, ห้ามแก้
    "apa_year": "...",    ← ใหม่: copy จาก Searcher, ห้ามแก้
    "apa_journal": "...", ← ใหม่: copy จาก Searcher, ห้ามแก้
    "relevance_score": 8.5,
    ...
}
```

เพิ่มหมายเหตุ:
```
⚠️ ห้ามแก้ค่า pdf_url, title, apa_authors, apa_year — copy ตรงจาก Searcher output
```

**Acceptance criteria:**
- [ ] Screener JSON schema รวม `title`, `apa_*` fields
- [ ] มีหมายเหตุห้าม LLM แก้ค่า metadata

**Scope:** XS
**Fixes:** RC-CE-1 (prevents title loss at HOP 2)

---

### Task D4 (XS): อัปเดต Citation Agent prompt — ใช้ pre-extracted fields โดยตรง

**Root causes:** RC-CE-3, RC-CE-4, RC-CE-5

**ไฟล์:** `src/agents/citation_evidence.py`

**แก้ prompt (lines 53-61) จาก:**
```
- `title`: สกัดจาก `reference` (ชื่อบทความก่อนจุด) หรือจาก `summary` บรรทัดแรก
- `open_url`: ใช้ `pdf_url` โดยตรง
- `text_snippet`: ใช้ `summary` (ย่อไว้ที่ 500 อักขระ)
- `apa_authors`, `apa_year`, `apa_publisher`: สกัดจาก `reference` ถ้ามี
```

**เป็น:**
```
- `title`: ใช้ `title` field โดยตรงจาก ThaiJO tool output
  - ถ้า `title` เป็น null: ใช้ `"[ชื่อบทความไม่ปรากฏ]"` — ห้ามสร้างชื่อเอง
  - ห้ามสร้างชื่อ เช่น "สรุปบทความที่ N..." — นั่นคือ hallucination
- `open_url`: ใช้ `pdf_url` โดยตรง
- `text_snippet`: ใช้ `summary` 500 อักขระแรกโดยตรง — ห้ามสร้างเนื้อหาใหม่
- `apa_authors`: ใช้ `apa_authors` field โดยตรง (อาจเป็น null — ให้ใส่ null)
- `apa_year`: ใช้ `apa_year` field โดยตรง (อาจเป็น null — ให้ใส่ null)
- `apa_publisher`: ใช้ `apa_journal` field เป็น publisher (อาจเป็น null)
- `original_url`: ใช้ `pdf_url` (เหมือน open_url สำหรับ thaijo_article)
```

**Acceptance criteria:**
- [ ] Prompt ไม่มีคำว่า "สกัดจาก reference" หรือ "ชื่อบทความก่อนจุด"
- [ ] Prompt ระบุชัดเจนว่าห้าม generate title — ให้ใช้ `title` field หรือ null
- [ ] Prompt ระบุชัดเจนว่า `text_snippet` = `summary` 500 chars แรก โดยตรง

**Scope:** XS
**Fixes:** RC-CE-3, RC-CE-4, RC-CE-5

---

### Task D5 (XS): Invalidate cache — เพื่อให้ cached entries ได้รับ title field ใหม่

**Root causes:** RC-CE-1 (cached data ไม่มี title)

**Background:**
`thaijo_search_cache` เก็บ `results_json` ที่ไม่มี `title`, `apa_authors`, `apa_year`
หลัง deploy Task D1 — cache entries เก่าจะยังส่ง data ไม่มี title ไปให้ LLM

**ตัวเลือก:**
1. Clear cache ทั้งหมด: `DELETE FROM thaijo_search_cache;` — search term ใดก็ตามจะ re-fetch
2. Bump cache key format: เพิ่ม version prefix ใน key → เก่าทั้งหมดจะ miss → re-fetch อัตโนมัติ

**แนะนำ Option 2** (ไม่ทำลายข้อมูล):

```python
# src/tools/thaijo.py — เปลี่ยน cache key format
def _cache_key(normalized: str, size: int) -> str:
    """SHA-256 of 'v2:normalized_term|size=N' — v2 includes title/apa_* fields."""
    return sha256(f"v2:{normalized}|size={size}".encode()).hexdigest()
```

Cache entries ที่ key ขึ้นต้นด้วย sha256 ของ format เก่า (`"{normalized}|size={size}"`) จะ MISS
→ re-fetch จาก API → ได้ data ใหม่ที่มี title, apa_*

**Optional cleanup SQL:**
```sql
-- ล้าง cache เก่า (v1 format) หลัง 7 วัน เมื่อ traffic ลดลง
DELETE FROM thaijo_search_cache WHERE api_called_at < NOW() - INTERVAL '1 day';
-- หรือล้างทันที:
TRUNCATE thaijo_search_cache;
```

**Acceptance criteria:**
- [ ] Cache key format เปลี่ยนเป็น `v2:...`
- [ ] ทุก search term ที่ถามหลัง deploy จะ miss cache → re-fetch → ได้ data ใหม่
- [ ] New cache entries มี `title`, `apa_authors`, `apa_year` ใน `results_json`

**Scope:** XS
**Fixes:** RC-CE-1 (cache stale data)

---

### Task D6 (XS): ตรวจสอบว่า ThaiJO microservice return `title` field ใน API response

**Background:**
`_search_thaijo_impl()` ส่ง `"title": True` ใน payload (ใช้สำหรับ search filter)
แต่ยังไม่ทราบว่า microservice return `title` ใน response articles หรือไม่

**ขั้นตอน:**
```bash
# เรียก microservice โดยตรง (ไม่ผ่าน agent cache)
curl -s -X POST http://localhost:8505/search \
  -H "Content-Type: application/json" \
  -d '{"term": "อุบัติเหตุทางถนน", "size": 2, "strict": true, "title": true}' \
  | python -m json.tool | head -50

# ดูว่า results[0] มี field ไหนบ้าง
```

**ผลลัพธ์ที่คาดไว้:**
- Case A: microservice return `title` field → Task D1 `api_title = article.get("title", "")` จะได้ค่า → title ดีขึ้นทันที
- Case B: microservice ไม่ return `title` → ต้องพึ่ง `_extract_apa_fields()` เท่านั้น

**นี่ควร verify ก่อน Task D1** เพื่อให้รู้ว่า title parsing priority ควรเป็นอย่างไร

**Scope:** XS
**Fixes:** confirmation for D1

---

## Task Order & Dependencies

```
Task D6 (XS) ── verify microservice title field  ← ทำก่อนเสมอ
    │
    ▼
Task D1 (S)  ── pre-extract title + apa_* in thaijo.py  ← core fix
    │
    ├── Task D5 (XS) ── bump cache key to v2  ← run immediately after D1
    │
    ├── Task D2 (XS) ── Searcher schema update  ← parallel with D3, D4
    ├── Task D3 (XS) ── Screener schema update  ← parallel with D2, D4
    └── Task D4 (XS) ── Citation Agent prompt   ← parallel with D2, D3
```

**Priority:** D6 → D1 → D5 → (D2 + D3 + D4 parallel)
**Total scope:** ~1 วัน

---

## Checkpoints

### Checkpoint หลัง Task D1 + D5
- [ ] `POST /api/thaijo/search` response มี `title`, `apa_authors`, `apa_year` ใน articles
- [ ] ถ้า `reference` มีข้อมูล → `apa_year` ถูกต้อง
- [ ] ถ้า `reference = null` → `title = None` (ไม่ใช่ fake string)
- [ ] Cache key format เปลี่ยนเป็น v2 (ยืนยันด้วย DB query)

### Checkpoint หลัง Task D2 + D3 + D4
- [ ] รัน Tab 2 "สร้างรายงานวิจัย" → Citation Agent output มี title จริง
- [ ] title ≠ "สรุปบทความที่ N เกี่ยวกับ..."
- [ ] `text_snippet` ≠ `title` (ต่างกัน)
- [ ] `apa_authors` และ `apa_year` มีค่า (เมื่อ reference ไม่ใช่ null)
- [ ] `apa_authors = null` และ `apa_year = null` เฉพาะเมื่อ reference = null จริง

### Final Checkpoint
- [ ] Tab 1 search: `title` field แสดงใน article cards (UI)
- [ ] Tab 2 report: APA bibliography แสดงผู้แต่งและปีถูกต้อง (เมื่อ reference available)
- [ ] No regression: non-ThaiJO citations (document, database) ยังทำงานปกติ

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Microservice ไม่ return `title` (Case B) | Low — _extract_apa_fields() เป็น fallback | Verify ใน Task D6 ก่อน |
| `_extract_apa_fields()` parse ผิดสำหรับ reference บางรูปแบบ | Medium — title ผิดดีกว่า null ผิด | Log ทุก parse attempt, fail gracefully (return None) |
| Cache bump (v2) ทำให้ทุก request ช้า (re-fetch) | Low — cache fill ใน 1-2 วัน | ยอมรับได้ |
| Screener LLM drop title field ระหว่าง HOP 2 | Medium — RC-CE-1 residual risk | คำเตือนใน Screener prompt + ตรวจสอบ Screener output ใน _parse() |
| `reference` format แตกต่างจาก standard APA | Medium | regex test กับ sample ก่อน deploy |

---

## ไม่ต้องแก้ (Out of Scope)

- `apa_publisher` สำหรับ thaijo_article ยังคงเป็น null — TCI-THAIJO ไม่ expose สำนักพิมพ์
  ใช้ `apa_journal` แทน (journal name เป็น publisher สำหรับ articles)
- Screener tools (ยังคงเป็น pure LLM) — เพิ่ม schema pass-through เพียงพอ
- หาก reference = null — apa_authors/year ยังเป็น null (correct behavior)

---

## Open Questions

1. **[CRITICAL] ThaiJO microservice (:8505) return `title` field ไหม?**
   → ตอบได้ใน Task D6 (curl ทดสอบโดยตรง)

2. **[MEDIUM] Thai APA format แตกต่างจาก standard อย่างไร?**
   → ตัวอย่าง real references จาก search_thaijo — sample 5 รายการ
   → ใช้ confirm regex pattern ก่อน deploy _extract_apa_fields()

3. **[LOW] ควร clear cache ทั้งหมดหรือ bump version?**
   → แนะนำ version bump (v2) — ไม่ทำลายข้อมูล, re-fill อัตโนมัติ

---

*Last updated: 2026-04-19 | Investigation version 1.0*
*Root causes: RC-CE-1 (critical, core fix), RC-CE-2..5 (downstream effects)*
*Single fix at tool level (D1) resolves majority of hallucination pattern*
