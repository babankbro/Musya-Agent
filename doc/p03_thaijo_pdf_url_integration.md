# P03 — ThaiJO pdf_url Integration: Comparison & Fix Plan

**Date**: 2026-04-19  
**Status**: PLAN

---

## 1. Comparison: สร้างรายงานวิจัย vs ทดสอบ Agent Multi-Query

| ด้าน | Tab "สร้างรายงานวิจัย" (6-agent pipeline) | Tab "ทดสอบ Agent" Section B (Multi-Query) |
|------|------------------------------------------|------------------------------------------|
| **Trigger** | CrewAI Crew.kickoff() → 6 tasks sequential | JS loop: `/api/thaijo/search` × N queries |
| **Agent ที่ค้นหา** | `ThaiJO Searcher` (CrewAI Agent + `search_thaijo` tool) | ไม่มี agent — เรียก REST endpoint โดยตรง |
| **URL ที่ได้** | ผ่าน `search_thaijo` tool → `_normalize_to_view_url()` → valid URL | ผ่าน `_search_thaijo_impl()` → `_normalize_to_view_url()` → valid URL |
| **ต้นทาง URL เดียวกัน?** | ✅ เหมือนกัน — ทั้งคู่ผ่าน `_search_thaijo_impl` และ `_normalize_to_view_url` |  |
| **สิ่งที่ต่าง** | Searcher LLM **อาจเขียน URL ใหม่** ใน output JSON ของตัวเอง (hallucinate) | JS ใช้ JSON จาก API โดยตรง ไม่มี LLM ระหว่างกลาง |
| **Dedup** | LLM Searcher → ตาม prompt ("ลบซ้ำด้วย pdf_url") | JS: `seenUrls` Set keyed on `pdf_url` |
| **ผ่าน evidence_registry?** | ✅ Citation Agent เรียก `lookup_thaijo_evidence` → `register_evidence` → INSERT | ❌ ไม่เขียน evidence_registry เลย |
| **URL verification** | `register_evidence` เรียก `_confirm_thaijo_url()` + `_is_valid_thaijo_url()` | ไม่มี |
| **ปัญหา URL ที่เหลือ** | LLM Searcher ใน task อาจ output URL รูปแบบผิดใน JSON ก่อนถึง Citation Agent | ไม่มีปัญหา URL (ดึงจาก REST API โดยตรง) |

---

## 2. URL Flow ในระบบ — ทุก path

```
ThaiJO Microservice (port 8505)
        │
        │  returns: {pdf_url, summary, reference}
        │  pdf_url อาจเป็น:
        │    /article/view/3802            (canonical)
        │    /article/view/3802/6365       (with file segment ← valid)
        │    /article/download/252647/170884  (download ← ต้อง normalize)
        │
        ▼
_search_thaijo_impl()  [src/tools/thaijo.py]
  1. cache check (PostgreSQL thaijo_search_cache)
  2. API call if miss
  3. _normalize_to_view_url():  /download/ → /view/
  4. _is_valid_thaijo_url():    filter invalid
  5. _extract_article_fields(): title, apa_year, apa_authors, apa_journal
  6. cache write (only if enriched non-empty — v4)
  7. returns JSON {count, results[]}
        │
   ┌────┴──────────────────────────────────────────────┐
   │                                                   │
   ▼  (Tab "ค้นหาบทความ" / Tab "ทดสอบ Agent")         ▼  (Tab "สร้างรายงานวิจัย")
/api/thaijo/search                            search_thaijo @tool
  strict retry if 0                           (same _search_thaijo_impl)
  returns ThaiJOArticle[]                             │
  pdf_url = validated view URL ✅              ▼
  No LLM in between ✅                 ThaiJO Searcher (CrewAI Agent)
  Not stored in evidence_registry ❌     LLM reads tool output JSON
                                          LLM writes its own output JSON
                                          ⚠️ LLM may mutate pdf_url here
                                                  │
                                                  ▼
                                         Article Screener (LLM)
                                          copies pdf_url — may drift again
                                                  │
                                                  ▼
                                         Citation Agent (LLM)
                                          calls lookup_thaijo_evidence(pdf_url)
                                            → PostgreSQL thaijo_search_cache
                                            → re-validates URL
                                          calls register_evidence()
                                            → _confirm_thaijo_url()
                                            → INSERT evidence_registry
                                                  │
                                                  ▼
                                         evidence_registry (PostgreSQL)
                                            open_url = confirmed view URL
                                            ⚠️ อาจเป็น /view/3802 (ไม่มี file seg)
                                               แต่ ThaiJO microservice embed
                                               /view/3802/6365 ใน summary
```

