# P02 — Agent Test UI Tab Plan

**Date**: 2026-04-19  
**Status**: PLAN (v2 — updated with real-URL linking)  
**File to modify**: `static/thaijo_research_ui.html`, `src/tools/thaijo.py`

---

## Goal

Add a new **"🧪 ทดสอบ Agent"** tab (5th tab) to the existing UI that lets developers:

1. **Section A — Direct API Test** (`/api/thaijo/search`): single-query search with full output including `title`, `apa_*` fields, cache-HIT/MISS badge, and clickable real article URL.
2. **Section B — Multi-Query Searcher Test** (ThaiJO Searcher Agent): run multiple queries at once, see deduplication result and per-query cache status — mirrors how the agent pipeline works. All article URLs clickable.
3. **Section C — Sync Evidence** (`/api/thaijo/sync-evidence`): trigger sync with result detail table, no need to go to Cache tab.

**Also fix** two related issues in the existing UI and backend:
- **Cache tab**: Make article URLs clickable — extract real view URL from Redis summary text.
- **Backend**: `_VIEW_EXTRA_SEGMENT_RE` incorrectly strips `/article/view/3802/6365` → `/article/view/3802`. The full URL with file segment IS valid on ThaiJO (confirmed by user). Fix: preserve view URLs with extra segments as-is.

---

## Current State

**Existing tabs** (4):
- `search` → `panel-search`: single `/api/thaijo/search` call, shows article cards
- `report` → `panel-report`: 6-agent pipeline via SSE
- `status` → `panel-status`: health/config
- `cache` → `panel-cache`: Redis inspector + Sync Evidence button

**`switchTab()` function** hardcodes the 4 tab IDs:
```js
['search', 'report', 'status', 'cache'].forEach(t => { ... })
```
Must be updated to include `'agent-test'`.

**`ThaiJOArticle` model** (from D02): now includes `title`, `apa_authors`, `apa_year`, `apa_journal`.  
**`/api/thaijo/search`** (from D02): auto-retries with `strict=False` when 0 results, returns `note` field.  
**`/api/thaijo/sync-evidence`**: POST, returns `{ synced, cleared, skipped, errors, detail[] }`.

### URL Data Sources (critical for real-link feature)

ThaiJO has **two URL formats** for view links:
```
/article/view/3802          ← canonical (article-only, always works)
/article/view/3802/6365     ← with file segment (direct to specific PDF version)
```

Both are valid and open in browser. The second form is what the microservice embeds in `summary` text.

**Redis `pdf_cache:<sha256(url)>` key** stores: the GPT-4.1 summary which **always contains the real URL** in this format:
```
(อ้างอิงจาก: https://he05.tci-thaijo.org/index.php/WESR/article/view/3802/6365)
```
or
```
**สรุปบทความวิชาการ: "TITLE"**
(อ้างอิงจาก: https://...)
```

**PostgreSQL `thaijo_search_cache` entry** (`pdf_url` field): the canonical view URL (after D02 normalization) — may be `/article/view/3802` (without file segment).

**Priority for "best clickable URL"**:
1. URL extracted from summary text (preserves file segment, most direct link)
2. `pdf_url` field from search cache (canonical view URL, always valid)

### Bug: `_VIEW_EXTRA_SEGMENT_RE` in `src/tools/thaijo.py`

The hook-added code at lines 29-58 strips file segments:
```python
# /article/view/3802/6365  →  /article/view/3802
_VIEW_EXTRA_SEGMENT_RE = re.compile(r'^(https?://[^/]+/index\.php/[^/]+/article/view/(\d+))/\d+(.*)$')
```

This **loses the file segment** from a valid URL. Fix: remove Case 2 from `_normalize_to_view_url()` — only normalize download URLs, not view URLs with extra segments.

---

## New Tab Specification

### Tab Button (insert after Cache tab button, line ~67)
```html
<button onclick="switchTab('agent-test')" id="tab-agent-test"
    class="tab-btn px-4 py-1.5 rounded-lg text-sm font-medium text-white/70 hover:text-white transition-all">
    🧪 ทดสอบ Agent
</button>
```

