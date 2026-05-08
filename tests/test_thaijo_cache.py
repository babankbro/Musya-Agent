"""Unit tests for Task 2: ThaiJO cache-first + URL validation in search_thaijo.

All tests are fully offline — they mock httpx, query_db, and execute_db.
"""
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── module-level mocks for heavy dependencies ──────────────────────────────
sys.modules.setdefault("crewai", MagicMock())
sys.modules.setdefault("crewai.tools", MagicMock())


# ── import helpers directly (no crewai dependency on helpers) ─────────────
from src.tools.thaijo import (
    _is_valid_thaijo_url,
    _normalize_term,
    _cache_key,
    _read_cache,
    _write_cache,
    _increment_hit,
    _search_thaijo_impl,
)

# ─────────────────────────────────────────────────────────────────────────────
# _is_valid_thaijo_url
# ─────────────────────────────────────────────────────────────────────────────

class TestIsValidThaijoUrl:
    def test_valid_he01_url(self):
        url = "https://he01.tci-thaijo.org/index.php/jpmat/article/view/12345"
        assert _is_valid_thaijo_url(url) is True

    def test_valid_he02_url(self):
        url = "https://he02.tci-thaijo.org/index.php/abc/article/view/99"
        assert _is_valid_thaijo_url(url) is True

    def test_valid_plain_tci_thaijo(self):
        url = "https://tci-thaijo.org/index.php/foo/article/view/1"
        assert _is_valid_thaijo_url(url) is True

    def test_empty_url_is_invalid(self):
        assert _is_valid_thaijo_url("") is False

    def test_none_url_is_invalid(self):
        assert _is_valid_thaijo_url(None) is False

    def test_hallucinated_url_is_invalid(self):
        assert _is_valid_thaijo_url("https://hallucinated-url.com/fake/123") is False

    def test_url_missing_article_view(self):
        assert _is_valid_thaijo_url("https://he01.tci-thaijo.org/index.php/foo/download/123") is False

    def test_url_with_no_article_id(self):
        assert _is_valid_thaijo_url("https://he01.tci-thaijo.org/index.php/foo/article/view/") is False

    def test_truncated_article_id_still_valid(self):
        # LLM might truncate to shorter ID but still a valid integer
        assert _is_valid_thaijo_url("https://he01.tci-thaijo.org/index.php/foo/article/view/123") is True


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_term / _cache_key
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeAndCacheKey:
    def test_normalize_strips_whitespace(self):
        assert _normalize_term("  อุบัติเหตุ  ") == "อุบัติเหตุ"

    def test_normalize_collapses_internal_spaces(self):
        assert _normalize_term("อุบัติเหตุ  ทางถนน") == "อุบัติเหตุ ทางถนน"

    def test_normalize_lowercases(self):
        assert _normalize_term("DIABETES") == "diabetes"

    def test_same_term_different_whitespace_gives_same_key(self):
        key1 = _cache_key(_normalize_term("อุบัติเหตุ"), 5)
        key2 = _cache_key(_normalize_term("  อุบัติเหตุ  "), 5)
        assert key1 == key2

    def test_different_size_gives_different_key(self):
        key5 = _cache_key("อุบัติเหตุ", 5)
        key10 = _cache_key("อุบัติเหตุ", 10)
        assert key5 != key10

    def test_cache_key_is_64_char_hex(self):
        key = _cache_key("test", 5)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ─────────────────────────────────────────────────────────────────────────────
# _read_cache / _write_cache / _increment_hit  (mocked DB)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_ARTICLES = [
    {
        "pdf_url": "https://he01.tci-thaijo.org/index.php/jpmat/article/view/12345",
        "summary": "summary text",
        "reference": "Author A. (2023). Title. Journal, 1(1), 1-10.",
        "source_type": "thaijo_article",
    }
]


class TestReadCache:
    def test_cache_miss_returns_none(self):
        with patch("src.db.pool.query_db", return_value=[]):
            result = _read_cache("nonexistent_key")
        assert result is None

    def test_cache_hit_returns_list(self):
        with patch("src.db.pool.query_db", return_value=[{"results_json": SAMPLE_ARTICLES}]):
            result = _read_cache("some_key")
        assert result == SAMPLE_ARTICLES

    def test_db_error_returns_none(self):
        with patch("src.db.pool.query_db", side_effect=Exception("DB down")):
            result = _read_cache("some_key")
        assert result is None


class TestWriteCache:
    def test_write_calls_execute_db(self):
        with patch("src.db.pool.execute_db") as mock_exec:
            _write_cache("key123", "term", "term", SAMPLE_ARTICLES, 7)
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert "INSERT INTO thaijo_search_cache" in call_args[0]

    def test_write_db_error_does_not_raise(self):
        with patch("src.db.pool.execute_db", side_effect=Exception("DB down")):
            _write_cache("key123", "term", "term", SAMPLE_ARTICLES, 7)  # should not raise


