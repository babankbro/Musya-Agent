"""Integration tests for Task 6: Full ThaiJO cache + validation pipeline.

Tests the complete flow:
  search_thaijo (cache+API) → thaijo_research_orchestrator._parse → citations

All tests are offline — mock httpx and DB.
"""
import sys
import json
from unittest.mock import MagicMock, patch, call

import pytest

# Module-level mocks so imports don't fail without venv
sys.modules.setdefault("crewai", MagicMock())
sys.modules.setdefault("crewai.tools", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.pool", MagicMock())

from src.tools.thaijo import (
    _is_valid_thaijo_url,
    _normalize_term,
    _cache_key,
    _search_thaijo_impl,
)
from src.agents.thaijo_research_orchestrator import _parse
from src.schemas.thaijo_research import ThaiJOResearchResponse

# ── shared fixtures ──────────────────────────────────────────────────────────

VALID_URL_1 = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/11111"
VALID_URL_2 = "https://he02.tci-thaijo.org/index.php/abc/article/view/22222"
REF_1 = "ผู้แต่ง ก. (2566). ป้องกันเบาหวาน ด้วยการออกกำลังกาย. วารสารสาธารณสุข, 1(1), 1-10."
REF_2 = "ผู้แต่ง ข. (2565). พฤติกรรมสุขภาพในผู้ป่วยเบาหวาน. วารสารสุขภาพ, 2(2), 20-30."

ARTICLE_1 = {
    "pdf_url": VALID_URL_1,
    "summary": "บทความเกี่ยวกับการป้องกันเบาหวาน",
    "reference": REF_1,
    "source_type": "thaijo_article",
}
ARTICLE_2 = {
    "pdf_url": VALID_URL_2,
    "summary": "บทความเกี่ยวกับพฤติกรรมสุขภาพ",
    "reference": REF_2,
    "source_type": "thaijo_article",
}


def _make_searcher_raw(articles):
    return json.dumps({"total_unique_articles": len(articles), "articles": articles})


def _make_screener_raw(count=0):
    return json.dumps({"total_included": count, "screened_articles": []})


def _make_citation_json(citations_data):
    citations = []
    for d in citations_data:
        citations.append({
            "citation_code": d["code"],
            "evidence_id": d.get("evidence_id", ""),
            "source_type": "thaijo_article",
            "source_ref": d.get("source_ref", ""),
            "citation_text": d.get("citation_text", ""),
            "open_url": d.get("open_url", ""),
            "bibliography_text": d.get("bib", ""),
            "trust_level": "high",
        })
    return json.dumps({"citations": citations, "evidence_items": [], "claims": []})


def _make_mock_result(searcher_raw, screener_raw, citation_raw):
    mock_searcher = MagicMock(); mock_searcher.raw = searcher_raw
    mock_screener = MagicMock(); mock_screener.raw = screener_raw
    mock_citation = MagicMock(); mock_citation.raw = citation_raw
    mock_result = MagicMock()
    mock_result.__str__.return_value = "Full report content"
    mock_result.tasks_output = [
        MagicMock(), mock_searcher, mock_screener,
        mock_citation, MagicMock(), MagicMock(),
    ]
    return mock_result


# ── Scenario A: Cache MISS → API → cache written → _parse gets correct URLs ──

class TestCacheMissToParseIntegration:
    def test_api_articles_flow_into_parse_correctly(self):
        """Full path: API returns 2 valid articles → cached → _parse fixes LLM citation."""
        # The LLM produced a citation with a hallucinated URL
        citation_data = [{
            "code": "C-200",
            "open_url": "https://hallucinated.com/fake/99",
            "bib": REF_1,  # bib text matches searcher article 1
        }]

        # _parse gets searcher articles that came from the API
        mock_result = _make_mock_result(
            _make_searcher_raw([ARTICLE_1, ARTICLE_2]),
            _make_screener_raw(2),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "เบาหวาน", 5.0)

        assert isinstance(response, ThaiJOResearchResponse)
        assert len(response.citations) == 1
        c = response.citations[0]
        # hallucinated URL must be cleared (invalid pattern)
        assert c["open_url"] == ""

    def test_valid_url_that_matches_searcher_is_kept(self):
        """If LLM correctly outputs a real URL that's in searcher map → kept and bib reinforced."""
        citation_data = [{
            "code": "C-200",
            "open_url": VALID_URL_1,
            "bib": "old bib text that will be overwritten",
        }]
        mock_result = _make_mock_result(
            _make_searcher_raw([ARTICLE_1, ARTICLE_2]),
            _make_screener_raw(2),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "เบาหวาน", 5.0)

        c = response.citations[0]
        assert c["open_url"] == VALID_URL_1
        assert c["bibliography_text"] == REF_1


# ── Scenario B: Cache HIT → skips API ────────────────────────────────────────

class TestCacheHitSkipsApi:
    def test_cache_hit_returns_cached_data_without_api_call(self):
        """Cache HIT: no httpx calls, returns cached articles."""
        cached = [ARTICLE_1, ARTICLE_2]
        with patch("src.tools.thaijo._read_cache", return_value=cached), \
             patch("src.tools.thaijo._increment_hit") as mock_incr, \
             patch("src.tools.thaijo.httpx") as mock_httpx:

            result = json.loads(_search_thaijo_impl("เบาหวาน ป้องกัน"))

        assert result["count"] == 2
        assert result["results"] == cached
        mock_httpx.Client.assert_not_called()
        mock_incr.assert_called_once()

    def test_cache_key_deterministic_for_same_query(self):
        """Same query (different whitespace) should produce identical cache key."""
        key1 = _cache_key(_normalize_term("เบาหวาน  ป้องกัน"), 5)
        key2 = _cache_key(_normalize_term("เบาหวาน ป้องกัน"), 5)
        assert key1 == key2


# ── Scenario C: URL filter removes invalid articles from API response ─────────

class TestUrlFilterInPipeline:
    def test_mixed_valid_invalid_articles_only_valid_reach_parse(self):
        """API returns mix of valid + invalid URLs; only valid ones pass URL filter."""
        mixed_articles = [
            ARTICLE_1,  # valid
            {"pdf_url": "https://hallucinated.example.com/fake", "summary": "bad", "reference": "bad"},
            {"pdf_url": "", "summary": "empty url", "reference": "empty"},
            ARTICLE_2,  # valid
        ]
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache") as mock_write, \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"count": 4, "results": mixed_articles}
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("เบาหวาน"))

        assert result["count"] == 2
        assert all(_is_valid_thaijo_url(r["pdf_url"]) for r in result["results"])
        # Only valid articles written to cache
        written_results = mock_write.call_args[0][3]  # 4th positional arg = results
        assert len(written_results) == 2

    def test_all_invalid_returns_zero_results(self):
        """If ALL articles have invalid URLs → return empty, write empty cache."""
        bad_articles = [
            {"pdf_url": "https://bad1.com/fake", "summary": "s", "reference": "r"},
            {"pdf_url": "https://bad2.com/fake", "summary": "s", "reference": "r"},
        ]
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache") as mock_write, \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"count": 2, "results": bad_articles}
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("เบาหวาน"))

        assert result["count"] == 0
        assert result["results"] == []