### Panel `panel-agent-test` (insert after `panel-cache` closing `</div>`)

Three sections inside one `<div id="panel-agent-test" class="hidden space-y-6">`:

---

#### Section A — Direct API Test

**UI elements**:
- Search term input (pre-filled: `อุบัติเหตุ ปัจจัยเสี่ยง ถนน มุกดาหาร`)
- Size selector (3/5/10)
- Strict checkbox
- "🔍 ทดสอบ API" button → calls `POST /api/thaijo/search`

**Result display**:
- Stats row: `count` | strict retry used (from `note` field) | request time (ms)
- Cache status badge per article: if the result came back instantly (< 500ms) → show **🟢 CACHE HIT**; otherwise **🔵 API CALL**
- Article cards: `title` (not null), `apa_year`, `apa_authors`, `apa_journal`, clickable `pdf_url` (open in new tab), `summary` collapsible
- Raw JSON toggle (collapsible `<pre>` block)

**JS function**: `testDirectApi()`  
**Element IDs**: `#agent-test-term`, `#agent-test-size`, `#agent-test-strict`, `#agent-test-api-result`

---

#### Section B — Multi-Query Searcher Test

**Purpose**: Simulate what the ThaiJO Multi-Query Searcher agent does — run N queries, show per-query status, deduplicate by `pdf_url`.

**UI elements**:
- Textarea for queries (one per line), pre-filled with 3 example queries matching the failing case:
  ```
  อุบัติเหตุ ปัจจัยเสี่ยง ถนน มุกดาหาร
  อุบัติเหตุ ปัจจัยเสี่ยง ถนน ยโสธร
  อุบัติเหตุทางถนน พฤติกรรมเสี่ยง
  ```
- Size per query (default 5)
- "▶ รัน Multi-Query" button → calls `/api/thaijo/search` for each query sequentially, then deduplicates

**Result display**:
- Query results table (one row per query):
  | Query | Count | Strict | Time (ms) | Status |
  |---|---|---|---|---|
  | อุบัติเหตุ... | 3 | ✓ | 245ms | 🟢 CACHE HIT |
  | อุบัติเหตุ... | 0→5 | ✗ fallback | 1420ms | 🔵 API CALL |
- Summary: Total raw = N, Unique (after dedup) = M
- Merged article cards (same as Section A but tagged with source query badges)

**JS function**: `testMultiQuery()`  
**Element IDs**: `#agent-test-queries`, `#agent-test-multi-size`, `#agent-test-multi-result`, `#agent-test-multi-table`

---

#### Section C — Sync Evidence

**UI elements**:
- Description: "อัปเดต evidence_registry จาก ThaiJO search cache"
- "🔗 Sync Evidence Registry" button → `POST /api/thaijo/sync-evidence`
- Loading spinner

**Result display**:
- Stats chips: `synced N` (green) | `cleared N` (red) | `skipped N` (gray) | `errors N` (orange)
- Detail table (if `detail` array returned):
  | pdf_url | action | reason |
  |---|---|---|
  | https://... | synced | url matched cache |
  | https://... | cleared | url not in cache |
- Timestamp of last sync

**JS function**: `testSyncEvidence()`  
**Element IDs**: `#agent-test-sync-result`, `#agent-test-sync-table`, `#agent-test-sync-stats`

---

## Implementation Plan

### Task T0 — Fix `_normalize_to_view_url` in backend (1 file, ~10 lines removed)

**File**: `src/tools/thaijo.py`  
**Change**: Remove `_VIEW_EXTRA_SEGMENT_RE` and Case 2 from `_normalize_to_view_url()`. Keep only Case 1 (download → view conversion).

Before:
```python
# Case 2: /article/view/NNN/MMM → strip extra segment
m2 = _VIEW_EXTRA_SEGMENT_RE.match(url)
if m2:
    normalized = m2.group(1)
    ...
    return normalized
```
After: delete these lines. View URLs with file segments are valid — do not mutate them.

