# Implementation Plan: Unified Test UI (`unified_test_ui.html`)

## Overview

A single static HTML file that tests all 3 Musya Agent pipelines (Chat, Policy Brief, Short Chat) through the unified endpoint. Built as a 5-tab vanilla-JS application following the exact conventions of `test_ui.html` (Tailwind CSS CDN, IBM Plex Sans Thai, Chart.js 4.4.2, marked.js). No bundler, no build step — drop-in static file served by the existing FastAPI backend.

The new file intentionally consolidates what 4 separate test UIs do today, so developers can test routing decisions, full pipeline responses, streaming, and system health in one place.

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Vanilla JS, no bundler | Matches all existing UIs; zero build dependency |
| Single file | Served as static file; no routing needed |
| `window.location.origin` for API base | Avoids hardcoded localhost; works in any deploy env |
| Tailwind CDN + IBM Plex Sans Thai | Consistent with `test_ui.html` |
| Chart.js 4.4.2 | Same version as other UIs; avoids API drift |
| marked.js CDN | Shared markdown renderer |
| Module pattern: named JS objects | E.g. `TabChat`, `TabRouter`, `TabSSE` — keeps file navigable |
| Routing color coding | chat=purple, policy_brief=teal, short_chat=orange |
| Pipeline-aware response rendering | Each pipeline result type gets its own render function |

---

## Task List

### Phase 1: Scaffolding

#### Task 1 — HTML shell + tab navigation

**Description:** Create the HTML file with head (CSS/JS imports), sticky header with health badge, 5 tab buttons, 5 panel `div`s (hidden by default), and the `switchTab()` JS function.

**Acceptance criteria:**
- [ ] File exists at `Agent/static/unified_test_ui.html`
- [ ] 5 tabs: Unified Chat, Short Chat, Router, SSE Stream, Health
- [ ] Active tab panel is visible; others have `display:none`
- [ ] Health badge starts as "Checking..." and changes to green/yellow/red after health fetch
- [ ] Tailwind, marked.js, Chart.js 4.4.2, IBM Plex Sans Thai all loaded
- [ ] `switchTab(name)` highlights active tab button and shows correct panel

**Verification:**
- [ ] Open in browser → 5 tabs visible, clicking switches panels
- [ ] No console errors on load

**Dependencies:** None

**Files touched:** `Agent/static/unified_test_ui.html` (new)

**Estimated scope:** S

---

#### Task 2 — Shared utilities module

**Description:** Inline JS utility block with functions used across all tabs: `apiBase()`, `toNumeric(v)`, `markdownToHtml(md)`, `renderCitations(citations)`, `buildChart(canvasId, spec)`, `fmtSeconds(s)`, `showStatus(el, msg, type)`.

**Acceptance criteria:**
- [ ] `apiBase()` returns `window.location.origin`
- [ ] `toNumeric(v)` converts string numbers, handles commas, returns `NaN` on failure
- [ ] `markdownToHtml(md)` returns `marked.parse(md)` with sanitized fallback
- [ ] `renderCitations(citations)` produces collapsible `<details>` with `[C-xxx]` badges
- [ ] `buildChart(canvasId, spec)` wraps Chart.js; uses `PALETTE` constant matching `test_ui.html`
- [ ] `fmtSeconds(s)` returns `"1.2s"` format
- [ ] `showStatus(el, msg, type)` sets text + color class (type: info/success/error/warning)

**Verification:**
- [ ] `toNumeric("1,234.5")` returns `1234.5`
- [ ] `renderCitations([])` returns empty string without error

**Dependencies:** Task 1

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** S

---

### Phase 2: Core Tabs

#### Task 3 — Health tab

**Description:** Panel that calls `GET /api/health` on load and on-demand. Shows system status fields (version, database, rag, llm, thaijo) as a grid of status pills. Each field has green/yellow/red indicator matching the badge in the header.

**Acceptance criteria:**
- [ ] Health tab fetches `/api/health` on tab activation if not already fetched
- [ ] Shows: version, status, database, rag, llm, thaijo availability
- [ ] Each field rendered as colored pill (green=ok, yellow=degraded, red=error)
- [ ] "Refresh" button re-fetches and updates display
- [ ] Elapsed time shown (time to receive health response)
- [ ] Header health badge updates to match overall status

**Verification:**
- [ ] Click Health tab → status grid appears within 2s
- [ ] Refresh button triggers new fetch and updates display

**Dependencies:** Task 2

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** S

---

#### Task 4 — Router tab

