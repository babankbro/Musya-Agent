"""Tests for the Policy Brief report UI HTML page.

Verifies that the static HTML is served correctly and contains
the expected JS functions and DOM elements for citation rendering.
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def policy_brief_html(client):
    """Fetch the policy_brief_ui.html content once for all UI tests."""
    resp = client.get("/static/policy_brief_ui.html")
    assert resp.status_code == 200, f"UI page not served: {resp.status_code}"
    return resp.text


# ═══════════════════════════════════════════════════════════════════
# 1. Static page serving
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefUIServed:

    def test_static_page_returns_200(self, client):
        resp = client.get("/static/policy_brief_ui.html")
        assert resp.status_code == 200

    def test_static_page_is_html(self, client):
        resp = client.get("/static/policy_brief_ui.html")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_static_page_has_content(self, client):
        resp = client.get("/static/policy_brief_ui.html")
        assert len(resp.text) > 1000, "HTML page seems too short"

    def test_test_ui_page_returns_200(self, client):
        resp = client.get("/test")
        assert resp.status_code == 200

    def test_test_ui_is_html(self, client):
        resp = client.get("/test")
        assert "text/html" in resp.headers.get("content-type", "")


# ═══════════════════════════════════════════════════════════════════
# 2. Citation rendering JS functions present
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefUICitationJS:

    def test_has_render_citations_function(self, policy_brief_html):
        assert "function renderCitations" in policy_brief_html

    def test_has_post_process_inline_citations(self, policy_brief_html):
        assert "function postProcessInlineCitations" in policy_brief_html

    def test_has_citation_map_global(self, policy_brief_html):
        assert "_citationMap" in policy_brief_html

    def test_has_escape_html_function(self, policy_brief_html):
        assert "function escapeHtml" in policy_brief_html or "escapeHtml" in policy_brief_html


# ═══════════════════════════════════════════════════════════════════
# 3. open_url / 🔗 icon link rendering in citations
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefUICitationLinkIcon:

    def test_open_url_field_referenced(self, policy_brief_html):
        assert "open_url" in policy_brief_html

    def test_link_icon_rendered_when_open_url_present(self, policy_brief_html):
        assert "🔗" in policy_brief_html

    def test_link_opens_in_new_tab(self, policy_brief_html):
        assert 'target="_blank"' in policy_brief_html

    def test_link_has_rel_noopener(self, policy_brief_html):
        assert 'rel="noopener"' in policy_brief_html

    def test_link_uses_open_url_as_href(self, policy_brief_html):
        assert "c.open_url" in policy_brief_html or "${c.open_url}" in policy_brief_html

    def test_link_has_thai_tooltip(self, policy_brief_html):
        assert "เปิด" in policy_brief_html


# ═══════════════════════════════════════════════════════════════════
# 4. Required DOM elements present
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefUIDomElements:

    def test_has_citations_content_element(self, policy_brief_html):
        assert 'id="citations-content"' in policy_brief_html

    def test_has_citation_count_element(self, policy_brief_html):
        assert 'id="citation-count"' in policy_brief_html

    def test_has_brief_content_element(self, policy_brief_html):
        assert 'id="brief-content"' in policy_brief_html

    def test_has_rti_content_element(self, policy_brief_html):
        assert 'id="rti-content"' in policy_brief_html

    def test_has_result_citations_tab(self, policy_brief_html):
        assert 'id="result-citations"' in policy_brief_html

    def test_has_province_selector(self, policy_brief_html):
        assert "province" in policy_brief_html.lower()

    def test_has_api_policy_brief_endpoint(self, policy_brief_html):
        assert "/api/policy-brief" in policy_brief_html


# ═══════════════════════════════════════════════════════════════════
# 5. Inline [C-xxx] tooltip rendering
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefUIInlineCitations:

    def test_inline_citation_pattern_handled(self, policy_brief_html):
        assert r"C-(\d{3})" in policy_brief_html or "C-" in policy_brief_html

    def test_tooltip_span_generated(self, policy_brief_html):
        assert "citation-tooltip" in policy_brief_html or "citation_tooltip" in policy_brief_html

    def test_inline_citation_clickable(self, policy_brief_html):
        assert "window.open" in policy_brief_html
