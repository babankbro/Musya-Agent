# ThaiJO Research Report — Hallucinated PDF Links Fix

## Problem Statement
When using the `thaijo_research_ui.html` interface:
1. **"Search Articles" Tab**: correctly returns accurate `pdf_url` links directly from the ThaiJO search API.
2. **"Create Research Report" Tab**: generates hallucinated PDF links and truncated APA references. The 6-agent pipeline's Citation Generator (Agent 4) is generative and sometimes fabricates `open_url` and `bibliography_text` values.

**Root Causes (from p01 plan)**:
- **RC-1**: No URL validation on API results — invalid URLs passed to LLM
- **RC-2**: No persistence of API results before LLM — no source of truth
- **RC-3**: `parse_evidence_context()` explicitly skipped ThaiJO citations in its cross-reference guard
- **RC-4**: `_parse()` used Screener output (not Searcher) and a loose ratio threshold (0.3)

## Fix Architecture (p01 Plan — Implemented)

### Phase 1 — Anchor: Persist API results before LLM sees them
- **Task 1**: `database/018_thaijo_search_cache.sql` — new `thaijo_search_cache` table with GIN index on `results_json`
- **Task 2**: `src/tools/thaijo.py` — `THAIJO_URL_PATTERN` regex validates URLs; `_search_thaijo_impl()` implements cache-first (HIT/MISS) with UPSERT; invalid URLs filtered before caching or returning

### Phase 2 — Verify: Check URLs after LLM output
- **Task 3**: `src/agents/citation_evidence.py` — `_verify_thaijo_url_in_cache()` checks each ThaiJO citation's `open_url` against `thaijo_search_cache`; clears hallucinated URLs (fails open on DB error)
- **Task 4**: `src/agents/thaijo_research_orchestrator.py` — `_parse()` uses Searcher output (`to[1]`) as source; priority-based correction:
  1. Exact URL match in searcher map → keep + reinforce reference
  2. Invalid URL pattern → clear immediately
  3. Fuzzy match ≥ 0.6 → correct URL + reference
  4. Fuzzy < 0.6 → clear (no link better than wrong link)

### Phase 3 — Guard: Logging
- **Task 5**: Citation guard log in `_parse()` reports count of cleared ThaiJO citations per run

## Configuration Added
- `src/config.py`: `THAIJO_CACHE_TTL_DAYS: int = 7`
- Add `THAIJO_CACHE_TTL_DAYS=7` to `.env` to override

## Files Modified
| File | Change |
|------|--------|
| `database/018_thaijo_search_cache.sql` | New — cache table + GIN index |
| `src/config.py` | Added `THAIJO_CACHE_TTL_DAYS` |
| `src/tools/thaijo.py` | URL validation, cache helpers, `_search_thaijo_impl()` |
| `src/agents/citation_evidence.py` | `_verify_thaijo_url_in_cache()` + ThaiJO verification block |
| `src/agents/thaijo_research_orchestrator.py` | `_parse()` priority-based correction + citation guard log |

## Tests
| File | Coverage |
|------|----------|
| `tests/test_thaijo_cache.py` | URL validation, cache helpers, `_search_thaijo_impl()` (36 tests) |
| `tests/test_thaijo_orchestrator_parse.py` | `_parse()` all 4 priorities (8 tests) |
| `tests/test_thaijo_integration.py` | End-to-end pipeline scenarios (12 tests) |

Run: `python -m pytest tests/test_thaijo_cache.py tests/test_thaijo_orchestrator_parse.py tests/test_thaijo_integration.py --noconftest -v`

## DB Migration
```bash
psql $DATABASE_URL -f database/018_thaijo_search_cache.sql
psql $DATABASE_URL -c "\d thaijo_search_cache"
psql $DATABASE_URL -c "\di idx_thaijo_cache_*"
```

## Verification (Manual)
1. Run research report at `http://localhost:8000/static/thaijo_research_ui.html`
2. Check citations at bottom — all URLs should point to `he0N.tci-thaijo.org` or `tci-thaijo.org`
3. Server logs should show `Citation guard: N ThaiJO citation(s) had URLs cleared` if hallucinations were detected

## Status
**Completed** — all 56 tests pass. Cache-first architecture ensures LLM always sees pre-validated URLs, and any remaining hallucinations are caught by two independent guards (pattern check + cache lookup).