**Also update** `THAIJO_URL_PATTERN` to accept `/article/view/\d+(?:/\d+)?` so view URLs with file segments pass validation:
```python
THAIJO_URL_PATTERN = re.compile(
    r'^https://he0[1-9]\.tci-thaijo\.org/index\.php/[^/]+/article/view/\d+(?:/\d+)?'
    r'|^https://tci-thaijo\.org/index\.php/[^/]+/article/view/\d+(?:/\d+)?'
)
```

**Cache key**: bump to `v4` so articles re-fetched with corrected URLs cached freshly.

---

### Task T1 — Update `switchTab()` (1 change, 1 line)

Add `'agent-test'` to the tab ID array in `switchTab()`.

**Line**: ~514 in current file  
**Change**: `['search', 'report', 'status', 'cache']` → `['search', 'report', 'status', 'cache', 'agent-test']`

---

### Task T2 — Add Tab Button

Insert after the Cache tab button (line ~67).

---

### Task T3 — Add Panel HTML

Insert `<div id="panel-agent-test" class="hidden space-y-6">` with all three sections after the closing `</div>` of `panel-cache` (around line ~511).

**Section A HTML**: search form + result container  
**Section B HTML**: multi-query textarea + results table + merged cards container  
**Section C HTML**: sync button + stats + detail table  

---

### Task T4 — Add JS Functions

Insert JS functions before the closing `</script>` tag:

```js
// Shared: extract best clickable URL from article data
function extractBestUrl(article) {
    const m = (article.summary || '').match(
        /https?:\/\/[a-z0-9]+\.tci-thaijo\.org\/index\.php\/[^\/\s]+\/article\/view\/\d+(?:\/\d+)?/
    );
    return m ? m[0] : (article.pdf_url || null);
}

// Shared: linkify ThaiJO URLs in text
function linkifySummary(text) {
    return escapeHtml(text).replace(
        /(https?:\/\/[a-z0-9]+\.tci-thaijo\.org\/index\.php\/[^\s<]+\/article\/view\/[\d\/]+)/g,
        '<a href="$1" target="_blank" class="text-indigo-600 underline hover:text-indigo-800 break-all">$1</a>'
    );
}

// T4-A: testDirectApi()
async function testDirectApi() { ... }

// T4-B: testMultiQuery()
async function testMultiQuery() { ... }

// T4-C: testSyncEvidence()
async function testSyncEvidence() { ... }
```

Helper render functions:
- `renderDirectApiResult(data, term, elapsed)` — stats row + article cards
- `renderAgentArticleCard(article, sourceQuery, cacheHit)` — card with `extractBestUrl()`
- `renderMultiQueryTable(queryResults)` — per-query status table
- `renderSyncResult(data)` — stats chips + detail table

---

### Task T5 — Cache Tab URL Linkification

**File**: `static/thaijo_research_ui.html` — JS only (no HTML change)  
**Find**: function that sets `cache-detail-summary` innerHTML (search for `cache-detail-summary`)  
**Change**: wrap set-content call with `linkifySummary()` so every ThaiJO URL in the full summary becomes a clickable `<a>` tag.

**Also**: in the cache table row builder, extract URL from `entry.preview` using the same regex and add a `🔗` icon link button in the Actions column.

---

## Article Card Design (shared by Section A & B)

```
┌─────────────────────────────────────────────────────────┐
│  📄 [title]                          [🟢 CACHE HIT]      │
│  ─────────────────────────────────────────────────────  │
│  👤 [apa_authors] · 📅 [apa_year] · 📰 [apa_journal]   │
│  🔗 [best_url]  → opens article page in new tab         │
│  ─────────────────────────────────────────────────────  │
│  [summary first 300 chars...]  [▼ ดูเพิ่มเติม]          │
│  ─────────────────────────────────────────────────────  │
│  Source: [query badge]                                  │
└─────────────────────────────────────────────────────────┘
```

