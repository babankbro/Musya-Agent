"""Unit tests for Task 4: _parse() URL correction — p01 plan.

Fully offline: mocks crewai and DB. Tests the new priority-based URL correction:
  P1: exact match in searcher_url_map
  P2: invalid URL pattern → clear
  P3: fuzzy match on searcher articles, threshold 0.6
  P4: fuzzy below threshold → clear
Source: Searcher output (to[1]), NOT Screener (to[2]).
"""
import sys
import json
from unittest.mock import MagicMock, patch
import pytest

# Module-level mocks so imports don't fail without venv
sys.modules.setdefault("crewai", MagicMock())
sys.modules.setdefault("crewai.tools", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("psycopg2.pool", MagicMock())

from src.agents.thaijo_research_orchestrator import _parse
from src.schemas.thaijo_research import ThaiJOResearchResponse


# ── helpers ────────────────────────────────────────────────────────────────

REAL_URL_A = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/12345"
REAL_URL_B = "https://he01.tci-thaijo.org/index.php/abc/article/view/99999"
REF_A = "Real Author. (2023). Real Title. Real Journal, 1(1), 1-10."
REF_B = "Author B. (2022). Title B. Journal B, 2(2), 20-30."


def _make_searcher_raw(articles):
    """Build a JSON string mimicking what the ThaiJO Searcher agent outputs."""
    return json.dumps({"total_unique_articles": len(articles), "articles": articles})


def _make_screener_raw(count=5):
    return json.dumps({"total_included": count, "screened_articles": []})


def _make_citation_json(citations_data):
    """Build JSON string mimicking Citation Agent output (parse_evidence_context is JSON-only)."""
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


def _make_mock_result(searcher_raw, screener_raw, citation_raw, output_str="Report content"):
    mock_searcher = MagicMock()
    mock_searcher.raw = searcher_raw
    mock_screener = MagicMock()
    mock_screener.raw = screener_raw
    mock_citation = MagicMock()
    mock_citation.raw = citation_raw
    mock_result = MagicMock()
    mock_result.__str__.return_value = output_str
    mock_result.tasks_output = [
        MagicMock(),     # to[0]: topic parser
        mock_searcher,   # to[1]: searcher
        mock_screener,   # to[2]: screener
        mock_citation,   # to[3]: citation
        MagicMock(),     # to[4]: synthesizer
        MagicMock(),     # to[5]: composer
    ]
    return mock_result


# ── Priority 1: exact URL match in searcher map ─────────────────────────────

class TestExactUrlMatch:
    def test_exact_match_url_kept_and_reference_reinforced(self):
        """Citation URL exactly matches searcher → keep URL, overwrite bib with searcher ref."""
        searcher_articles = [{"pdf_url": REAL_URL_A, "reference": REF_A, "summary": "s"}]
        citation_data = [{"code": "C-200", "open_url": REAL_URL_A, "bib": "old bib text"}]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            _make_screener_raw(),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "Diabetes", 5.0)

        assert len(response.citations) == 1
        c = response.citations[0]
        assert c["open_url"] == REAL_URL_A
        assert c["bibliography_text"] == REF_A

    def test_source_is_searcher_not_screener(self):
        """Searcher and screener have different articles — searcher wins."""
        searcher_articles = [{"pdf_url": REAL_URL_A, "reference": REF_A, "summary": "s"}]
        # screener has a DIFFERENT article — should be irrelevant
        screener_raw = json.dumps({
            "total_included": 1,
            "screened_articles": [{"pdf_url": REAL_URL_B, "reference": REF_B}],
        })
        citation_data = [{"code": "C-200", "open_url": REAL_URL_A, "bib": "s"}]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            screener_raw,
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        assert c["open_url"] == REAL_URL_A
        assert c["bibliography_text"] == REF_A


# ── Priority 2: invalid URL pattern → clear ─────────────────────────────────

class TestInvalidUrlPatternCleared:
    def test_hallucinated_url_cleared(self):
        """Citation URL doesn't match pattern and isn't in searcher → cleared."""
        searcher_articles = [{"pdf_url": REAL_URL_A, "reference": REF_A, "summary": "completely different topic"}]
        citation_data = [{
            "code": "C-200",
            "open_url": "https://hallucinated-fake.com/article/123",
            "bib": "hallucinated bib",
        }]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            _make_screener_raw(),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        assert c["open_url"] == ""

    def test_empty_url_not_modified(self):
        """Citation with empty open_url should stay empty (no pattern check triggered)."""
        searcher_articles = [{"pdf_url": REAL_URL_A, "reference": REF_A, "summary": "completely different topic xyz"}]
        citation_data = [{"code": "C-200", "open_url": "", "bib": "hallucinated bib"}]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            _make_screener_raw(),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        assert c["open_url"] == ""


# ── Priority 3: fuzzy match on searcher, threshold 0.6 ───────────────────────

class TestFuzzyMatchThreshold:
    def test_fuzzy_above_threshold_corrects_url(self):
        """URL is a valid pattern but not in searcher map; fuzzy match ≥ 0.6 → correct."""
        # Citation has slightly truncated reference; searcher has the full one
        full_ref = "Author A. (2023). Diabetes Prevention in Rural Thailand. JPHD, 21(3), 100-112."
        truncated_ref = "Author A. (2023). Diabetes Prevention in Rural Thailand. JPHD, 21(3)"
        wrong_url = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/99"  # valid pattern, wrong id

        searcher_articles = [{"pdf_url": REAL_URL_A, "reference": full_ref, "summary": "s"}]
        citation_data = [{"code": "C-200", "open_url": wrong_url, "bib": truncated_ref}]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            _make_screener_raw(),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "Diabetes", 1.0)

        c = response.citations[0]
        # Should have been corrected to the real searcher URL
        assert c["open_url"] == REAL_URL_A
        assert c["bibliography_text"] == full_ref

    def test_fuzzy_below_threshold_clears_url(self):
        """Fuzzy ratio < 0.6 → open_url cleared (better to have no link than wrong link)."""
        searcher_articles = [{
            "pdf_url": REAL_URL_A,
            "reference": "Completely different topic about accident statistics",
            "summary": "road accident analysis",
        }]
        wrong_url = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/99"  # valid pattern
        citation_data = [{
            "code": "C-200",
            "open_url": wrong_url,
            "bib": "Diabetes nutrition intervention study 2023 Bangkok",
        }]

        mock_result = _make_mock_result(
            _make_searcher_raw(searcher_articles),
            _make_screener_raw(),
            _make_citation_json(citation_data),
        )
        response = _parse(mock_result, "test", 1.0)

        c = response.citations[0]
        assert c["open_url"] == ""


# ── ThaiJOResearchResponse shape ─────────────────────────────────────────────

class TestParseResponseShape:
    def test_returns_correct_response_type(self):
        mock_result = _make_mock_result(
            _make_searcher_raw([]),
            _make_screener_raw(0),
            _make_citation_json([]),
        )
        response = _parse(mock_result, "test topic", 3.5)
        assert isinstance(response, ThaiJOResearchResponse)
        assert response.topic == "test topic"
        assert response.metadata["elapsed_seconds"] == 3.5
        assert response.metadata["pipeline"] == "thaijo_research"

    def test_articles_counts_from_searcher_and_screener(self):
        searcher_raw = json.dumps({"total_unique_articles": 12, "articles": []})
        screener_raw = json.dumps({"total_included": 7, "screened_articles": []})
        mock_result = _make_mock_result(searcher_raw, screener_raw, _make_citation_json([]))
        response = _parse(mock_result, "test", 1.0)
        assert response.articles_found == 12
        assert response.articles_selected == 7