# ── Scenario D: DB unavailable → fail open ───────────────────────────────────

class TestDbUnavailableFailOpen:
    def test_cache_read_db_error_falls_through_to_api(self):
        """DB error during cache read → MISS path → API called normally."""
        with patch("src.db.pool.query_db", side_effect=Exception("DB down")), \
             patch("src.tools.thaijo._write_cache"), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"count": 1, "results": [ARTICLE_1]}
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("เบาหวาน"))

        # DB error in _read_cache → returns None → API path runs → valid article returned
        assert result["count"] == 1
        assert result["results"][0]["pdf_url"] == VALID_URL_1

    def test_cache_write_db_error_does_not_affect_result(self):
        """DB error during cache write → result still returned correctly."""
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.db.pool.execute_db", side_effect=Exception("DB down")), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"count": 1, "results": [ARTICLE_1]}
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("เบาหวาน"))

        assert result["count"] == 1


# ── Scenario E: End-to-end hallucination clearing in _parse ──────────────────

class TestEndToEndHallucinationClearing:
    def test_multiple_citations_partial_hallucination(self):
        """Two citations: one with correct URL (in searcher), one hallucinated → second cleared."""
        citation_data = [
            {"code": "C-200", "open_url": VALID_URL_1, "bib": REF_1},   # correct
            {"code": "C-201", "open_url": "https://hallucinated.org/x", "bib": "other bib"},  # hallucinated
        ]
        mock_result = _make_mock_result(
            _make_searcher_raw([ARTICLE_1, ARTICLE_2]),
            _make_screener_raw(2),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "เบาหวาน", 3.0)

        assert len(response.citations) == 2
        c200 = next(c for c in response.citations if c["citation_code"] == "C-200")
        c201 = next(c for c in response.citations if c["citation_code"] == "C-201")

        assert c200["open_url"] == VALID_URL_1
        assert c200["bibliography_text"] == REF_1
        assert c201["open_url"] == ""  # hallucinated → cleared

    def test_no_searcher_articles_all_invalid_urls_cleared(self):
        """No searcher articles: hallucinated URLs fail pattern check → all cleared."""
        citation_data = [
            {"code": "C-200", "open_url": "https://hallucinated.com/x", "bib": "bib"},
        ]
        mock_result = _make_mock_result(
            _make_searcher_raw([]),  # empty searcher
            _make_screener_raw(0),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        assert c["open_url"] == ""

    def test_no_searcher_articles_valid_pattern_url_preserved(self):
        """No searcher articles: URL passes pattern → kept as-is (no fuzzy data to match)."""
        valid_url = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/9999"
        citation_data = [{"code": "C-200", "open_url": valid_url, "bib": "some bib"}]
        mock_result = _make_mock_result(
            _make_searcher_raw([]),  # empty searcher
            _make_screener_raw(0),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        # Valid pattern but no searcher articles → Priority 3 fuzzy has no candidates → URL kept
        assert c["open_url"] == valid_url

    def test_citation_guard_metadata(self):
        """ThaiJOResearchResponse metadata fields are correct regardless of URL correction."""
        citation_data = [
            {"code": "C-200", "open_url": VALID_URL_1, "bib": REF_1},
            {"code": "C-201", "open_url": VALID_URL_2, "bib": REF_2},
        ]
        mock_result = _make_mock_result(
            _make_searcher_raw([ARTICLE_1, ARTICLE_2]),
            _make_screener_raw(2),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "เบาหวาน พฤติกรรม", 8.5)

        assert response.topic == "เบาหวาน พฤติกรรม"
        assert response.metadata["pipeline"] == "thaijo_research"
        assert response.metadata["agent_count"] == 6
        assert response.metadata["citation_count"] == 2
        assert response.metadata["elapsed_seconds"] == 8.5
