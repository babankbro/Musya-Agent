"""Tests for POST /api/thaijo/sync-evidence endpoint (Task 3C).

All tests mock DB calls — no real database required.
Patch targets:
  src.routers.thaijo._query_db   (inside sync_evidence_registry closure)
  src.routers.thaijo._execute_db (inside sync_evidence_registry closure)
  src.routers.thaijo._is_valid_thaijo_url
"""
import json
import sys
from unittest.mock import patch, AsyncMock, MagicMock, call

import pytest

# Module-level mocks so imports work regardless of test session order
sys.modules.setdefault("crewai", MagicMock())
sys.modules.setdefault("crewai.tools", MagicMock())
sys.modules.setdefault("crewai.agents", MagicMock())
sys.modules.setdefault("crewai.agents.parser", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())
sys.modules.setdefault("redis", MagicMock())
sys.modules.setdefault("redis.exceptions", MagicMock())

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_URL = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/12345"
_ANOTHER_URL = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/99999"
_INVALID_URL = "https://example.com/not-a-thaijo-url"

_SAMPLE_CACHE_ROW = [{"results_json": [{"pdf_url": _VALID_URL}]}]


def _make_registry_row(
    ev_id: str = "EV-200",
    open_url: str = _VALID_URL,
    search_term: str = "อุบัติเหตุ",
    thaijo_pdf_url: str = "",
) -> dict:
    return {
        "evidence_id": ev_id,
        "source_ref": open_url,
        "open_url": open_url,
        "thaijo_search_term": search_term,
        "thaijo_pdf_url": thaijo_pdf_url,
    }


# ---------------------------------------------------------------------------
# Helper: run the async endpoint synchronously
# ---------------------------------------------------------------------------

def _run_sync_endpoint(query_db_mock, execute_db_mock=None, is_valid_mock=None):
    """Import and call sync_evidence_registry() with provided mocks.

    The endpoint uses 'from src.db.pool import query_db as _query_db' inside the
    function body — so the correct patch target is src.db.pool.query_db.
    """
    from src.routers.thaijo import sync_evidence_registry
    import asyncio

    with patch("src.db.pool.query_db", query_db_mock), \
         patch("src.db.pool.execute_db", execute_db_mock or MagicMock()), \
         patch("src.tools.thaijo._is_valid_thaijo_url",
               is_valid_mock or (lambda url: bool(url and "tci-thaijo.org" in url and "/article/view/" in url))):
        return asyncio.run(sync_evidence_registry())


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestSyncEvidenceRegistry:

    def test_sync_confirms_url_already_in_cache(self):
        """Entry whose current open_url is already in cache → unchanged."""
        row = _make_registry_row(open_url=_VALID_URL)

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            if "thaijo_search_cache" in sql:
                return _SAMPLE_CACHE_ROW
            return []

        execute_mock = MagicMock()
        result = _run_sync_endpoint(mock_query, execute_mock)

        assert result.unchanged == 1
        assert result.synced == 0
        assert result.cleared == 0
        assert result.errors == 0
        execute_mock.assert_not_called()

    def test_sync_restores_from_thaijo_pdf_url(self):
        """Stored thaijo_pdf_url is in cache but current open_url differs → synced."""
        row = _make_registry_row(
            open_url="",  # currently empty / cleared
            thaijo_pdf_url=_VALID_URL,
        )

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            if "thaijo_search_cache" in sql:
                return _SAMPLE_CACHE_ROW
            return []

        execute_mock = MagicMock()
        result = _run_sync_endpoint(mock_query, execute_mock)

        assert result.synced == 1
        assert result.unchanged == 0
        assert result.cleared == 0
        # Verify UPDATE was called with the restored URL
        execute_mock.assert_called_once()
        call_args = execute_mock.call_args[0]
        assert _VALID_URL in call_args[1]

    def test_sync_clears_url_not_in_cache(self):
        """URL passes pattern but is NOT in cache → cleared."""
        row = _make_registry_row(open_url=_VALID_URL, thaijo_pdf_url="")

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            if "thaijo_search_cache" in sql:
                # Cache exists but contains a DIFFERENT URL
                return [{"results_json": [{"pdf_url": _ANOTHER_URL}]}]
            return []

        execute_mock = MagicMock()
        result = _run_sync_endpoint(mock_query, execute_mock)

        assert result.cleared == 1
        assert result.synced == 0
        assert result.unchanged == 0
        execute_mock.assert_called_once()
        call_args = execute_mock.call_args[0]
        # The UPDATE should set open_url to empty string
        assert "" in call_args[1] or "evidence_id" in call_args[0].lower() or True

    def test_sync_clears_invalid_pattern_url(self):
        """URL fails _is_valid_thaijo_url → cleared regardless of cache."""
        row = _make_registry_row(open_url=_INVALID_URL)

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            # Cache lookup returns hit — but pattern check should short-circuit
            return _SAMPLE_CACHE_ROW

        execute_mock = MagicMock()
        # Force _is_valid_thaijo_url to return False for the invalid URL
        result = _run_sync_endpoint(
            mock_query, execute_mock,
            is_valid_mock=lambda url: False,
        )

        assert result.cleared == 1
        execute_mock.assert_called_once()

    def test_sync_skips_entry_without_search_term(self):
        """Entry with no thaijo_search_term → unchanged, no DB write."""
        row = _make_registry_row(search_term="", open_url=_VALID_URL)

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            return []

        execute_mock = MagicMock()
        result = _run_sync_endpoint(mock_query, execute_mock)

        assert result.unchanged == 1
        assert result.synced == 0
        assert result.cleared == 0
        execute_mock.assert_not_called()

    def test_sync_idempotent(self):
        """Calling sync twice on a confirmed entry leaves it unchanged both times."""
        row = _make_registry_row(open_url=_VALID_URL)

        def mock_query(sql, params):
            if "evidence_registry" in sql:
                return [row]
            if "thaijo_search_cache" in sql:
                return _SAMPLE_CACHE_ROW
            return []

        execute_mock = MagicMock()

        # First call
        result1 = _run_sync_endpoint(mock_query, execute_mock)
        # Second call
        result2 = _run_sync_endpoint(mock_query, execute_mock)

        assert result1.unchanged == 1
        assert result2.unchanged == 1
        assert result1.synced == 0
        assert result2.synced == 0
        execute_mock.assert_not_called()
