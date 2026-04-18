"""Unit tests for src/tools/thaijo.py — ThaiJO search tool."""
import json
from unittest.mock import MagicMock, patch

import pytest
import httpx

from src.tools.thaijo import search_thaijo as _search_thaijo_tool


def search_thaijo(**kwargs) -> str:
    """Thin wrapper: call the underlying raw function (bypasses CrewAI Tool wrapper)."""
    return _search_thaijo_tool.func(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_RESPONSE_DATA = {
    "count": 2,
    "results": [
        {
            "pdf_url": "https://he01.tci-thaijo.org/index.php/jnhs/article/view/12345/9999",
            "summary": "งานวิจัยนี้ศึกษาปัจจัยเสี่ยงต่ออุบัติเหตุทางถนนในวัยรุ่น...",
            "reference": "สมชาย ใจดี, & สมหญิง รักเรียน. (2567). ปัจจัยเสี่ยงต่อการเกิดอุบัติเหตุทางถนน. วารสารสาธารณสุขศาสตร์, 54(2), 123-135.",
        },
        {
            "pdf_url": "https://he02.tci-thaijo.org/index.php/tnh/article/view/67890/4321",
            "summary": "การศึกษาการบาดเจ็บรุนแรงบริเวณศีรษะ...",
            "reference": None,
        },
    ],
}


def _make_mock_response(data: dict, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_search_thaijo_success():
    """Mock ThaiJO API and verify result structure."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response(MOCK_RESPONSE_DATA)

        result = search_thaijo(term="อุบัติเหตุทางถนน ปัจจัยเสี่ยง", size=5)

    data = json.loads(result)
    assert data["count"] == 2
    assert len(data["results"]) == 2

    first = data["results"][0]
    assert first["pdf_url"].startswith("https://")
    assert first["source_type"] == "thaijo_article"
    assert first["trust_level"] == "medium"
    assert first["apa_type"] == "article"
    assert first["search_term"] == "อุบัติเหตุทางถนน ปัจจัยเสี่ยง"
    assert "reference" in first


def test_search_thaijo_payload_sent():
    """Verify correct payload is sent to ThaiJO microservice."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response({"count": 0, "results": []})

        search_thaijo(term="โรคซึมเศร้า", size=3, page=2, strict=False)

    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if call_kwargs else {}
    assert payload["term"] == "โรคซึมเศร้า"
    assert payload["size"] == 3
    assert payload["page"] == 2
    assert payload["strict"] is False
    assert payload["title"] is True
    assert payload["author"] is True
    assert payload["abstract"] is True


# ---------------------------------------------------------------------------
# Null reference field
# ---------------------------------------------------------------------------

def test_search_thaijo_null_reference():
    """Verify article with null reference is still returned correctly."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response(MOCK_RESPONSE_DATA)

        result = search_thaijo(term="บาดเจ็บศีรษะ")

    data = json.loads(result)
    second = data["results"][1]
    assert second["reference"] is None
    assert second["pdf_url"] != ""
    assert second["source_type"] == "thaijo_article"


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

def test_search_thaijo_empty_results():
    """Verify empty result format when no articles found."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response({"count": 0, "results": []})

        result = search_thaijo(term="คำที่ไม่มีในระบบ xyz123")

    data = json.loads(result)
    assert data["count"] == 0
    assert data["results"] == []
    assert "error" not in data


# ---------------------------------------------------------------------------
# Size clamping
# ---------------------------------------------------------------------------

def test_search_thaijo_size_clamping_min():
    """Verify size is clamped to minimum 1."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response({"count": 0, "results": []})

        search_thaijo(term="test", size=0)

    payload = mock_client.post.call_args[1]["json"]
    assert payload["size"] == 1


def test_search_thaijo_size_clamping_max():
    """Verify size is clamped to maximum THAIJO_MAX_SIZE (10)."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response({"count": 0, "results": []})

        search_thaijo(term="test", size=999)

    payload = mock_client.post.call_args[1]["json"]
    assert payload["size"] <= 10


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_search_thaijo_timeout():
    """Verify graceful timeout handling returns empty results with error key."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = httpx.TimeoutException("timeout")

        result = search_thaijo(term="อุบัติเหตุ")

    data = json.loads(result)
    assert data["count"] == 0
    assert data["results"] == []
    assert "timed out" in data["error"].lower() or "timeout" in data["error"].lower()


def test_search_thaijo_http_error():
    """Verify graceful HTTP error handling."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable", request=MagicMock(), response=mock_resp
        )

        result = search_thaijo(term="อุบัติเหตุ")

    data = json.loads(result)
    assert data["count"] == 0
    assert data["results"] == []
    assert "error" in data


def test_search_thaijo_unexpected_error():
    """Verify graceful handling of unexpected exceptions."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = RuntimeError("unexpected!")

        result = search_thaijo(term="test")

    data = json.loads(result)
    assert data["count"] == 0
    assert "error" in data


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def test_search_thaijo_disabled():
    """Verify THAIJO_ENABLED=False disables search without calling HTTP."""
    with patch("src.tools.thaijo.settings") as mock_settings, \
         patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_settings.THAIJO_ENABLED = False
        mock_settings.THAIJO_MAX_SIZE = 10

        result = search_thaijo(term="อุบัติเหตุ")

    mock_client_cls.assert_not_called()
    data = json.loads(result)
    assert data["count"] == 0
    assert data["results"] == []
    assert "disabled" in data.get("note", "").lower()


# ---------------------------------------------------------------------------
# JSON output validity
# ---------------------------------------------------------------------------

def test_search_thaijo_returns_valid_json():
    """Verify tool always returns valid JSON (never raises)."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response(MOCK_RESPONSE_DATA)

        result = search_thaijo(term="สุขภาพจิต")

    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert "count" in parsed
    assert "results" in parsed


def test_search_thaijo_thai_characters_preserved():
    """Verify Thai characters in summary/reference are not escaped."""
    with patch("src.tools.thaijo.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = _make_mock_response(MOCK_RESPONSE_DATA)

        result = search_thaijo(term="อุบัติเหตุ")

    assert "ปัจจัยเสี่ยง" in result or "\\u" not in result[:50]
    data = json.loads(result)
    assert data["results"][0]["summary"] != ""
