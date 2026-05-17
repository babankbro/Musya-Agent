# Implementation Plan: Document Agent Test UI (`document_agent_test_ui.html`)

## Overview

A single static HTML file at `Agent/static/document_agent_test_ui.html`, served at `/doc-agents`, that lets developers test every tool and API endpoint used by the Shared Foundation document agents (Agents 1–4). Six tabs cover the full document workflow: RAG search, indicator catalog, SQL playground, document library, file upload, and session-based evidence/citation inspection.

**Why this file instead of extending existing UIs:**
- `document_upload_ui.html` uses old CSS (Segoe UI, gradient header) — no Tailwind, no IBM Plex Thai
- `citation_test_ui.html` uses old CSS and covers only citation APIs; no tool-level testing
- This new file uses the **Tailwind + IBM Plex Sans Thai** standard from `test_ui.html` and `unified_test_ui.html`
- Focus is on **agent workflow testing**, not document management

---

## API Endpoints Catalogue

| Endpoint | Method | Tab | Notes |
|----------|--------|-----|-------|
| `/api/test/tool/search_documents` | POST | RAG Search | `{topic, keywords}` → calls `search_documents` tool |
| `/api/test/tool/indicator_catalog` | POST | Indicators | `{topic}` → calls `get_indicator_catalog` |
| `/api/test/query` | POST | SQL | `{sql}` — SELECT/WITH only |
| `/api/documents` | GET | Doc Library | `?topic=&status=&search=&page=&per_page=` |
| `/api/documents/{id}` | GET | Doc Library | Detail + chunk preview |
| `/api/documents/{id}` | PATCH | Doc Library | Update APA metadata |
| `/api/documents/{id}` | DELETE | Doc Library | Delete from registry + MinIO + pgvector |
| `/api/documents/{id}/reingest` | POST | Doc Library | Re-embed chunks |
| `/api/documents/open/{id}` | GET | Doc Library | Stream PDF/DOCX inline |
| `/api/documents/upload` | POST | Upload | multipart → MinIO → register → ingest |
| `/api/documents/analyze-upload` | POST | Upload | multipart → AI APA draft (no DB write) |
| `/api/citations/document/{id}` | GET | Doc Library | APA citation for doc |
| `/api/evidence/session/{id}` | GET | Evidence | All evidence for session |
| `/api/evidence/session/{id}/coverage` | GET | Evidence | Coverage report |
| `/api/citations/session/{id}` | GET | Evidence | APA citations for session |
| `/api/health` | GET | Header badge | System status |

---

## Tab Layout (6 tabs)

| # | Tab Name | Color Theme | Primary Agent | Primary Tool |
|---|----------|-------------|---------------|--------------|
| 1 | RAG Search | Indigo | Agent 2 (Retrieval) | `search_documents` |
| 2 | Indicators | Teal | Agent 2 (Retrieval) | `get_indicator_catalog` |
| 3 | SQL Playground | Amber | Agent 3 (SQL Specialist) | `execute_custom_sql` |
| 4 | Document Library | Purple | Agent 4 (Citation) | `lookup_document_apa` |
| 5 | Upload | Green | Agent 2 (Retrieval) | ingest pipeline |
| 6 | Evidence & Citations | Rose | Agent 4 (Citation) | `register_evidence` |

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Vanilla JS, no bundler | Matches all other UIs; zero build step |
| Tailwind CDN + IBM Plex Sans Thai | Consistent with `test_ui.html`, `unified_test_ui.html` |
| One JS object per tab (`TabRAG`, `TabSQL`, etc.) | Clear ownership, avoids global name collisions |
| `window.location.origin` for API base | Works in any deploy environment |
| No Chart.js needed | Document agents don't return chart specs |
| `marked.js` for snippet rendering | Snippets may contain markdown |
| Pagination state in tab objects | Each tab manages its own list state |
| Confirm dialog before DELETE | Prevents accidental document deletion |

---

## Task List

### Phase 1: Scaffolding

#### Task 1 — HTML shell, tab navigation, health badge

**Description:** Create the file with head (CDN imports), sticky Tailwind header with 6 tab buttons, health badge, 6 hidden panels, and `switchTab()` function. On load: activate Tab 1 (RAG Search), pre-fetch `/api/health` for badge.