**Description:** Panel that tests routing decision in isolation. Input → `POST /api/chat/unified` with a flag to inspect the `routing` field only (the full response is parsed but only routing metadata is displayed). Color-coded result panel with `pipeline_used`, `confidence`, `reason`, `extracted_params`.

**Acceptance criteria:**
- [ ] Text input + "Test Routing" button
- [ ] Calls `POST /api/chat/unified` with `{"message": ...}`
- [ ] Displays `routing.pipeline_used` with color badge: chat=purple, policy_brief=teal, short_chat=orange
- [ ] Displays `routing.confidence` as percentage bar
- [ ] Displays `routing.reason` as text
- [ ] Displays `routing.extracted_params` as formatted JSON block
- [ ] Quick test buttons covering all 3 routing cases (one per pipeline)
- [ ] Loading state while waiting

**Quick test messages (one per routing case):**
- Chat: `"สรุปสถานการณ์อุบัติเหตุปี 2567"` → expects `chat_pipeline`
- Policy Brief: `"สร้างรายงานตรวจราชการ จ.เชียงใหม่ ปี 2567"` → expects `policy_brief_pipeline`
- Short Chat: `"คำถามสั้น: อัตราการเสียชีวิตต่อแสนประชากร"` → expects `short_chat`

**Verification:**
- [ ] Each quick test button populates input and submits
- [ ] Color badge changes per pipeline
- [ ] Confidence bar shows correct percentage

**Dependencies:** Task 2

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** M

---

#### Task 5 — Short Chat tab

**Description:** Chat-style panel using `POST /api/chat/short`. Simpler than Unified Chat: no charts, no citation collapsible (just inline ref count), shows disclaimer banner about short mode.

