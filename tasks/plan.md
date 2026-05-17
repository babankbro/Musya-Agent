# Implementation Plan: AccidentPolicyAgent — เขตสุขภาพที่ 10

## Overview

A targeted sub-agent system that answers 7 policy questions for Road Traffic Injury (RTI)
in Health Zone 10 (อุบลราชธานี, ศรีสะเกษ, ยโสธร, อำนาจเจริญ, มุกดาหาร).
It produces structured policy reports for สสส./สสจ./ศปถ. directly from the PostgreSQL
star-schema database — no NotebookLM required.

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| 3-agent sequential pipeline (no foundation) | No NLM retrieval needed; all data is in the DB; leaner pipeline = faster output |
| 7 dedicated SQL tools in `zone10_accident.py` | Each tool answers exactly one policy question; avoids prompt over-loading |
| Q3/Q4 use `fact_accident_event` proxy queries | `fact_accident_person` is empty (CSV has no person-level data); severity_level + vehicle_type serve as proxy |
| Separate router + schema from policy_brief | Zone 10 agent has distinct input/output shape; sharing would couple unrelated domains |
| Static HTML UI follows db_explorer_ui.html pattern | Tailwind CDN, IBM Plex Sans Thai, plain JS — consistent with project style |
| All province names must match DB values exactly | `ILIKE %province%` used for fuzzy match safety |

---

## Pipeline Architecture

```
POST /api/accident-policy/zone10
          │
          ▼
Zone10 SQL Data Fetcher (fast LLM)
   runs all 7 zone10_accident tools
   returns formatted text per question
          │
          ▼
Zone10 Policy Analyst (pro LLM)
   interprets data using RTI/Haddon Matrix framework
   maps to 4 policy categories
   produces structured JSON analysis
          │
          ▼
Zone10 Report Writer (pro LLM)
   writes policy brief in Thai government report style
   for สสส./สสจ./ศปถ. audience
   returns Markdown + chart_candidates JSON
          │
          ▼
AccidentPolicyResponse (JSON)
```

---

## The 7 Policy Questions → SQL Tools Mapping

| Q# | Category | Tool | Tables Used |
|----|----------|------|-------------|
| Q1 | Hotspot | `get_zone10_top_roads` | `mart_province_road` |
| Q2 | Hotspot | `get_zone10_time_bands` | `fact_accident_event` + `dim_geography` |
| Q3 | Human Behavior | `get_zone10_motorcycle_severity` | `fact_accident_event` + `dim_geography` (proxy) |
| Q4 | Human Behavior | `get_zone10_car_serious_injuries` | `fact_accident_event` + `dim_geography` (proxy) |
| Q5 | Environment | `get_zone10_environment_risk` | `fact_accident_event` + `dim_geography` |
| Q6 | KPI | `get_zone10_yearly_kpi` | `mart_province_year` |
| Q7 | KPI | `get_zone10_monthly_risk` | `mart_province_year` + `mart_accident_summary` |

---

## Dependency Graph

```
mart_province_road, mart_province_year (existing DB data)
fact_accident_event + dim_geography (existing DB data)
        │
        ├── src/tools/zone10_accident.py     ← Phase 1
        │       (7 SQL tools)
        │
        ├── src/agents/accident_policy_agent.py     ← Phase 2
        │       (3 agents: fetcher, analyst, writer)
        │
        ├── src/agents/accident_policy_orchestrator.py  ← Phase 2
        │       (pipeline runner)
        │
        ├── src/schemas/accident_policy.py   ← Phase 3
        │
        ├── src/routers/accident_policy.py   ← Phase 3
        │       + wired in src/main.py
        │
        └── tests/ + static/accident_policy_ui.html  ← Phase 4
```

---

## Phase 1 — SQL Tools

### Task 1: Zone 10 SQL tools (`src/tools/zone10_accident.py`)

**Description:**
Seven `@tool`-decorated functions for the 7 policy questions.
All accept a comma-separated `provinces` parameter (defaults to all 5 Zone 10 provinces).
Each returns formatted Thai text ready for the analyst agent.