**Acceptance criteria:**
- [ ] File exists at `Agent/static/document_agent_test_ui.html`
- [ ] 6 tabs render in sticky header: RAG Search, Indicators, SQL Playground, Document Library, Upload, Evidence & Citations
- [ ] `switchTab(name)` hides all panels, shows matching panel, highlights active tab button
- [ ] Health badge reads `/api/health` and shows green/yellow/red pill on load
- [ ] Tailwind CSS CDN, IBM Plex Sans Thai, marked.js all loaded (no Chart.js — not needed)
- [ ] `API = window.location.origin` constant declared
- [ ] Shared utilities: `escapeHtml()`, `fmtBytes()`, `fmtDate()`, `statusBadge(status)`, `topicBadge(topic)`

**Verification:**
- [ ] Open file in browser → 6 tabs visible, each click switches panel
- [ ] No console errors on load

**Dependencies:** None

**Files touched:** `Agent/static/document_agent_test_ui.html` (new)

**Estimated scope:** S

---

### Checkpoint: Phase 1

- [ ] File opens in browser without errors
- [ ] All 6 tabs navigate cleanly
- [ ] Health badge shows a status

---

### Phase 2: Tool-Testing Tabs

#### Task 2 — RAG Search tab

**Description:** Panel to test the `search_documents` tool via `/api/test/tool/search_documents`. Shows results as result cards with distance score, APA citation, text snippet, and PDF link.

**Acceptance criteria:**
- [ ] Keyword input + topic dropdown (all / accident / mental_health / nutrition)
- [ ] `n_results` number input (1–20, default 5)
- [ ] "Search" button → `POST /api/test/tool/search_documents` `{topic, keywords, n_results}`
- [ ] Results rendered as cards (one per evidence item):
  - Title + document_id badge
  - `distance` shown as relevance bar (0=perfect → green, 1=poor → red) — `(1 - distance) * 100%`
  - `text_snippet` (first 300 chars, monospace or small prose)
  - `bibliography_text` (APA citation, italic)
  - `[PDF]` button → opens `/api/documents/open/{document_id}` in new tab (if `document_id` present)
  - Topic badge + trust_level badge
- [ ] Empty state: "ไม่พบเอกสาร — ลองเปลี่ยน keywords" shown when results = 0
- [ ] Loading state (3-dot pulse) while request in flight
- [ ] Quick queries:
  - `"อุบัติเหตุ ปัจจัยเสี่ยง"` (accident)
  - `"สุขภาพจิต ผู้สูงอายุ"` (mental_health)
  - `"โภชนาการ เด็ก"` (nutrition)
  - `"แผนปฏิบัติการ ความปลอดภัยทางถนน"` (all)

**Verification:**
- [ ] Search with keyword "อุบัติเหตุ" → result cards appear
- [ ] Distance bar shows meaningful relative width
- [ ] PDF button opens file in new tab (if document exists in DB)

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** M

---

#### Task 3 — Indicator Catalog tab

**Description:** Panel to browse health indicators by topic via `/api/test/tool/indicator_catalog`. Displays indicators in a clean table.

**Acceptance criteria:**
- [ ] Topic button group (accident / mental_health / nutrition) — clicking immediately loads
- [ ] Table: `indicator_code` | `indicator_name` | `unit_name` | `preferred_chart` | definition (truncated)
- [ ] Row click → expands inline detail row showing full definition
- [ ] Loading state while fetching
- [ ] Empty state when no indicators found for topic
- [ ] Result count shown: "พบ N ตัวชี้วัด"

**Verification:**
- [ ] Click "accident" → indicator table loads
- [ ] Row click expands/collapses definition

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** S

---

#### Task 4 — SQL Playground tab

**Description:** Read-only SQL playground via `/api/test/query`. Also shows table schema via a schema inspector panel.

**Acceptance criteria:**
- [ ] SQL textarea (monospace, 6 rows, resizable)
- [ ] "Execute" button → `POST /api/test/query {sql}`
- [ ] Server rejects non-SELECT/WITH queries → show error message in UI
- [ ] Results displayed as scrollable table (columns auto-sized, max-height)
- [ ] Row count shown: "N แถว"
- [ ] "JSON" toggle → shows raw JSON result below table
- [ ] Schema inspector sidebar:
  - Dropdown of common tables: `mart_accident_summary`, `dim_geography`, `document_registry`, `document_embeddings`, `evidence_registry`, `indicator_catalog`
  - "Describe" button → runs `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '...'`
  - Shows schema as compact table
