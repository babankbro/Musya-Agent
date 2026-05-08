# D02 — ThaiJO URL Normalization & Search Fix Plan

**Date**: 2026-04-19  
**Status**: PLAN  
**Previous**: d01_citation_thaijo_data_quality.md (pre-extraction of title/apa_* at tool level)

---

## Summary of Issues

After D01 implementation the Searcher agent still outputs `/article/download/` URLs (instead of `/article/view/`) and some articles still have `title: null`. Additionally Tab 1 "ค้นหาข้อมูล" fails for multi-word Thai queries. Four root causes identified.

---

## Root Causes

### RC-A — Download URL Leak into Searcher Output

**Symptom**: Searcher JSON contains  
`"pdf_url": "https://he01.tci-thaijo.org/index.php/jnat/article/download/252647/170884"`

**Evidence from D01**: `THAIJO_URL_PATTERN` only accepts `/article/view/\d+` — any download URL returned by the microservice is filtered by `_is_valid_thaijo_url()` and the article is dropped from `enriched`.

**Most-probable cause (from data)**: The microservice's `summary` text embeds a download hyperlink inside the Thai prose (e.g. "…อ่านเพิ่มเติมที่ https://…/download/252647/170884"). The LLM Searcher reads the full summary text and picks this embedded URL to fill its `pdf_url` field, overriding the validated `pdf_url` that was already null for that article.

**Secondary cause**: When the article was truly filtered out, the LLM Searcher hallucinates a plausible ThaiJO URL by appending a secondary ID it saw in the summary text, producing `/download/` format.

**Why filter alone is insufficient**: `_is_valid_thaijo_url()` runs at *tool* level; the LLM Searcher writes its *output* JSON free-form. There is no validation of the Searcher's JSON output at the orchestrator level.

---

### RC-B — Tab 1 Search Returns 0 for Multi-Word Thai Queries

**Symptom**: Searching "อุบัติเหตุ ปัจจัยเสี่ยง ถนน ยโสธร" from Tab 1 UI returns empty.

**Cause**: `POST /api/thaijo/search` passes `strict=True` (default). ThaiJO backend treats `strict=True` as AND-match across all 4 words in full-text index. A 4-word Thai query often returns 0 results on `strict=True` because THAIJO full-text index does not tokenize Thai words by default — the entire term must appear verbatim.

The agent pipeline already handles this (it retries with `strict=False` when `count==0`), but the direct `/api/thaijo/search` endpoint used by Tab 1 does **not** implement this retry.

---

### RC-C — `title: null` for Articles with Plain-Text Summaries

**Symptom**: `"title": null` when the summary is raw Thai prose without the `**สรุปบทความวิชาการ: "TITLE"**` header.

**Cause**: `_SUMMARY_TITLE_RE` requires the GPT-4.1 standard header. Some articles in the ThaiJO microservice have legacy/raw summaries (no structured header). The current fallback in `_extract_article_fields` only extracts from Vancouver reference (`[internet]` marker). APA-format references have no `[internet]` → title also stays null.

**Data from failed article**:  
```
summary: "การวิจัยครั้งนี้มีวัตถุประสงค์..."  (no header)
reference: "ณัฐกานต์ หอมหวล, & สุวิณี วิวัฒน์วานิช. (2022). ปัจจัยที่มีผลต่อการเกิดอุบัติเหตุ... วารสารวิทยาศาสตร์สุขภาพ, 5(3), 49–60."
```
Reference is APA format — no `[internet]` → `internet_pos == -1` → journal/title extraction skipped.

---

### RC-D — APA-Format Reference Year & Journal Not Extracted

**Symptom**: `apa_year: "2022"` was correctly shown (from data above), but the journal appears wrong or null for APA references in some cases.

**Cause**: 
- `_REF_YEAR_RE = re.compile(r'\[internet\]\.\s+(\d{4})')` — only matches Vancouver format.  
  APA format: `". (2022)."` → year **not** matched → `apa_year: null`.