Tool signatures:
```python
ZONE10_PROVINCES = ['อุบลราชธานี', 'ศรีสะเกษ', 'ยโสธร', 'อำนาจเจริญ', 'มุกดาหาร']

get_zone10_top_roads(provinces: str, top_n: int = 10) -> str
get_zone10_time_bands(provinces: str) -> str
get_zone10_motorcycle_severity(provinces: str) -> str   # Q3 proxy
get_zone10_car_serious_injuries(provinces: str) -> str  # Q4 proxy
get_zone10_environment_risk(provinces: str) -> str
get_zone10_yearly_kpi(provinces: str) -> str
get_zone10_monthly_risk(provinces: str) -> str
```

Data note for Q3/Q4: `fact_accident_person` is empty (CSV has no person-level rows).
Q3 uses `fact_accident_event` WHERE `vehicle_type ILIKE '%จักรยานยนต์%'` and reports
severity breakdown. Q4 uses car accidents and `death_count + serious_injured`.
Both tools include a data-limitation note in their output.

**Acceptance criteria:**
- [ ] All 7 tools return non-empty strings when Zone 10 provinces are queried
- [ ] Province filter uses `ILIKE %province%` — matches partial names safely
- [ ] Q3/Q4 tools include explicit data-limitation disclaimer in their output
- [ ] No raw SQL concatenation of user input — all values use `%s` placeholders
- [ ] Each tool handles DB errors gracefully (try/except → Thai error message)

**Verification:**
- [ ] Manually call each tool via `python -c "from src.tools.zone10_accident import ...; print(...('อุบลราชธานี'))"`
- [ ] No tool crashes on real DB

**Dependencies:** None (uses `query_db` from `src.db.pool`)

**Files:**
- `src/tools/zone10_accident.py` (new)

**Estimated scope:** M

---

### Task 2: Zone 10 tool unit tests (`tests/test_zone10_tools.py`)

**Description:**
Unit tests for each SQL tool using the `db_query` pytest fixture (real DB, no mocks).
Each test verifies: return is non-empty string, no exception thrown, key Thai terms present.

**Acceptance criteria:**
- [ ] 7 tests × 1 each = 7 tests minimum
- [ ] Tests use the existing `db_query` fixture from `conftest.py`
- [ ] Each test asserts the return is a `str` with length > 0
- [ ] Q3/Q4 tests assert disclaimer text is present in output

**Verification:**
- [ ] `pytest tests/test_zone10_tools.py -v` all pass

**Dependencies:** Task 1

**Files:**
- `tests/test_zone10_tools.py` (new)

**Estimated scope:** S

---

### Checkpoint 1 — SQL Tools Verified

- [ ] All 7 tools run against real DB without error
- [ ] Tool outputs are readable Thai text with data values
- [ ] Tests pass

---

## Phase 2 — Agent Pipeline

### Task 3: Zone 10 agents (`src/agents/accident_policy_agent.py`)

**Description:**
Define the 3 CrewAI agents for the Zone 10 pipeline.
Pattern follows `policy_rti.py` and `policy_report_writer.py`.

```python
create_zone10_sql_fetcher(llm) -> Agent   # fast tier
create_zone10_policy_analyst(llm) -> Agent  # pro tier
create_zone10_report_writer(llm) -> Agent   # pro tier
```

Agent prompts (Thai):
- **SQL Fetcher**: "ดึงข้อมูลอุบัติเหตุเขตสุขภาพที่ 10 โดยใช้เครื่องมือทั้ง 7 ตัว ..."
- **Policy Analyst**: "วิเคราะห์ข้อมูลด้วยกรอบ Haddon Matrix แยก 4 หมวดนโยบาย ..."
- **Report Writer**: "เขียนรายงานนโยบายสำหรับ สสส./สสจ./ศปถ. ในรูปแบบราชการ ..."

**Acceptance criteria:**
- [ ] 3 factory functions return valid `crewai.Agent` instances
- [ ] SQL Fetcher has all 7 zone10_accident tools assigned
- [ ] All agents use `**agent_retry_kwargs()` for Gemini 429 resilience
- [ ] Analyst prompt includes Haddon Matrix framework and 4-category structure

**Dependencies:** Tasks 1, 2

**Files:**
- `src/agents/accident_policy_agent.py` (new)