**`best_url` resolution** (JS helper `extractBestUrl(article)`):
```js
function extractBestUrl(article) {
    // Priority 1: URL embedded in summary text (อ้างอิงจาก: URL)
    const m = (article.summary || '').match(
        /https?:\/\/[a-z0-9]+\.tci-thaijo\.org\/index\.php\/[^\/\s]+\/article\/view\/\d+(?:\/\d+)?/
    );
    if (m) return m[0];
    // Priority 2: pdf_url field (canonical view URL from D02)
    return article.pdf_url || null;
}
```

**URL display**: Show as a truncated link `he05.tci-thaijo.org/.../view/3802/6365` — full URL on hover tooltip.

Key: `title` must NOT be null (D02 fix). If null → show `"[ไม่มีชื่อบทความ]"` in red so it's visible as a regression.

---

## Cache Tab Enhancement (Task T0)

Existing `cache-detail-summary` panel shows raw text. Add URL auto-linking.

**JS function**: `linkifyCacheSummary(text)` — finds all ThaiJO view URLs in the text and wraps them in `<a href="..." target="_blank">` tags. Regex:
```js
/(https?:\/\/[a-z0-9]+\.tci-thaijo\.org\/index\.php\/[^\s\/<>]+\/article\/view\/\d+(?:\/\d+)?)/g
```

**Apply in**: `showCacheDetail(key)` function — after setting `cache-detail-summary` innerHTML, run `linkifyCacheSummary()` on the content.

**Also add per-cache-row**: In the cache table (`#cache-tbody`), if the row's preview text contains a ThaiJO URL, add a small 🔗 button that opens it. Extract the URL from the cache entry `preview` field using the same regex.

---

## Files Changed

| File | Task | Change |
|------|------|--------|
| `src/tools/thaijo.py` | T0 | Remove `_VIEW_EXTRA_SEGMENT_RE` / Case 2; update `THAIJO_URL_PATTERN` to accept `/view/ID/FILEID`; bump cache to v4 |
| `static/thaijo_research_ui.html` | T1 | Update `switchTab()` array |
| `static/thaijo_research_ui.html` | T2 | Add tab button |
| `static/thaijo_research_ui.html` | T3 | Add panel HTML (3 sections) |
| `static/thaijo_research_ui.html` | T4 | Add JS functions + render helpers |
| `static/thaijo_research_ui.html` | T5 | Cache tab URL linkification |

---

## Acceptance Criteria

**T0 — Backend URL fix**
- [ ] `_normalize_to_view_url("https://he05.../view/3802/6365")` returns unchanged (no stripping)
- [ ] `_normalize_to_view_url("https://he01.../download/252647/170884")` still converts to `/view/252647`
- [ ] `_is_valid_thaijo_url("https://he05.../article/view/3802/6365")` returns `True`
- [ ] Cache key is v4; first search after deploy is a miss

**T1–T2 — Tab**
- [ ] "🧪 ทดสอบ Agent" tab button appears in header
- [ ] Clicking tab switches panel; other tabs unaffected

**T3–T4 — Agent Test tab**
- [ ] Section A: "อุบัติเหตุ ปัจจัยเสี่ยง ถนน มุกดาหาร" returns articles with `title` ≠ null, clickable URL
- [ ] Section A: URL shown is from `extractBestUrl()` — uses summary text URL (with file segment) when available
- [ ] Section A: 🟢 CACHE HIT badge when elapsed < 500ms; shows `note` when strict fallback used
- [ ] Section A: raw JSON toggle works
- [ ] Section B: 3 queries execute sequentially; per-query table shows count / time / cache status
- [ ] Section B: deduplication → unique count ≤ sum of individual counts
- [ ] Section B: each article card has source query badge(s)
- [ ] Section C: Sync Evidence button POSTs, shows stats chips; detail table when `detail[]` present
- [ ] null title shows `"[ไม่มีชื่อบทความ]"` in red (regression detector)

**T5 — Cache tab**
- [ ] Cache detail full-summary panel: every ThaiJO URL is a clickable blue underlined link
- [ ] Cache table rows: 🔗 icon in Actions column when URL found in preview
- [ ] Clicking 🔗 opens article in new tab (URL from summary, preserves `/view/3802/6365` form)