- Journal extraction also tied to `[internet]` position → skipped for APA.

**Note**: In the specific example, `apa_year` showed `"2022"` — investigation needed whether a different code path happened, or the actual microservice reference format was Vancouver for that article. The fix must handle both formats robustly.

---

## Fix Tasks

### Task D2-1 — URL Normalization: Convert Download → View URL

**File**: `src/tools/thaijo.py`  
**Scope**: Add `_normalize_to_view_url()` helper; apply to Searcher prompt guardrail.

**Logic**:
```
/article/download/{article_id}/{file_id}  →  /article/view/{article_id}
```
Pattern: `re.compile(r'(https?://[^/]+/index\.php/[^/]+)/article/download/(\d+)/\d+')`  
Replace with: `\1/article/view/\2`

**Apply at**:
1. After receiving `pdf_url` from microservice — normalize before `_is_valid_thaijo_url()` check (so valid download URLs become view URLs instead of being filtered away entirely)
2. Add to Searcher prompt: "ถ้า pdf_url มีรูปแบบ `/article/download/ID/FILEID` ให้เปลี่ยนเป็น `/article/view/ID` ก่อน copy"

**Acceptance criteria**:
- `_normalize_to_view_url("https://he01.tci-thaijo.org/index.php/jnat/article/download/252647/170884")` → `"https://he01.tci-thaijo.org/index.php/jnat/article/view/252647"`
- Normalized URL passes `_is_valid_thaijo_url()`
- Articles previously lost due to download URL are now included in enriched list

---

### Task D2-2 — Tab 1 Search: Strict Fallback in Router Endpoint

**File**: `src/routers/thaijo.py`  
**Scope**: `thaijo_search()` endpoint — add automatic retry with `strict=False` when `strict=True` returns 0 results.

**Logic** (mirror agent behavior):
```python
if strict=True and count == 0:
    retry with strict=False
    return retry results
```

**Also**: Add `title`, `apa_authors`, `apa_year`, `apa_journal` fields to `ThaiJOArticle` Pydantic model so Tab 1 results display these pre-extracted fields.

**Acceptance criteria**:
- Searching "อุบัติเหตุ ปัจจัยเสี่ยง ถนน ยโสธร" in Tab 1 returns results
- Response includes `title`, `apa_authors`, `apa_year`, `apa_journal` fields
- Retry is transparent to the caller (single response with `note` field indicating retry was used)

---

### Task D2-3 — Title Fallback for Plain-Text Summaries

**File**: `src/tools/thaijo.py`, function `_extract_article_fields()`  
**Scope**: Add 2 extra title fallback strategies when `_SUMMARY_TITLE_RE` doesn't match.

**Fallback chain** (after existing strategies):

**Fallback 3 — APA reference title extraction**:
```
Pattern: ". (YEAR). TITLE. JOURNAL, vol(issue),"
Extract: text between ". (YEAR). " and the last ". JOURNAL"
```
Regex: `r'\.\s*\(\d{4}\)\.\s*(.+?)\.\s*[^\.\,]+,\s*\d'`

**Fallback 4 — Summary first meaningful line**:
If summary doesn't have the header AND APA title extraction fails:
- Take the first 200 characters of summary
- Strip markdown (`**`, `*`, `#`)
- Trim to first sentence (up to first `。` or `. ` or `\n`)
- Use as title IF length 10–150 characters (avoids picking up boilerplate)

**Acceptance criteria**:
- Article with APA reference `"Author. (2022). ชื่อบทความจริง. วารสาร, 5(3)..."` → `title = "ชื่อบทความจริง"`
- Article with raw summary `"การวิจัยครั้งนี้มีวัตถุประสงค์เพื่อ..."` and no APA → `title` = first sentence of summary
- Original `_SUMMARY_TITLE_RE` (header format) remains priority 1

---

### Task D2-4 — APA Reference: Year & Journal Extraction

**File**: `src/tools/thaijo.py`, function `_extract_article_fields()`  
**Scope**: Add APA format parsing as fallback when Vancouver `[internet]` is absent.