- [ ] Quick queries (pill buttons):
  - `SELECT COUNT(*) FROM mart_accident_summary`
  - `SELECT * FROM document_registry LIMIT 10`
  - `SELECT * FROM indicator_catalog WHERE topic = 'accident'`
  - `SELECT source, COUNT(*) as chunks FROM document_embeddings GROUP BY source ORDER BY chunks DESC LIMIT 15`
  - `SELECT * FROM evidence_registry ORDER BY created_at DESC LIMIT 10`

**Verification:**
- [ ] Run `SELECT 1` → returns 1 row
- [ ] Run `DELETE FROM document_registry` → returns error (blocked)
- [ ] Schema inspector shows columns for `document_registry`

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** M

---

### Checkpoint: Phase 2

- [ ] All 3 tool tabs (RAG, Indicators, SQL) return data without errors
- [ ] No console errors when results are empty
- [ ] Quick queries all reachable

---

### Phase 3: Document Management Tabs

#### Task 5 — Document Library tab

**Description:** Browse, inspect, and manage documents in `document_registry`. This is a **Tailwind-restyled** subset of what `document_upload_ui.html` already does — designed for agent workflow context (focus on chunk count, embedding status, APA citation verification).

**Acceptance criteria:**
- [ ] Filter bar: topic dropdown + status dropdown (completed/failed/pending) + text search input + "Filter" button
- [ ] Paginated table (20 per page): document_id | title | topic badge | status badge | chunk_count | pages | uploaded_at
- [ ] Row click → slide-open detail panel below row showing:
  - Full APA citation text (formatted, copyable)
  - APA fields (authors, year, publisher, type, DOI)
  - Chunk preview (first 5 chunks: index, page_ref, section_label, 200-char snippet)
  - `[PDF]` button (opens `/api/documents/open/{id}`)
- [ ] Row actions: `[Reingest]` (confirm → `POST /{id}/reingest`) | `[Delete]` (confirm dialog → `DELETE /{id}`)
- [ ] Reingest and Delete update the row in place after completion
- [ ] Pagination: prev/next buttons + page indicator "หน้า X / Y"
- [ ] Status badges: completed=green, failed=red, pending=yellow, processing=blue

**Verification:**
- [ ] Table loads on tab activation
- [ ] Filter by topic "accident" → only accident docs shown
- [ ] Click row → detail panel expands
- [ ] Delete action shows confirm then removes row

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** L → split: Task 5a (table + filters + pagination) and Task 5b (row detail + actions)

---

#### Task 5a — Document Library: table, filters, pagination

**Acceptance criteria:**
- [ ] `GET /api/documents?topic=&status=&search=&page=&per_page=20` on load and on filter change
- [ ] Table renders `document_id`, `title`, `topic` badge, `status` badge, `chunk_count`, `total_pages`, `uploaded_at`
- [ ] Pagination with prev/next, page X of Y
- [ ] Clicking a row calls `GET /api/documents/{id}` for detail

**Dependencies:** Task 1

**Estimated scope:** M

---

#### Task 5b — Document Library: row detail, reingest, delete

**Acceptance criteria:**
- [ ] Clicking a row expands inline detail below it (slides open, closes on second click)
- [ ] Detail shows: APA citation block, APA fields grid, chunk preview table, [PDF] link
- [ ] `[Reingest]` button → confirm → `POST /api/documents/{id}/reingest` → update chunk_count in row
- [ ] `[Delete]` button → confirm dialog "ลบเอกสาร '{title}'?" → `DELETE /api/documents/{id}` → remove row

**Dependencies:** Task 5a

**Estimated scope:** M

---

#### Task 6 — Upload tab

**Description:** Two-step document upload: (1) drag-and-drop file → AI APA draft analysis, (2) review/edit APA form → submit to upload endpoint. Uses the established Tailwind style.

**Acceptance criteria:**
- [ ] Drop zone: accepts .pdf, .docx, .txt, .md (max 50 MB)
- [ ] On file drop/select → `POST /api/documents/analyze-upload` (multipart) → populate APA form fields from draft
- [ ] Shows confidence badge ("high/medium/low") and AI reasoning text from response
- [ ] APA form fields (pre-filled from draft, user-editable):
  - Title, topic dropdown, apa_type dropdown
  - apa_authors, apa_year, apa_publisher, apa_doi, apa_url