---

## 3. Root Causes — ความไม่สอดคล้องของ pdf_url

### RC-P3-1: evidence_registry เก็บ URL ที่ต่างจาก summary embed

**สาเหตุ**: `_confirm_thaijo_url()` ทำ JSONB query ด้วย `pdf_url` canonical (`/view/3802`)  
แต่ thaijo_search_cache เก็บ URL จาก microservice ซึ่งอาจเป็น `/view/3802/6365`  
→ JSONB `@>` match ล้มเหลว → URL cleared → evidence_registry ได้ `open_url = ""`

**Evidence**: cache entry มี  
```json
{"pdf_url": "https://he05.tci-thaijo.org/index.php/WESR/article/view/3802/6365"}
```
แต่ `_confirm_thaijo_url("https://.../view/3802")` ค้นด้วย  
```sql
WHERE results_json @> '[{"pdf_url": "https://.../view/3802"}]'::jsonb
```
→ ไม่ match (JSON exact match ต้องการ string เหมือนกัน 100%)

### RC-P3-2: LLM Searcher อาจ mutate pdf_url ใน output JSON

**สาเหตุ**: CrewAI Searcher LLM เขียน JSON output เอง — อาจเปลี่ยน `/view/3802/6365` → `/view/3802` หรือ `/download/3802/6365` โดยไม่รู้ตัว แม้ prompt จะบอกห้ามเปลี่ยน  
→ URL ที่ถึง Citation Agent อาจไม่ตรงกับ cache entry

### RC-P3-3: lookup_thaijo_evidence ไม่รองรับ URL ที่มี file segment

**สาเหตุ**: `normalized_url = _normalize_to_view_url(pdf_url)` แปลง `/download/` → `/view/` แต่ URL `/view/3802/6365` ผ่านมาเป็น `/view/3802/6365` ไม่เปลี่ยน ซึ่ง valid แล้ว  
แต่ cache เก็บ `/view/3802/6365` ขณะที่ Citation Agent ส่ง `/view/3802` มา → miss

### RC-P3-4: Tab UI ทดสอบ Agent ไม่เขียน evidence_registry

**สาเหตุ**: Section B เรียกแค่ `/api/thaijo/search` แล้วแสดงผล ไม่ได้เรียก `register_evidence`  
→ ไม่สามารถใช้ Tab ทดสอบ Agent เพื่อ verify URL ใน evidence_registry ได้

---

## 4. Fix Tasks

### Task F1 — ปรับ _confirm_thaijo_url ให้ match ทั้ง canonical และ file-segment URL

**File**: `src/agents/citation_evidence.py`  
**Function**: `_confirm_thaijo_url(pdf_url, search_term)` และ `lookup_thaijo_evidence()`

**Problem**: JSONB query `WHERE results_json @> '[{"pdf_url": ".../view/3802"}]'` จะ miss ถ้า cache เก็บ `.../view/3802/6365`

**Fix**: เพิ่ม fallback — ถ้า exact match miss ให้ลอง prefix match:
```sql
WHERE results_json::text LIKE '%/view/3802%'
```
หรือดีกว่า: query ด้วย `results_json::text LIKE %s` ด้วย pattern `%/article/view/3802%` เพื่อ match ทั้ง `/view/3802` และ `/view/3802/6365`

**Implementation**:
```python
# Current (exact match only):
WHERE results_json @> %s::jsonb  # hits /view/3802 only

# Fix (add prefix fallback):
article_id = re.search(r'/article/view/(\d+)', normalized_url)
if article_id:
    rows = query_db(
        "SELECT results_json FROM thaijo_search_cache "
        "WHERE results_json::text LIKE %s AND expires_at > NOW() LIMIT 1",
        (f'%/article/view/{article_id.group(1)}%',)
    )
    # pick the article whose pdf_url starts with /view/{article_id}
```

---

### Task F2 — lookup_thaijo_evidence: รองรับ URL ทั้งสองรูปแบบ

**File**: `src/agents/citation_evidence.py`  
**Function**: `lookup_thaijo_evidence()`