class TestIncrementHit:
    def test_increment_calls_execute_db(self):
        with patch("src.db.pool.execute_db") as mock_exec:
            _increment_hit("key123")
        mock_exec.assert_called_once()
        assert "hit_count" in mock_exec.call_args[0][0]

    def test_increment_db_error_does_not_raise(self):
        with patch("src.db.pool.execute_db", side_effect=Exception("DB down")):
            _increment_hit("key123")  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# search_thaijo integration (cache HIT/MISS, URL filter)
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchThaijoTool:
    """Test search_thaijo through its public interface."""

    def _make_api_response(self, articles):
        return {"count": len(articles), "results": articles}

    def test_invalid_url_filtered_at_tool_level(self):
        """Articles with bad pdf_url should be dropped before returning."""
        bad_article = {
            "pdf_url": "https://hallucinated.com/fake/path",
            "summary": "test",
            "reference": "Ref.",
        }
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache"), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._make_api_response([bad_article])
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("test term"))

        assert result["count"] == 0
        assert result["results"] == []

    def test_empty_url_filtered(self):
        empty_url_article = {"pdf_url": "", "summary": "test", "reference": "Ref."}
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache"), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._make_api_response([empty_url_article])
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("test term"))

        assert result["count"] == 0

    def test_cache_hit_skips_api(self):
        """Cache HIT: should return cached data without calling httpx."""
        with patch("src.tools.thaijo._read_cache", return_value=SAMPLE_ARTICLES), \
             patch("src.tools.thaijo._increment_hit") as mock_incr, \
             patch("src.tools.thaijo.httpx") as mock_httpx:

            result = json.loads(_search_thaijo_impl("อุบัติเหตุ"))

        assert result["count"] == 1
        assert result["results"] == SAMPLE_ARTICLES
        mock_httpx.Client.assert_not_called()
        mock_incr.assert_called_once()

    def test_cache_miss_calls_api_and_writes(self):
        """Cache MISS: should call API and write to cache."""
        valid_article = {
            "pdf_url": "https://he01.tci-thaijo.org/index.php/jpmat/article/view/12345",
            "summary": "summary",
            "reference": "Ref.",
        }
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache") as mock_write, \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._make_api_response([valid_article] * 5)
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("อุบัติเหตุ"))

        assert result["count"] == 5
        mock_write.assert_called_once()

    def test_normalized_whitespace_hits_same_cache(self):
        """'  term  ' and 'term' should produce the same cache key."""
        with patch("src.tools.thaijo._read_cache", return_value=SAMPLE_ARTICLES) as mock_read, \
             patch("src.tools.thaijo._increment_hit"):
            _search_thaijo_impl("  อุบัติเหตุ  ")
            _search_thaijo_impl("อุบัติเหตุ")

        call_keys = [call[0][0] for call in mock_read.call_args_list]
        assert call_keys[0] == call_keys[1]

    def test_db_error_falls_through(self):
        """DB error in cache read should not prevent tool from returning API results."""
        valid_article = {
            "pdf_url": "https://he01.tci-thaijo.org/index.php/jpmat/article/view/9999",
            "summary": "ok",
            "reference": "Ref.",
        }
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache"), \
             patch("src.db.pool.query_db", side_effect=Exception("DB down")), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._make_api_response([valid_article])
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("term"))

        assert result["count"] == 1

    def test_expired_cache_refetches(self):
        """Expired cache (MISS path) → API called → cache rewritten."""
        valid_article = {
            "pdf_url": "https://he01.tci-thaijo.org/index.php/jpmat/article/view/7777",
            "summary": "summary",
            "reference": "Ref.",
        }
        with patch("src.tools.thaijo._read_cache", return_value=None), \
             patch("src.tools.thaijo._write_cache") as mock_write, \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.json.return_value = self._make_api_response([valid_article])
            mock_resp.raise_for_status.return_value = None
            mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_resp

            result = json.loads(_search_thaijo_impl("อุบัติเหตุ"))

        assert result["count"] == 1
        mock_httpx.Client.assert_called()
        mock_write.assert_called_once()

    def test_cache_hit_during_api_outage(self):
        """Cache HIT during API outage → return cached result, never call httpx."""
        with patch("src.tools.thaijo._read_cache", return_value=SAMPLE_ARTICLES), \
             patch("src.tools.thaijo._increment_hit"), \
             patch("src.tools.thaijo.httpx") as mock_httpx:
            mock_httpx.Client.side_effect = Exception("Connection refused")

            result = json.loads(_search_thaijo_impl("อุบัติเหตุ"))

        assert result["count"] == 1
        assert result["results"] == SAMPLE_ARTICLES
        mock_httpx.Client.assert_not_called()
