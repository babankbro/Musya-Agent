# Task List — AccidentPolicyAgent (เขตสุขภาพที่ 10)

## Phase 1 — SQL Tools

- [x] **Task 1** · `src/tools/zone10_accident.py` — 7 SQL tools for Zone 10 policy questions
  - Tools: get_zone10_top_roads, get_zone10_time_bands, get_zone10_motorcycle_severity,
    get_zone10_car_serious_injuries, get_zone10_environment_risk, get_zone10_yearly_kpi, get_zone10_monthly_risk
  - Q3/Q4 proxy queries (fact_accident_person empty) with data-limitation disclaimer
  - Size: M

- [x] **Task 2** · `tests/test_zone10_tools.py` — unit tests for all 7 SQL tools
  - Uses `db_query` fixture (real DB, no mocks)
  - 7+ tests, verify non-empty string output and no exceptions
  - Size: S
  - Depends on: Task 1

### ✅ Checkpoint 1 — PASSED
- [x] All 7 tools run against real DB without error
- [x] Tests pass: 28/28 `pytest tests/test_zone10_tools.py -v`

## Phase 2 — Agent Pipeline

- [x] **Task 3** · `src/agents/accident_policy_agent.py` — 3 CrewAI agent factories
  - create_zone10_sql_fetcher (fast LLM, all 7 tools)
  - create_zone10_policy_analyst (pro LLM, Haddon Matrix framework)
  - create_zone10_report_writer (pro LLM, สสส./สสจ./ศปถ. report style)
  - Size: S
  - Depends on: Task 1

- [x] **Task 4** · `src/agents/accident_policy_orchestrator.py` — sequential pipeline runner
  - run_zone10_analysis(provinces, questions, year_range) → dict
  - Returns: {policy_brief, sections: {hotspot, human_behavior, environment, kpi}, charts, metadata}
  - Uses kickoff_with_retry from agent_defaults.py
  - Size: M
  - Depends on: Task 3

### ✅ Checkpoint 2 — PASSED
- [x] run_zone10_data_only() returns all 7 questions, 0 errors
- [x] Imports clean: 7 tools registered, 3 agents created

## Phase 3 — Schema + Router

- [x] **Task 5** · `src/schemas/accident_policy.py` — Pydantic request/response models
  - AccidentPolicyRequest (provinces, questions, year_range, format)
  - AccidentPolicyResponse (zone, provinces, policy_brief, sections, charts, metadata)
  - Size: XS

- [x] **Task 6** · `src/routers/accident_policy.py` + main.py wiring
  - POST /api/accident-policy/zone10 (full LLM pipeline)
  - GET /api/accident-policy/zone10/data (raw SQL, no LLM, fast)
  - GET /accident-policy (HTML UI page)
  - Size: S
  - Depends on: Tasks 4, 5

### Checkpoint 3
- [ ] `/data` endpoint returns JSON within 5s
- [ ] Schema validation rejects invalid provinces
- [ ] No existing routes broken

## Phase 4 — Tests + UI

- [x] **Task 7** · `tests/test_accident_policy_api.py` — API integration tests
  - TestDataEndpoint: 6 tests for /zone10/data
  - TestPolicyRequest: 4 validation tests
  - TestPipelineSmoke: 1 slow-marked test (full LLM)
  - 10+ tests total, non-slow tests complete in <30s
  - Size: S
  - Depends on: Task 6

- [x] **Task 8** · `static/accident_policy_ui.html` — UI test page
  - Province checkboxes + year range inputs
  - Preview Data button → /data endpoint (fast)
  - Generate Analysis button → LLM pipeline
  - 4-tab results view (Hotspot / Human Behavior / Environment / KPI)
  - Markdown renderer + Chart.js charts
  - Size: L
  - Depends on: Tasks 6, 7

### Checkpoint 4 — DONE
- [x] `pytest tests/test_accident_policy_api.py -v -m "not slow"` all pass (14/14)
- [x] `pytest tests/test_zone10_tools.py -v` all pass (28/28)
- [x] UI Preview Data works in browser (/accident-policy, 200 OK)
- [ ] Human sign-off
