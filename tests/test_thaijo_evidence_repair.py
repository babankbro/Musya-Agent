"""Tests for GET /api/thaijo/evidence and POST /api/thaijo/fix-evidence-urls endpoints.

Phase E2: verifies URL normalization logic in the evidence repair endpoints.
"""
import sys
from unittest.mock import patch, MagicMock

import pytest

# Module-level mocks so imports work regardless of session order
sys.modules.setdefault("crewai", MagicMock())
sys.modules.setdefault("crewai.tools", MagicMock())
sys.modules.setdefault("crewai.agents", MagicMock())
sys.modules.setdefault("crewai.agents.parser", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

_VALID_VIEW_URL  = "https://he01.tci-thaijo.org/index.php/jnat/article/view/250446"
_VIEW_WITH_FILE  = "https://he01.tci-thaijo.org/index.php/jnat/article/view/250446/169419"  # also valid
_DOWNLOAD_URL    = "https://he01.tci-thaijo.org/index.php/jnat/article/download/250446/169419"  # normalized → view
_INVALID_URL     = "https://example.com/not-thaijo"


def _make_ev_row(evidence_id, open_url, source_ref="", original_url=""):
    return {
        "evidence_id": evidence_id,
        "open_url": open_url,
        "source_ref": source_ref or open_url,
        "original_url": original_url or open_url,
        "title": "Test Article",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_fix_endpoint(query_rows, execute_mock=None):
    """Call fix_evidence_urls() synchronously with mocked DB."""
    import asyncio
    from src.routers.thaijo import fix_evidence_urls

    with patch("src.db.pool.query_db", return_value=query_rows), \
         patch("src.db.pool.execute_db", execute_mock or MagicMock()):
        return asyncio.run(fix_evidence_urls())


def _run_list_endpoint(query_rows, bad_only=False):
    """Call list_thaijo_evidence() synchronously with mocked DB."""
    import asyncio
    from src.routers.thaijo import list_thaijo_evidence

    with patch("src.db.pool.query_db", return_value=query_rows):
        return asyncio.run(list_thaijo_evidence(bad_only=bad_only))


# ---------------------------------------------------------------------------
# Tests: GET /api/thaijo/evidence
# ---------------------------------------------------------------------------

class TestListThaijoeEvidence:

    def test_download_url_flagged_as_bad(self):
        """Row with /article/download/ URL is flagged is_download_url=True and url_ok=False."""
        rows = [_make_ev_row("EV-001", _DOWNLOAD_URL)]
        result = _run_list_endpoint(rows)

        assert result.total == 1
        assert result.bad_url_count == 1
        assert result.rows[0].is_download_url is True
        assert result.rows[0].url_ok is False

    def test_view_url_flagged_as_ok(self):
        """Row with valid /view/ID URL is flagged url_ok=True."""
        rows = [_make_ev_row("EV-002", _VALID_VIEW_URL)]
        result = _run_list_endpoint(rows)

        assert result.total == 1
        assert result.bad_url_count == 0
        assert result.rows[0].url_ok is True
        assert result.rows[0].is_download_url is False

    def test_view_with_file_segment_also_ok(self):
        """Row with /view/ID/FILEID URL is now valid (pattern updated in P02)."""
        rows = [_make_ev_row("EV-003", _VIEW_WITH_FILE)]
        result = _run_list_endpoint(rows)

        assert result.rows[0].url_ok is True
        assert result.rows[0].is_download_url is False

    def test_bad_only_filter(self):
        """bad_only=True returns only rows with bad URLs (/download/ type)."""
        rows = [
            _make_ev_row("EV-001", _DOWNLOAD_URL),
            _make_ev_row("EV-002", _VALID_VIEW_URL),
        ]
        result = _run_list_endpoint(rows, bad_only=True)

        assert result.total == 1
        assert result.rows[0].evidence_id == "EV-001"


# ---------------------------------------------------------------------------
# Tests: POST /api/thaijo/fix-evidence-urls
# ---------------------------------------------------------------------------

class TestFixEvidenceUrls:

    def test_download_url_is_fixed(self):
        """Row with /article/download/ URL → normalized to /view/, fixed count incremented."""
        execute_mock = MagicMock()
        rows = [_make_ev_row("EV-001", _DOWNLOAD_URL)]

        result = _run_fix_endpoint(rows, execute_mock)

        assert result.fixed == 1
        assert result.already_ok == 0
        # execute_db must have been called with normalized /view/ URL
        call_args = execute_mock.call_args[0]
        new_open_url = call_args[1][0]
        assert "/download/" not in new_open_url
        assert "/view/250446" in new_open_url

    def test_view_url_already_ok_not_touched(self):
        """Row with valid /view/ID URL → already_ok incremented, no DB write."""
        execute_mock = MagicMock()
        rows = [_make_ev_row("EV-002", _VALID_VIEW_URL)]

        result = _run_fix_endpoint(rows, execute_mock)

        assert result.already_ok == 1
        assert result.fixed == 0
        execute_mock.assert_not_called()

    def test_view_with_file_segment_is_normalized(self):
        """Row with /view/ID/FILEID URL → _normalize_to_view_url strips FILEID → fixed."""
        execute_mock = MagicMock()
        rows = [_make_ev_row("EV-003", _VIEW_WITH_FILE)]

        result = _run_fix_endpoint(rows, execute_mock)

        # /view/ID/FILEID normalizes to /view/ID — counted as fixed
        assert result.fixed == 1
        assert result.already_ok == 0
        call_args = execute_mock.call_args[0]
        new_open_url = call_args[1][0]
        # FILEID segment stripped
        assert "/article/view/" in new_open_url
        assert new_open_url.count("/") < _VIEW_WITH_FILE.count("/")