**APA year pattern**: `_APA_YEAR_RE = re.compile(r'\.\s*\((\d{4})\)')`  
Apply after `_REF_YEAR_RE` fails (no `[internet]` found).

**APA journal pattern**:  
APA format: `"AUTHORS. (YEAR). TITLE. JOURNAL_NAME, VOL(ISSUE), PAGES."`  
Journal is segment after last `. ` before `, VOL(ISSUE)` or before `. DOI`.  
Regex: `r'\.([^\.]+),\s*\d+\s*\(\d+\)'` — captures journal name before volume notation.

**APA authors**:  
For APA format `"LastName, F., & LastName2, F. (YEAR)."` the current `reference[:first_dot]` extracts only the first author's surname. Fix: take everything before `. (YEAR).` as authors.  
Pattern: `r'^(.+?)\.\s*\(\d{4}\)'`

**Acceptance criteria**:
- Reference `"ณัฐกานต์ หอมหวล, & สุวิณี วิวัฒน์วานิช. (2022). ชื่อ. วารสาร, 5(3), 49–60."`:
  - `apa_year = "2022"`
  - `apa_authors = "ณัฐกานต์ หอมหวล, & สุวิณี วิวัฒน์วานิช"`
  - `apa_journal = "วารสาร"`
- Vancouver reference still works (no regression)

---

### Task D2-5 — Cache Bump: v3 Key to Force Re-fetch with Normalized URLs

**File**: `src/tools/thaijo.py`, function `_cache_key()`  
**Scope**: Bump cache version from `v2` to `v3` so all existing cache entries (possibly with download URLs) are invalidated and articles are re-fetched with the new normalization applied.

**Change**:
```python
# Before
return sha256(f"v2:{normalized}|size={size}".encode()).hexdigest()
# After  
return sha256(f"v3:{normalized}|size={size}".encode()).hexdigest()
```

**Why**: v2 cache entries may contain articles with un-normalized URLs or missing `title` fields (from pre-D2-3 extraction). v3 forces fresh API calls so all articles go through the new normalization + extraction pipeline.

**Acceptance criteria**:
- First search after deploy goes to API (cache miss for all v2 keys)
- Cached results contain normalized view URLs and populated `title` fields where possible

---

## Implementation Order

```
D2-1 → URL normalization (core fix, unblocks correct pdf_url)
D2-4 → APA year/journal/authors (needed for D2-3 APA title fallback)
D2-3 → Title fallbacks (depends on D2-4 for APA path)
D2-5 → Cache bump (depends on D2-1, D2-3, D2-4 being complete)
D2-2 → Tab 1 strict fallback (independent, can run in parallel with D2-1)
```

---

## Files to Modify

| File | Task | Change |
|------|------|--------|
| `src/tools/thaijo.py` | D2-1 | Add `_normalize_to_view_url()`, apply before URL validation |
| `src/tools/thaijo.py` | D2-3 | Add fallback 3 (APA title) + fallback 4 (summary first line) |
| `src/tools/thaijo.py` | D2-4 | Add `_APA_YEAR_RE`, APA journal/authors parsing |
| `src/tools/thaijo.py` | D2-5 | Bump cache key to v3 |
| `src/routers/thaijo.py` | D2-2 | Add strict→non-strict retry; add new fields to `ThaiJOArticle` |
| `src/agents/thaijo_searcher.py` | D2-1 | Add prompt note about download URL normalization |

---

## Testing

After implementation, verify with test data from `thaijo_test.json`:
1. `pdf_url` containing `/article/download/` → normalized to `/article/view/`  
2. Tab 1 search for "อุบัติเหตุ ปัจจัยเสี่ยง ถนน ยโสธร" → returns results  
3. Article with APA reference → `title`, `apa_year`, `apa_journal` populated  
4. Article with plain-text summary → `title` = first sentence (not null)  
5. Cache miss on first query after v3 bump  