**Estimated scope:** S

---

### Task 4: Orchestrator (`src/agents/accident_policy_orchestrator.py`)

**Description:**
Wire the 3 agents into a CrewAI sequential pipeline.
`run_zone10_analysis(provinces, questions, year_range)` → dict matching `AccidentPolicyResponse`.

Pipeline:
1. Task A — SQL Fetcher runs all 7 tools, returns combined text
2. Task B — Policy Analyst receives Task A output, produces structured JSON analysis
3. Task C — Report Writer receives Task B output, writes full markdown report

Uses `kickoff_with_retry` from `agent_defaults.py`.

**Acceptance criteria:**
- [ ] `run_zone10_analysis` returns a dict with keys: `policy_brief`, `sections`, `charts`, `metadata`
- [ ] `sections` contains keys `hotspot`, `human_behavior`, `environment`, `kpi`
- [ ] `elapsed_seconds` is recorded in `metadata`
- [ ] On crew failure, returns error dict (no exception raised to caller)
- [ ] Province list defaults to all 5 Zone 10 provinces if not specified

**Dependencies:** Task 3

**Files:**
- `src/agents/accident_policy_orchestrator.py` (new)

**Estimated scope:** M

---

### Checkpoint 2 — Pipeline Wired

- [ ] `run_zone10_analysis()` completes (may take 2-4 min with LLM)
- [ ] Returns dict with correct shape
- [ ] No uncaught exceptions on error path

---

## Phase 3 — Schema + Router

### Task 5: Pydantic schemas (`src/schemas/accident_policy.py`)

**Description:**
Request and response models for the Zone 10 policy endpoint.

```python
class AccidentPolicyRequest(BaseModel):
    provinces: list[str] = Field(default=ZONE10_PROVINCES)
    questions: list[str] = Field(default=["all"])  # "all" | "Q1"..."Q7"
    year_range: list[int] = Field(default=[2021, 2026])
    format: str = Field(default="markdown")

class AccidentPolicyResponse(BaseModel):
    zone: str = "เขตสุขภาพที่ 10"
    provinces: list[str]
    policy_brief: str
    sections: dict[str, Any]  # {hotspot, human_behavior, environment, kpi}
    charts: list[dict[str, Any]]
    metadata: dict[str, Any]
```

**Acceptance criteria:**
- [ ] `AccidentPolicyRequest` validates province names against ZONE10_PROVINCES list
- [ ] `AccidentPolicyResponse` serialises to JSON without error
- [ ] `year_range` must have exactly 2 elements, first ≤ second

**Dependencies:** None

**Files:**
- `src/schemas/accident_policy.py` (new)

**Estimated scope:** XS

---

### Task 6: FastAPI router + main.py wiring

**Description:**
Two endpoints:
- `POST /api/accident-policy/zone10` → runs full LLM pipeline
- `GET /api/accident-policy/zone10/data` → returns raw SQL data only (no LLM, for testing/UI preview)

Wire router + `/accident-policy` UI route into `src/main.py`.

**Acceptance criteria:**
- [ ] `POST /api/accident-policy/zone10` with default body returns 200 with policy_brief text
- [ ] `GET /api/accident-policy/zone10/data` returns JSON with 7 question results within 5 seconds
- [ ] `GET /accident-policy` returns HTML 200
- [ ] No existing routes broken

**Verification:**
- [ ] `curl -X POST http://localhost:8000/api/accident-policy/zone10 -H 'Content-Type: application/json' -d '{}'` → 200
- [ ] `curl http://localhost:8000/api/accident-policy/zone10/data` → JSON with 7 keys

**Dependencies:** Tasks 4, 5

**Files:**
- `src/routers/accident_policy.py` (new)
- `src/main.py` (modify — add router + UI route)

**Estimated scope:** S

---

### Checkpoint 3 — API Layer Verified

- [ ] `/data` endpoint returns correct JSON within 5s
- [ ] Full pipeline endpoint returns 200 (may be slow due to LLM)
- [ ] Schema validation rejects invalid province names

---

## Phase 4 — Tests + UI

### Task 7: API integration tests (`tests/test_accident_policy_api.py`)

