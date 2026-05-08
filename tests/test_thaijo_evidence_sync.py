"""Tests for ThaiJO Evidence Sync Agent (P04).

Covers:
  Phase 1  — rule-based + LLM field enrichment, JSONB patch
  Phase 1.5 — API re-fetch when usable articles < _MIN_REFS
  Phase 2  — evidence_registry INSERT ON CONFLICT DO NOTHING
  run_evidence_sync — end-to-end with all phases mocked
"""
import json
import sys
from dataclasses import asdict
from unittest.mock import MagicMock, patch, call

import pytest

# ── stub heavy deps before any project imports ──────────────────────────────
for _mod in (
    "crewai", "crewai.tools", "crewai.agents", "crewai.agents.parser",
    "asyncpg", "anthropic",
):
    sys.modules.setdefault(_mod, MagicMock())

from src.agents.thaijo_evidence_sync import (
    SyncResult,
    _needs_enrichment,
    _null_fields,
    _make_evidence_id,
    _format_apa,
    _count_usable,
    _fetch_more_from_api,
    _patch_cache_row,
    _phase1_enrich,
    _phase2_register,
    run_evidence_sync,
    _MIN_REFS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

_BASE_URL = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/100/200"
_BASE_URL2 = "https://he01.tci-thaijo.org/index.php/jnhs/article/view/101/201"

def _article(pdf_url=_BASE_URL, title="ชื่อบทความ", apa_authors="ผู้แต่ง ก",
             apa_year="2566", apa_journal="วารสารสุขภาพ", reference=None, summary=""):
    return {
        "pdf_url": pdf_url,
        "title": title,
        "apa_authors": apa_authors,
        "apa_year": apa_year,
        "apa_journal": apa_journal,
        "reference": reference,
        "summary": summary,
    }


def _null_article(pdf_url=_BASE_URL):
    """Article where all extractable fields are null."""
    return {
        "pdf_url": pdf_url,
        "title": None,
        "apa_authors": None,
        "apa_year": None,
        "apa_journal": None,
        "reference": None,
        "summary": "สรุปบทความ",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_needs_enrichment_all_null(self):
        assert _needs_enrichment(_null_article()) is True

    def test_needs_enrichment_partial_null(self):
        a = _article(apa_authors=None)
        assert _needs_enrichment(a) is True

    def test_needs_enrichment_complete(self):
        assert _needs_enrichment(_article()) is False

    def test_null_fields_returns_only_nulls(self):
        a = _article(title=None, apa_year=None)
        assert set(_null_fields(a)) == {"title", "apa_year"}

    def test_null_fields_empty_when_complete(self):
        assert _null_fields(_article()) == []

    def test_make_evidence_id_stable(self):
        ev1 = _make_evidence_id(_BASE_URL)
        ev2 = _make_evidence_id(_BASE_URL)
        assert ev1 == ev2
        assert ev1.startswith("TJ-")
        assert len(ev1) == 16

    def test_make_evidence_id_different_urls(self):
        assert _make_evidence_id(_BASE_URL) != _make_evidence_id(_BASE_URL2)

    def test_format_apa_all_fields(self):
        result = _format_apa("ชื่อ", "ผู้แต่ง", "2566", "วารสาร", _BASE_URL)
        assert "ผู้แต่ง" in result
        assert "2566" in result
        assert "ชื่อ" in result
        assert "วารสาร" in result
        assert _BASE_URL in result

    def test_format_apa_missing_fields(self):
        result = _format_apa(None, None, None, None, _BASE_URL)
        assert "[ไม่ระบุผู้แต่ง]" in result
        assert "[ไม่ระบุชื่อบทความ]" in result
        assert _BASE_URL in result

    def test_count_usable_counts_with_title(self):
        arts = [_article(), _null_article(), _article(pdf_url=_BASE_URL2)]
        assert _count_usable(arts) == 2

    def test_count_usable_all_null(self):
        assert _count_usable([_null_article(), _null_article()]) == 0

    def test_min_refs_value(self):
        assert _MIN_REFS == 5


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1.5 — _fetch_more_from_api
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchMoreFromApi:
    def _api_response(self, urls):
        return json.dumps({"results": [{"pdf_url": u, "title": f"t{i}"} for i, u in enumerate(urls)]})

    @patch("src.tools.thaijo._search_thaijo_impl")
    def test_returns_new_articles_only(self, mock_search):
        mock_search.return_value = self._api_response([_BASE_URL, _BASE_URL2])
        result = SyncResult()
        new = _fetch_more_from_api("คำค้น", {_BASE_URL}, result)
        assert len(new) == 1
        assert new[0]["pdf_url"] == _BASE_URL2
        assert result.api_new_articles == 1
        assert result.api_refetched_rows == 1

    @patch("src.tools.thaijo._search_thaijo_impl")
    def test_all_existing_returns_empty(self, mock_search):
        mock_search.return_value = self._api_response([_BASE_URL])
        result = SyncResult()
        new = _fetch_more_from_api("คำค้น", {_BASE_URL}, result)
        assert new == []
        assert result.api_new_articles == 0
        assert result.api_refetched_rows == 1

    @patch("src.tools.thaijo._search_thaijo_impl", side_effect=Exception("timeout"))
    def test_api_error_returns_empty(self, _mock):
        result = SyncResult()
        new = _fetch_more_from_api("คำค้น", set(), result)
        assert new == []
        assert result.api_refetched_rows == 0

    @patch("src.tools.thaijo._search_thaijo_impl")
    def test_dedup_within_api_response(self, mock_search):
        # API returns same URL twice — should only count once
        mock_search.return_value = self._api_response([_BASE_URL2, _BASE_URL2])
        result = SyncResult()
        new = _fetch_more_from_api("คำค้น", set(), result)
        assert len(new) == 1
        assert result.api_new_articles == 1


# ─────────────────────────────────────────────────────────────────────────────
# _patch_cache_row
# ─────────────────────────────────────────────────────────────────────────────

class TestPatchCacheRow:
    @patch("src.db.pool.execute_db", return_value=1)
    def test_returns_true_on_success(self, mock_exec):
        arts = [_article()]
        assert _patch_cache_row("key123", arts) is True
        mock_exec.assert_called_once()
        sql, params = mock_exec.call_args[0]
        assert "UPDATE thaijo_search_cache" in sql
        assert "key123" in params

    @patch("src.db.pool.execute_db", return_value=0)
    def test_returns_false_when_no_rows_updated(self, _mock):
        assert _patch_cache_row("key123", []) is False

    @patch("src.db.pool.execute_db", side_effect=Exception("DB down"))
    def test_returns_false_on_db_error(self, _mock):
        assert _patch_cache_row("key123", []) is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — _phase1_enrich
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_KEY = "abc12345"
_SEARCH_TERM = "ออกกำลังกาย ความดันโลหิต"

def _make_cache_row(articles, key=_CACHE_KEY, term=_SEARCH_TERM):
    return {"cache_key": key, "search_term": term, "normalized_term": term,
            "results_json": articles}


class TestPhase1Enrich:
    def _run(self, rows, rule_fields=None, llm_result=None, patch_ok=True):
        rule_fields = rule_fields or {}
        llm_result = llm_result or {}
        result = SyncResult()
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.tools.thaijo._extract_article_fields",
                   return_value=rule_fields), \
             patch("src.agents.thaijo_evidence_sync._llm_extract_fields",
                   return_value=llm_result), \
             patch("src.agents.thaijo_evidence_sync._patch_cache_row",
                   return_value=patch_ok), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary",
                   return_value=None), \
             patch("src.agents.thaijo_evidence_sync._fetch_more_from_api",
                   return_value=[]):
            enriched = _phase1_enrich(result, redis=None, model="model-x")
        return result, enriched

    def test_no_null_articles_skipped(self):
        rows = [_make_cache_row([_article()])]
        result, enriched = self._run(rows)
        assert result.articles_scanned == 1
        assert result.fields_filled_rule == 0
        assert result.fields_filled_llm == 0
        assert result.cache_patched == 0

    def test_rule_based_fills_null_fields(self):
        art = _null_article()
        rule = {"title": "ชื่อจาก rule", "apa_authors": "ผู้แต่ง",
                "apa_year": "2566", "apa_journal": "วารสาร"}
        rows = [_make_cache_row([art])]
        result, enriched = self._run(rows, rule_fields=rule)
        assert result.fields_filled_rule == 4
        assert result.fields_filled_llm == 0
        assert result.llm_calls == 0  # no LLM needed when rule fills everything

    def test_llm_fallback_for_remaining_nulls(self):
        art = _null_article()
        rule = {"title": "ชื่อจาก rule"}  # fills only title
        llm = {"apa_authors": "ผู้แต่ง LLM", "apa_year": "2565",
               "apa_journal": "วารสาร LLM", "bibliography_text": "ref text"}
        rows = [_make_cache_row([art])]
        result, enriched = self._run(rows, rule_fields=rule, llm_result=llm)
        assert result.fields_filled_rule == 1
        assert result.fields_filled_llm == 3
        assert result.llm_calls == 1

    def test_cache_patched_when_changed(self):
        art = _null_article()
        rule = {"title": "ชื่อ"}
        rows = [_make_cache_row([art])]
        result, enriched = self._run(rows, rule_fields=rule)
        assert result.cache_patched == 1

    def test_cache_not_patched_when_unchanged(self):
        rows = [_make_cache_row([_article()])]
        result, _ = self._run(rows)
        assert result.cache_patched == 0

    def test_enriched_map_returned(self):
        rows = [_make_cache_row([_article()])]
        result, enriched = self._run(rows)
        assert _CACHE_KEY in enriched
        assert "articles" in enriched[_CACHE_KEY]

    def test_db_error_increments_errors(self):
        result = SyncResult()
        with patch("src.db.pool.query_db",
                   side_effect=Exception("DB down")):
            enriched = _phase1_enrich(result, redis=None, model="x")
        assert result.errors == 1
        assert enriched == {}

    def test_phase15_triggered_when_usable_below_min(self):
        """Phase 1.5 should fire when usable articles < _MIN_REFS."""
        arts = [_null_article()]  # 1 article, no title → 0 usable
        rows = [_make_cache_row(arts)]
        result = SyncResult()
        new_art = _article(pdf_url=_BASE_URL2)
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.tools.thaijo._extract_article_fields", return_value={}), \
             patch("src.agents.thaijo_evidence_sync._llm_extract_fields",
                   return_value={"title": "LLM title", "apa_authors": None,
                                 "apa_year": None, "apa_journal": None}), \
             patch("src.agents.thaijo_evidence_sync._patch_cache_row", return_value=True), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary", return_value=None), \
             patch("src.agents.thaijo_evidence_sync._fetch_more_from_api",
                   return_value=[new_art]) as mock_fetch:
            enriched = _phase1_enrich(result, redis=None, model="x")
        mock_fetch.assert_called_once()
        merged = enriched[_CACHE_KEY]["articles"]
        assert any(a["pdf_url"] == _BASE_URL2 for a in merged)

    def test_phase15_not_triggered_when_enough_usable(self):
        """Phase 1.5 should NOT fire when usable articles >= _MIN_REFS."""
        arts = [_article(pdf_url=f"https://tci/{i}") for i in range(_MIN_REFS)]
        rows = [_make_cache_row(arts)]
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.tools.thaijo._extract_article_fields", return_value={}), \
             patch("src.agents.thaijo_evidence_sync._patch_cache_row", return_value=True), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary", return_value=None), \
             patch("src.agents.thaijo_evidence_sync._fetch_more_from_api") as mock_fetch:
            _phase1_enrich(SyncResult(), redis=None, model="x")
        mock_fetch.assert_not_called()

    def test_llm_null_string_not_stored(self):
        """LLM returning literal 'null' string should not be stored."""
        art = _null_article()
        llm = {"title": "null", "apa_authors": "null",
               "apa_year": "null", "apa_journal": "null"}
        rows = [_make_cache_row([art])]
        result, enriched = self._run(rows, rule_fields={}, llm_result=llm)
        assert result.fields_filled_llm == 0
        arts = enriched[_CACHE_KEY]["articles"]
        assert arts[0]["title"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — _phase2_register
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase2Register:
    def _run(self, all_rows, enriched_map=None, execute_rowcount=1):
        result = SyncResult()
        enriched_map = enriched_map or {}
        with patch("src.db.pool.query_db", return_value=all_rows), \
             patch("src.db.pool.execute_db",
                   return_value=execute_rowcount), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary",
                   return_value=None):
            _phase2_register(result, enriched_map, redis=None)
        return result

    def test_inserts_new_article(self):
        rows = [_make_cache_row([_article()])]
        result = self._run(rows, execute_rowcount=1)
        assert result.evidence_inserted == 1
        assert result.evidence_skipped == 0
        assert result.evidence_errors == 0

    def test_skips_existing_article(self):
        rows = [_make_cache_row([_article()])]
        result = self._run(rows, execute_rowcount=0)
        assert result.evidence_inserted == 0
        assert result.evidence_skipped == 1

    def test_skips_article_without_pdf_url(self):
        art = dict(_article())
        art["pdf_url"] = ""
        rows = [_make_cache_row([art])]
        result = self._run(rows)
        assert result.evidence_inserted == 0

    def test_uses_enriched_map_over_db_row(self):
        db_art = _article(title="DB title")
        enriched_art = _article(title="Enriched title")
        rows = [_make_cache_row([db_art])]
        enriched_map = {_CACHE_KEY: {"search_term": _SEARCH_TERM,
                                      "articles": [enriched_art]}}
        inserted_sql_params = []
        def capture_exec(sql, params):
            inserted_sql_params.append(params)
            return 1
        result = SyncResult()
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.db.pool.execute_db",
                   side_effect=capture_exec), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary",
                   return_value=None):
            _phase2_register(result, enriched_map, redis=None)
        assert result.evidence_inserted == 1
        # title param is index 3 (ev_id, topic, source_ref, title, ...)
        assert "Enriched title" in inserted_sql_params[0]

    def test_db_error_increments_evidence_errors(self):
        rows = [_make_cache_row([_article()])]
        result = SyncResult()
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.db.pool.execute_db",
                   side_effect=Exception("constraint")), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary",
                   return_value=None):
            _phase2_register(result, {}, redis=None)
        assert result.evidence_errors == 1
        assert result.evidence_inserted == 0

    def test_redis_snippet_used_when_available(self):
        captured = []
        def capture_exec(sql, params):
            captured.append(params)
            return 1
        rows = [_make_cache_row([_article(summary="short")])]
        result = SyncResult()
        with patch("src.db.pool.query_db", return_value=rows), \
             patch("src.db.pool.execute_db",
                   side_effect=capture_exec), \
             patch("src.agents.thaijo_evidence_sync._lookup_redis_summary",
                   return_value="full redis summary from GPT-4.1"):
            _phase2_register(result, {}, redis=MagicMock())
        assert result.evidence_inserted == 1
        # text_snippet is index 4
        assert "full redis summary" in captured[0][4]

    def test_scan_error_increments_errors(self):
        result = SyncResult()
        with patch("src.db.pool.query_db",
                   side_effect=Exception("DB down")):
            _phase2_register(result, {}, redis=None)
        assert result.errors == 1

    def test_multiple_articles_all_inserted(self):
        arts = [_article(), _article(pdf_url=_BASE_URL2)]
        rows = [_make_cache_row(arts)]
        result = self._run(rows, execute_rowcount=1)
        assert result.evidence_inserted == 2