**Acceptance criteria:**
- [ ] Chat bubble UI identical to `test_ui.html` (user=purple right, assistant=white left)
- [ ] Calls `POST /api/chat/short` with `{"message": ...}`
- [ ] Shows orange "Short Chat" disclaimer banner below header
- [ ] Response rendered with `markdownToHtml()`
- [ ] Metadata bar: elapsed_seconds, pipeline=short_chat (orange badge)
- [ ] Shows citation count if present (e.g. "3 แหล่งอ้างอิง")
- [ ] No Chart.js rendering (short mode doesn't return charts)
- [ ] Quick questions: 3 short factual questions
- [ ] Loading dots during wait
- [ ] "ล้างแชท" (clear chat) button

**Verification:**
- [ ] Send message → response appears as chat bubble
- [ ] Disclaimer banner visible
- [ ] No JS errors when response has no citations

**Dependencies:** Task 2

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** M

---

#### Task 6 — Unified Chat tab

**Description:** Main chat panel. Calls `POST /api/chat/unified`. Renders response based on `pipeline_used` field. Supports charts, collapsible citations, metadata bar, and per-pipeline color theming.

**Acceptance criteria:**
- [ ] Chat bubble UI matching `test_ui.html`
- [ ] Pipeline badge shown in assistant bubble header: chat=purple, policy=teal
- [ ] Metadata bar: elapsed_seconds, pipeline_used, routing_confidence (%), citation_count
- [ ] Response text rendered with `markdownToHtml()`
- [ ] Chart rendering: if response has `chart_spec` → render with `buildChart()`
- [ ] Citations: collapsible `<details>` block with `[C-xxx]` badges per citation
- [ ] Reference list at bottom of bubble (collapsed by default)
- [ ] Quick questions: 6 questions covering chat, policy brief, and mixed cases
- [ ] Loading dots during wait
- [ ] Routing decision mini-panel below each response showing pipeline+confidence
- [ ] "ล้างแชท" button

**Quick questions:**
- `"สรุปสถานการณ์อุบัติเหตุปี 2567"` (chat)
- `"จุดเสี่ยงอุบัติเหตุ 10 อันดับแรก จ.ขอนแก่น"` (chat)
- `"วิเคราะห์แนวโน้มอุบัติเหตุรายปี 2563-2567"` (chat + chart)
- `"สร้างรายงานตรวจราชการ จ.เชียงใหม่ ปี 2567"` (policy brief)
- `"งานวิจัยอุบัติเหตุทางถนน ปัจจัยเสี่ยง"` (chat + ThaiJO academic)
- `"เปรียบเทียบ 5 จังหวัดที่มีอัตราเสียชีวิตสูงสุด"` (chat + chart)

**Verification:**
- [ ] Response bubble shows correct pipeline badge color
- [ ] Metadata bar populated after response
- [ ] Citations collapsible expands/collapses without error
- [ ] Chart renders if spec present

**Dependencies:** Tasks 2, 4

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** L → split: Task 6a (bubble+metadata), Task 6b (charts+citations)

---

#### Task 6a — Unified Chat: bubble, input, metadata bar

**Description:** Core chat interaction for the Unified Chat tab. Focus on message send, bubble rendering, metadata bar. No charts or citations yet.

**Acceptance criteria:**
- [ ] Input form + send button
- [ ] User bubble: purple, right-aligned, with timestamp
- [ ] Assistant bubble: white card, left-aligned, pipeline badge in header
- [ ] Metadata bar shows: elapsed, pipeline_used (colored badge), confidence%, citation_count
- [ ] Loading dots during wait
- [ ] Quick questions pill buttons
- [ ] Clear chat button

**Dependencies:** Task 2

**Estimated scope:** M

---

#### Task 6b — Unified Chat: charts + citations

**Description:** Extend the assistant bubble from Task 6a with chart rendering and citation display.

**Acceptance criteria:**
- [ ] If `response.chart_spec` present → render Chart.js inside bubble
- [ ] Chart uses `PALETTE` constant, `toNumeric()` for data normalization
- [ ] Citations section: collapsible `<details>` block
- [ ] Each citation: `[C-xxx]` badge + `bibliography_text` + clickable `pdf_url` if present
- [ ] Reference list section inside collapsible

**Dependencies:** Task 6a

**Estimated scope:** M

---

### Phase 3: SSE Streaming Tab

#### Task 7 — SSE Stream tab

**Description:** Panel that sends `POST /api/chat/stream` and displays real-time agent events as they arrive (SSE). Shows a dark terminal-style log panel and accumulates the final response.

**Acceptance criteria:**
- [ ] Text input + "Stream" button
- [ ] Opens SSE connection to `POST /api/chat/stream` (using `EventSource` or `fetch` + ReadableStream)
- [ ] Dark terminal panel (`bg-[#0f172a]`, monospace, 320px height, scroll-to-bottom)
- [ ] Each event type displayed with color:
  - `agent_start` → cyan
  - `tool_call` → yellow
  - `tool_result` → green
  - `agent_complete` → green bold
  - `error` → red
  - `progress` → gray
- [ ] Final response rendered below terminal when stream ends
- [ ] "Stop" button aborts stream mid-flight
- [ ] Quick questions: 2 messages that exercise multi-agent flow

**Note on SSE with POST:** `EventSource` only supports GET. Use `fetch()` with `ReadableStream` + `TextDecoder` to parse `data: ...\n\n` lines from a POST body.

**Acceptance criteria (implementation detail):**
- [ ] `fetch(url, {method:'POST', body: JSON.stringify(...)})` with streaming reader
- [ ] Lines parsed: split on `\n`, filter `data:` prefix, `JSON.parse` each event
- [ ] Stream ends on `event: done` or fetch stream closes

**Verification:**
- [ ] Send message → events appear in terminal one by one
- [ ] Final response appears below terminal
- [ ] Stop button halts new events

**Dependencies:** Task 2

**Files touched:** `Agent/static/unified_test_ui.html`

**Estimated scope:** M

---

### Checkpoint: After All Tasks

- [ ] All 5 tabs render without JS console errors
- [ ] Health tab shows system status
- [ ] Router tab color-codes pipeline correctly
- [ ] Short Chat returns response with orange disclaimer
- [ ] Unified Chat renders markdown, charts (if present), citations (if present)
- [ ] SSE tab shows streaming events in terminal
- [ ] File is self-contained — no external backend changes needed

---

## JavaScript Module Layout

```javascript
// ─── Constants ───────────────────────────────────────────
const PALETTE = ['#6366f1','#f59e0b','#10b981','#ef4444','#3b82f6','#ec4899','#8b5cf6','#06b6d4'];
const PIPELINE_COLORS = {
  chat_pipeline:         { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-200' },
  policy_brief_pipeline: { bg: 'bg-teal-100',   text: 'text-teal-700',   border: 'border-teal-200'   },
  short_chat:            { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-200' },
};

// ─── Shared Utilities ─────────────────────────────────────
function apiBase() { return window.location.origin; }
function toNumeric(v) { ... }
function markdownToHtml(md) { ... }
function buildChart(canvasId, spec) { ... }
function renderCitations(citations) { ... }
function renderMetaBar(data) { ... }  // elapsed, pipeline badge, confidence, count
function showStatus(el, msg, type) { ... }
function fmtSeconds(s) { ... }

// ─── Tab Navigation ───────────────────────────────────────
function switchTab(name) { ... }

// ─── Health Tab ───────────────────────────────────────────
const TabHealth = {
  fetched: false,
  async load() { ... },
  render(data) { ... },
};

// ─── Router Tab ───────────────────────────────────────────
const TabRouter = {
  async testRouting(message) { ... },
  renderResult(data) { ... },
  pipelineBadge(pipeline) { ... },
};

// ─── Short Chat Tab ───────────────────────────────────────
const TabShort = {
  history: [],
  async send(message) { ... },
  appendBubble(role, html, meta) { ... },
  clear() { ... },
};

// ─── Unified Chat Tab ─────────────────────────────────────
const TabUnified = {
  history: [],
  chartInstances: {},
  async send(message) { ... },
  appendUserBubble(message) { ... },
  appendAssistantBubble(data) { ... },
  renderChart(bubble, chartSpec) { ... },
  renderCitationsBlock(bubble, citations) { ... },
  clear() { ... },
};

// ─── SSE Stream Tab ───────────────────────────────────────
const TabSSE = {
  controller: null,
  async startStream(message) { ... },
  stop() { ... },
  logEvent(event) { ... },
  renderFinal(data) { ... },
};

// ─── Init ─────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  switchTab('unified');
  TabHealth.load();  // pre-fetch health for badge
});
```

---

## Rendering Logic Per Pipeline Type

### `chat_pipeline` response
```
{
  "answer": "...",           // markdown text
  "pipeline_used": "chat_pipeline",
  "routing": { "confidence": 0.92, "reason": "..." },
  "chart_spec": { ... },     // optional Chart.js spec
  "citations": [...],        // optional array
  "elapsed_seconds": 8.2
}
```
Render: purple badge, markdown answer, chart if present, citations collapsible.

### `policy_brief_pipeline` response
```
{
  "report": "...",           // long markdown policy report
  "pipeline_used": "policy_brief_pipeline",
  "routing": { ... },
  "citations": [...],
  "elapsed_seconds": 45.0
}
```
Render: teal badge, markdown report (longer), citations collapsible, no chart.

### `short_chat` response
```
{
  "answer": "...",
  "pipeline_used": "short_chat",
  "elapsed_seconds": 3.1
}
```
Render: orange badge, markdown answer, no chart, citation count only.

---

## Routing Test Scenarios

| Tab | Message | Expected Pipeline | Notes |
|-----|---------|-------------------|-------|
| Router | `"สรุปสถานการณ์อุบัติเหตุปี 2567"` | `chat_pipeline` | General chat |
| Router | `"สร้างรายงานตรวจราชการ จ.เชียงใหม่"` | `policy_brief_pipeline` | Policy brief trigger |
| Router | `"อัตราการเสียชีวิตต่อแสนประชากร"` | `short_chat` | Short factual query |
| Unified | `"งานวิจัยอุบัติเหตุทางถนน ปัจจัยเสี่ยง"` | `chat_pipeline` | ThaiJO academic search |
| Unified | `"แนวโน้มอุบัติเหตุรายปี 2563-2567"` | `chat_pipeline` | Chart expected |
| SSE | `"สรุปอุบัติเหตุ จ.อุบลราชธานี"` | `chat_pipeline` | Multi-agent stream |

---

## API Endpoints

| Method | URL | Used By |
|--------|-----|---------|
| `POST` | `/api/chat/unified` | Unified Chat, Router |
| `POST` | `/api/chat/short` | Short Chat |
| `POST` | `/api/chat/stream` | SSE Stream |
| `GET` | `/api/health` | Health tab, header badge |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `/api/chat/stream` may use GET not POST | High | Read actual route definition before Task 7 |
| `routing` field may not exist on all responses | Med | Optional chaining `data?.routing?.confidence` everywhere |
| Chart spec schema varies | Med | Wrap `buildChart` with try/catch, show raw JSON on error |
| Policy report too long for bubble | Low | `max-h-96 overflow-y-auto` scroll on bubble |
| SSE POST via fetch — ReadableStream API support | Med | Tested in Chrome 120+; add note to comments |

---

## Open Questions

- Does `POST /api/chat/stream` actually exist? Check `Agent/src/api/` before Task 7.
- What exact fields does the unified endpoint return for policy_brief vs chat? Read response schema before Task 6.
- Does `/api/health` return `thaijo` availability or just db/rag/llm?