**Description:**
FastAPI `TestClient` tests. Fast tests use `/data` endpoint only (no LLM).
Pipeline test is marked `@pytest.mark.slow` and skipped by default.

Test classes:
- `TestDataEndpoint` — 6 tests for `/zone10/data`
- `TestPolicyRequest` — 4 tests for validation (invalid province, invalid year_range, etc.)
- `TestPipelineSmoke` — 1 smoke test (slow marker, runs full LLM pipeline)

**Acceptance criteria:**
- [ ] 10+ tests total
- [ ] All non-slow tests complete within 30 seconds
- [ ] Validates: province filter works, data keys present, error handling

**Dependencies:** Task 6

**Files:**
- `tests/test_accident_policy_api.py` (new)

**Estimated scope:** S

---

### Task 8: Static UI (`static/accident_policy_ui.html` + `/accident-policy` route)

**Description:**
Single-file HTML UI. Layout:
- **Header**: title + health zone label
- **Left panel**: Province checkboxes (5 provinces, all checked by default), year range inputs, "Preview Data" button (calls `/data`), "Generate Policy Brief" button (calls LLM pipeline)
- **Right panel**: Loading state → tabbed results (4 category tabs), markdown renderer, copy button

Visual style: Tailwind CDN, IBM Plex Sans Thai, indigo accent — matching db_explorer_ui.html.

Data preview mode shows raw SQL results per question in collapsible sections.
Full analysis mode shows formatted markdown + simple bar charts (Chart.js CDN).

**Acceptance criteria:**
- [ ] Page loads at `/accident-policy` within 2 seconds (static HTML)
- [ ] "Preview Data" button fetches `/data` and shows results for all 7 questions
- [ ] Province checkboxes correctly populate the POST body
- [ ] Loading spinner shown during LLM pipeline (can take 2-4 min)
- [ ] Results render markdown (convert `##`/`**` to HTML elements)
- [ ] `escHtml()` used for all user-facing data from API

**Verification:**
- [ ] Open browser at `http://localhost:8000/accident-policy`
- [ ] Click "Preview Data" → see 7 sections of data
- [ ] Uncheck อุบลราชธานี → data excludes that province

**Dependencies:** Tasks 6, 7

**Files:**
- `static/accident_policy_ui.html` (new)
- `src/main.py` (modify — add `/accident-policy` route, done in Task 6)

**Estimated scope:** L

---

### Checkpoint 4 — Feature Complete

- [ ] All non-slow tests pass: `pytest tests/test_accident_policy_api.py -v -m "not slow"`
- [ ] All zone10 tool tests pass: `pytest tests/test_zone10_tools.py -v`
- [ ] Data endpoint returns correct JSON for all 7 questions
- [ ] UI loads and Preview Data works
- [ ] **Human sign-off before considering done**

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `fact_accident_person` empty → Q3/Q4 have no helmet/seatbelt data | High | Use proxy: vehicle_type + severity_level from fact_accident_event; add explicit disclaimer to tool output and report |
| `mart_province_road.road_code VARCHAR(50)` too short for some roads | Medium | Migration 017 already widened to VARCHAR(255); verify in Task 1 |
| LLM pipeline timeout (2-4 min is long for synchronous HTTP) | Medium | `/data` endpoint is the fast path for UI testing; full pipeline uses `run_in_background` fallback |
| Province names in DB may use different spellings | Medium | All tools use `ILIKE %name%` for fuzzy matching; test with all 5 names in Task 2 |
| `mart_province_road` missing `serious_injured` column | Low | That column is in `mart_province_year`; Q1 uses death_count + hotspot_score which exist |
| Gemini 429 rate-limit on long pipelines | Medium | Inherited `kickoff_with_retry` + `_patch_gemini_429_backoff` from `agent_defaults.py` |

---

## Open Questions

- Should `/data` endpoint accept `provinces` query param or only POST body? Plan assumes GET with query params `?provinces=...`.
- Should the UI have a "Download as PDF" button? Deferred — markdown export sufficient for now.
- Should `year_range` filter be applied to all 7 tools? Currently Q1/Q3-Q5 have no year filter (mart tables aggregate all years). Plan is to add `year` filter to Q6/Q7 only.
+