**Fix**: ใน Step 1 (cache lookup) เพิ่ม fallback ค้นด้วย article ID แทน exact URL:
1. ลอง exact match ด้วย `normalized_url` (เหมือนเดิม)
2. ถ้า miss → extract article ID (`/view/(\d+)`) → ค้น `results_json::text LIKE '%/view/{id}%'`
3. Return article ที่ `pdf_url` starts with `/view/{id}` (เลือก URL ยาวสุด = most specific)

**Return url**: คืน URL ที่อยู่ใน cache จริง (อาจเป็น `/view/3802/6365`) ไม่ใช่ URL ที่ส่งเข้ามา  
→ evidence_registry จะเก็บ URL ที่ตรงกับ summary embed เสมอ

---

### Task F3 — evidence_registry: เพิ่ม endpoint แสดง ThaiJO URL ที่ missing หรือ broken

**File**: `src/routers/thaijo.py`  
**New endpoint**: `GET /api/thaijo/evidence-audit`

**Returns**:
```json
{
  "total": 15,
  "missing_url": [{"evidence_id": "...", "title": "..."}],
  "unverified_url": [{"evidence_id": "...", "open_url": "...", "in_cache": false}],
  "ok": [...]
}
```

**Logic**:
1. Query `evidence_registry WHERE evidence_type = 'thaijo_article'`
2. For each: check `open_url` against `thaijo_search_cache` using article ID prefix match (F1 logic)
3. Return categorized list

---

### Task F4 — Tab "ทดสอบ Agent": Section D — Evidence Registry Audit

**File**: `static/thaijo_research_ui.html`  
**Add**: Section D ใน panel-agent-test

**UI**:
- Button "🔍 Audit Evidence Registry" → `GET /api/thaijo/evidence-audit`
- 3 columns: ✅ OK | ⚠️ URL missing | ❌ URL not in cache
- Per-row: evidence_id, title, open_url (clickable if valid), "fix" action button
- "Fix All" button → POST `/api/thaijo/sync-evidence` → re-run

---

### Task F5 — Tab "ทดสอบ Agent": Section A แสดง comparison กับ evidence_registry

**File**: `static/thaijo_research_ui.html`  
**Enhancement**: เพิ่มใน Section A article card — ตรวจสอบว่า `pdf_url` ของบทความนี้อยู่ใน evidence_registry หรือไม่

**Logic**: หลัง render articles เรียก `GET /api/thaijo/evidence-audit` → mark แต่ละ card ด้วย:
- 🟡 ยังไม่ได้ register
- ✅ registered + URL ตรง
- ❌ registered แต่ URL ไม่ตรง

---

## 5. Data Flow หลัง Fix

```
ThaiJO Microservice
    → /article/view/3802/6365  (จาก Redis pdf_cache)
    → เก็บใน thaijo_search_cache ด้วย key v4 ✅

lookup_thaijo_evidence(pdf_url="/view/3802")
    → exact miss
    → prefix search: LIKE '%/view/3802%'
    → found: pdf_url="/view/3802/6365"  ← URL ใน cache จริง
    → return pdf_url="/view/3802/6365"  ✅

register_evidence(open_url="/view/3802/6365")
    → _confirm_thaijo_url("/view/3802/6365")
    → exact match FOUND ✅
    → INSERT open_url="/view/3802/6365"

evidence_registry
    → open_url = "/view/3802/6365"  ← URL ที่คลิกได้จริง ✅

Tab "ทดสอบ Agent" Section D
    → Audit: open_url "/view/3802/6365" ← in_cache: true ✅
```

---

## 6. ลำดับ Implementation

```
F1 → F2 (backend, แก้ URL mismatch ที่ root) 
F3 (endpoint audit)
F4 (UI Section D)
F5 (UI card comparison) — ถ้า F3 เสร็จแล้ว
```

## 7. Files

| File | Task | Change |
|------|------|--------|
| `src/agents/citation_evidence.py` | F1 | `_confirm_thaijo_url()` — prefix match fallback |
| `src/agents/citation_evidence.py` | F2 | `lookup_thaijo_evidence()` — article ID prefix search |
| `src/routers/thaijo.py` | F3 | `GET /api/thaijo/evidence-audit` endpoint |
| `static/thaijo_research_ui.html` | F4 | Section D — Evidence Registry Audit panel |
| `static/thaijo_research_ui.html` | F5 | Section A card — in-registry badge |