- [ ] "Upload & Ingest" button → `POST /api/documents/upload` (multipart/form-data with all APA fields)
- [ ] Progress indicator during upload (indeterminate spinner)
- [ ] Success state: shows document_id, chunk count, APA citation preview, [PDF] link
- [ ] Error state: shows error message with retry
- [ ] "Reset" button clears form for new file

**Note:** `/api/documents/upload` does upload-to-MinIO + register + ingest in one step. `/api/documents/analyze-upload` is only for the AI APA draft — it does NOT persist. The final `upload` call reads the same file bytes again.

**Verification:**
- [ ] Drop a PDF → APA fields populate from AI draft
- [ ] Submit → success card shows with chunk count
- [ ] Drop an unsupported file type → error message before analysis

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** M

---

#### Task 7 — Evidence & Citations tab

**Description:** Inspect evidence and APA citations for a specific chat session. Lets developers verify that Agent 4 (Citation & Evidence) is correctly registering evidence and generating citations.

**Acceptance criteria:**
- [ ] Session ID text input + "Load" button
- [ ] On load, three sections rendered:
  1. **Evidence items** (`GET /api/evidence/session/{id}`):
     - Each item: evidence_type badge (document/database), citation_code, source_ref, text_snippet (first 200 chars), trust_level badge
  2. **Coverage report** (`GET /api/evidence/session/{id}/coverage`):
     - Total claims, supported/partial/insufficient counts
     - Visual coverage bar (supported / total)
     - Claims list: claim_text + support_level badge
  3. **APA Citations** (`GET /api/citations/session/{id}`):
     - Each citation: citation_code badge, inline_text, reference_text (APA formatted), source link button
- [ ] Empty state: "ไม่พบ evidence สำหรับ session นี้"
- [ ] Session ID auto-filled from URL hash if present (`window.location.hash = '#session=xxx'`)
- [ ] "Copy Session ID" button

**Verification:**
- [ ] Enter a valid session ID → evidence + coverage + citations render
- [ ] Enter an invalid session ID → empty state shown without error

**Dependencies:** Task 1

**Files touched:** `Agent/static/document_agent_test_ui.html`

**Estimated scope:** M

---

### Checkpoint: Phase 3

- [ ] Document Library shows list and detail
- [ ] Upload flow works end-to-end (analyze → edit → upload)
- [ ] Evidence tab shows session data
- [ ] No JS errors when sessions are empty

---

### Phase 4: Route Registration

#### Task 8 — Register `/doc-agents` route in `main.py`

**Description:** Add a `GET /doc-agents` route in `Agent/src/main.py` that serves the HTML file, following the same pattern as `/test` and `/documents`.

**Acceptance criteria:**
- [ ] `GET /doc-agents` returns `HTMLResponse` from `static/document_agent_test_ui.html`
- [ ] `root()` endpoint response dict includes `"doc_agents": "/doc-agents"`

**Verification:**
- [ ] `curl http://localhost:8000/doc-agents` → returns HTML 200

**Dependencies:** Task 1

**Files touched:** `Agent/src/main.py`

**Estimated scope:** XS

---

### Final Checkpoint

- [ ] All 6 tabs functional without console errors
- [ ] Health badge shows system status
- [ ] RAG search returns results for "อุบัติเหตุ"
- [ ] SQL playground rejects non-SELECT queries
- [ ] Document Library loads paginated list
- [ ] Upload flow completes end-to-end
- [ ] Evidence tab shows empty state gracefully
- [ ] `/doc-agents` route serves the file

---

## JavaScript Module Layout