# ─────────────────────────────────────────────────────────────────────────────
# run_evidence_sync — end-to-end (all phases mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEvidenceSync:
    def _make_enriched_map(self):
        return {_CACHE_KEY: {"search_term": _SEARCH_TERM, "articles": [_article()]}}

    def test_returns_sync_result(self):
        with patch("src.agents.thaijo_evidence_sync._get_redis", return_value=None), \
             patch("src.agents.thaijo_evidence_sync._phase1_enrich",
                   return_value=self._make_enriched_map()) as m1, \
             patch("src.agents.thaijo_evidence_sync._phase2_register") as m2:
            result = run_evidence_sync(llm_model="test-model")
        assert isinstance(result, SyncResult)
        m1.assert_called_once()
        m2.assert_called_once()

    def test_llm_model_passed_to_phase1(self):
        with patch("src.agents.thaijo_evidence_sync._get_redis", return_value=None), \
             patch("src.agents.thaijo_evidence_sync._phase1_enrich",
                   return_value={}) as m1, \
             patch("src.agents.thaijo_evidence_sync._phase2_register"):
            run_evidence_sync(llm_model="claude-haiku-4-5-20251001")
        _, kwargs = m1.call_args
        # model is positional arg 3
        assert "claude-haiku-4-5-20251001" in m1.call_args[0]

    def test_result_fields_match_dataclass(self):
        """SyncResult asdict keys must match EvidenceSyncResult Pydantic model."""
        r = SyncResult()
        d = asdict(r)
        expected_keys = {
            "cache_rows_scanned", "articles_scanned",
            "fields_filled_rule", "fields_filled_llm", "llm_calls", "cache_patched",
            "api_refetched_rows", "api_new_articles",
            "evidence_inserted", "evidence_skipped", "evidence_errors",
            "errors", "details",
        }
        assert set(d.keys()) == expected_keys

    def test_phase2_receives_phase1_enriched_map(self):
        enriched = self._make_enriched_map()
        received = {}
        def fake_p2(result, em, redis):
            received.update(em)
        with patch("src.agents.thaijo_evidence_sync._get_redis", return_value=None), \
             patch("src.agents.thaijo_evidence_sync._phase1_enrich",
                   return_value=enriched), \
             patch("src.agents.thaijo_evidence_sync._phase2_register",
                   side_effect=fake_p2):
            run_evidence_sync()
        assert _CACHE_KEY in received