```javascript
'use strict';
const API = window.location.origin;

// ─── Shared Utilities ──────────────────────────────────────────
function escapeHtml(s) { ... }
function fmtBytes(n) { ... }        // "2.3 MB"
function fmtDate(s) { ... }         // "18 เม.ย. 2567"
function statusBadge(s) { ... }     // returns HTML span with color
function topicBadge(t) { ... }      // returns HTML span with color
function trustedBadge(t) { ... }    // high/medium/low
function apiBadge(pipeline) { ... } // not needed here

// ─── Tab Navigation ────────────────────────────────────────────
const TABS = ['rag','indicators','sql','library','upload','evidence'];
function switchTab(name) { ... }

// ─── Health Badge ──────────────────────────────────────────────
async function checkHealth() { ... }

// ─── Tab: RAG Search ──────────────────────────────────────────
const TabRAG = {
  async search() { ... },
  renderResults(items) { ... },
  relevanceBar(distance) { ... },
};

// ─── Tab: Indicator Catalog ───────────────────────────────────
const TabIndicators = {
  async load(topic) { ... },
  renderTable(lines) { ... },
};

// ─── Tab: SQL Playground ──────────────────────────────────────
const TabSQL = {
  async execute() { ... },
  async describeTable(name) { ... },
  renderTable(rows) { ... },
};

// ─── Tab: Document Library ────────────────────────────────────
const TabLibrary = {
  page: 1,
  filters: { topic: '', status: '', search: '' },
  expandedId: null,
  async load() { ... },
  renderList(docs, total) { ... },
  async loadDetail(id) { ... },
  renderDetail(doc) { ... },
  async reingest(id) { ... },
  async deleteDoc(id, title) { ... },
};

// ─── Tab: Upload ──────────────────────────────────────────────
const TabUpload = {
  pendingFile: null,
  pendingBytes: null,
  async analyze(file) { ... },
  renderDraft(draft) { ... },
  async upload() { ... },
  reset() { ... },
};

// ─── Tab: Evidence & Citations ────────────────────────────────
const TabEvidence = {
  async load(sessionId) { ... },
  renderEvidence(items) { ... },
  renderCoverage(coverage) { ... },
  renderCitations(citations) { ... },
};

// ─── Init ─────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  switchTab('rag');
  checkHealth();
  // Auto-load session from URL hash
  const hash = window.location.hash;
  const m = hash.match(/session=([^&]+)/);
  if (m) {
    document.getElementById('evidence-session-input').value = m[1];
    // Don't auto-load — require explicit "Load" click
  }
});
```

---

## Quick Test Scenarios

### RAG Search tab
| Keyword | Topic | Expected |
|---------|-------|----------|
| `"อุบัติเหตุ ปัจจัยเสี่ยง"` | accident | Results from accident docs |
| `"สุขภาพจิต ผู้สูงอายุ"` | mental_health | Results from mental health docs |
| `"โภชนาการ เด็ก"` | nutrition | Results from nutrition docs |
| `"แผนปฏิบัติการ ความปลอดภัย"` | all | Docs from any topic |

### SQL Playground tab
| Query | Expected |
|-------|----------|
| `SELECT COUNT(*) FROM mart_accident_summary` | Row count |
| `SELECT * FROM document_registry LIMIT 5` | 5 doc rows |
| `SELECT * FROM indicator_catalog WHERE topic = 'accident'` | Indicator list |
| `DROP TABLE document_registry` | Error: blocked |
| `SELECT source, COUNT(*) as n FROM document_embeddings GROUP BY source ORDER BY n DESC LIMIT 10` | Chunk counts per doc |

### Indicators tab
| Topic | Expected |
|-------|----------|
| accident | ≥1 indicator with code RTI-xx |
| mental_health | ≥1 indicator with code MH-xx |
| nutrition | ≥1 indicator |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `/api/test/tool/search_documents` response field `n_results` may not be forwarded | Med | Test endpoint body; check `ToolRequest` schema in `test_ui.py` |
| APA draft from `analyze-upload` doesn't persist file — `upload` re-reads it | High | Store `File` object in `TabUpload.pendingFile`; submit same file in `upload()` call |
| `document_embeddings` table name may differ | Low | Use `explain_schema` quick query to verify before testing |
| `evidence_registry` table may be empty in dev | Low | Show graceful empty state, don't treat as error |
| Confirm dialogs are blocking (window.confirm) | Low | Acceptable for dev tool; no need for custom modal |

---

## Open Questions

1. Does `POST /api/test/tool/search_documents` accept a `n_results` field, or is it always 5? Check `ToolRequest` schema in `test_ui.py`.
2. Does `indicator_catalog` table exist in dev DB? Query `SELECT COUNT(*) FROM indicator_catalog` first.
3. Is `evidence_registry.text_snippet` the right field, or is it `text_extract`? Check schema.
