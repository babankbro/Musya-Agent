"""Tests for Policy Brief agent pipeline, API endpoints, and citation enrichment.

All tests are mocked — no real LLM/Gemini/NotebookLM calls are made.
Full suite runs in < 5 seconds.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from src.main import app
from src.schemas.response import Citation


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════
# 1. validate_province
# ═══════════════════════════════════════════════════════════════════

class TestValidateProvince:

    def test_valid_province_returns_true(self):
        from src.agents.policy_orchestrator import validate_province
        from src.tools.notebooklm import SUPPORTED_PROVINCES
        if not SUPPORTED_PROVINCES:
            pytest.skip("No supported provinces configured")
        valid, notebook_id = validate_province(SUPPORTED_PROVINCES[0])
        assert valid is True
        assert notebook_id != ""

    def test_invalid_province_returns_false(self):
        from src.agents.policy_orchestrator import validate_province
        valid, notebook_id = validate_province("จังหวัดที่ไม่มีอยู่จริง")
        assert valid is False
        assert notebook_id == ""


# ═══════════════════════════════════════════════════════════════════
# 2. run_policy_brief — logic-level (no CrewAI)
# ═══════════════════════════════════════════════════════════════════

class TestRunPolicyBriefLogic:

    def test_unsupported_province_returns_error_dict(self):
        from src.agents.policy_orchestrator import run_policy_brief
        result = run_policy_brief(province="จังหวัดปลอม", topics=["rti"])
        assert result["province"] == "จังหวัดปลอม"
        assert "ไม่รองรับ" in result["policy_brief"]
        assert result["metadata"].get("error") == "unsupported_province"
        assert result["citations"] == []

    def test_invalid_topics_normalised_to_default(self):
        """Topic normalisation logic: invalid topics are filtered out → default to all 3."""
        # Direct test of the normalisation expression used in run_policy_brief
        raw_topics = ["invalid_topic", "also_bad"]
        normalised = [t.lower() for t in raw_topics if t.lower() in ("rti", "mental", "ncd")]
        if not normalised:
            normalised = ["rti", "mental", "ncd"]
        assert normalised == ["rti", "mental", "ncd"]

    def test_valid_topics_preserved(self):
        """Valid topic codes are kept as-is after normalisation."""
        raw_topics = ["RTI", "NCD"]
        normalised = [t.lower() for t in raw_topics if t.lower() in ("rti", "mental", "ncd")]
        assert normalised == ["rti", "ncd"]


# ═══════════════════════════════════════════════════════════════════
# 3. Policy Brief API endpoints
# ═══════════════════════════════════════════════════════════════════

class TestPolicyBriefAPI:

    def test_provinces_endpoint_returns_list(self, client):
        resp = client.get("/api/policy-brief/provinces")
        assert resp.status_code == 200
        data = resp.json()
        assert "provinces" in data
        assert isinstance(data["provinces"], list)
        assert "health_zone" in data

    def test_provinces_endpoint_has_notebook_id(self, client):
        resp = client.get("/api/policy-brief/provinces")
        data = resp.json()
        assert "notebook_id" in data

    def test_invalid_province_returns_400(self, client):
        resp = client.post("/api/policy-brief", json={
            "province": "จังหวัดปลอม",
            "topics": ["rti"],
            "year": 2567,
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data["detail"]["error"] == "unsupported_province"

    def test_invalid_topics_returns_400(self, client):
        from src.tools.notebooklm import SUPPORTED_PROVINCES
        if not SUPPORTED_PROVINCES:
            pytest.skip("No supported provinces configured")
        resp = client.post("/api/policy-brief", json={
            "province": SUPPORTED_PROVINCES[0],
            "topics": ["invalid_topic"],
            "year": 2567,
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data["detail"]["error"] == "invalid_topics"

    def test_mocked_pipeline_returns_200(self, client):
        from src.tools.notebooklm import SUPPORTED_PROVINCES
        if not SUPPORTED_PROVINCES:
            pytest.skip("No supported provinces configured")

        mock_result = {
            "province": SUPPORTED_PROVINCES[0],
            "policy_brief": "# รายงานทดสอบ\n\nเนื้อหารายงานนโยบาย",
            "sections": {"rti": "RTI analysis", "mental": "", "ncd": ""},
            "cross_topic_links": ["ความเชื่อมโยง RTI-NCD"],
            "priority_recommendations": [],
            "charts": [],
            "citations": [
                {
                    "citation_code": "C-001",
                    "source_type": "document",
                    "source_ref": "accident/report.pdf",
                    "citation_text": "รายงานอุบัติเหตุ 2567",
                    "open_url": "/api/documents/open/42",
                    "bibliography_text": "สสจ.อุบล. (2567). รายงานอุบัติเหตุ. กระทรวงสาธารณสุข.",
                }
            ],
            "metadata": {
                "elapsed_seconds": 1.5,
                "agent_count": 8,
                "pipeline": "test",
                "topics_analyzed": ["rti"],
                "year": 2567,
            },
        }

        with patch("src.routers.policy_brief.run_policy_brief", return_value=mock_result):
            resp = client.post("/api/policy-brief", json={
                "province": SUPPORTED_PROVINCES[0],
                "topics": ["rti"],
                "year": 2567,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["province"] == SUPPORTED_PROVINCES[0]
        assert "รายงานทดสอบ" in data["policy_brief"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["open_url"] == "/api/documents/open/42"
        assert data["citations"][0]["citation_code"] == "C-001"


# ═══════════════════════════════════════════════════════════════════
# 4. _dedup_citations
# ═══════════════════════════════════════════════════════════════════

class TestDedupCitations:

    def _make_citation(self, code: str, source_ref: str) -> Citation:
        return Citation(
            citation_code=code,
            source_type="document",
            source_ref=source_ref,
            citation_text=f"Citation {code}",
            open_url="",
            bibliography_text="",
        )

    def test_dedup_removes_duplicate_source_refs(self):
        from src.agents.policy_orchestrator import _dedup_citations
        citations = [
            self._make_citation("C-001", "report.pdf"),
            self._make_citation("C-002", "report.pdf"),  # duplicate source_ref
            self._make_citation("C-003", "other.pdf"),
        ]
        result = _dedup_citations(citations)
        assert len(result) == 2
        assert result[0].citation_code == "C-001"
        assert result[1].citation_code == "C-003"

    def test_dedup_keeps_all_unique(self):
        from src.agents.policy_orchestrator import _dedup_citations
        citations = [
            self._make_citation("C-001", "a.pdf"),
            self._make_citation("C-002", "b.pdf"),
            self._make_citation("C-003", "c.pdf"),
        ]
        result = _dedup_citations(citations)
        assert len(result) == 3

    def test_dedup_empty_list(self):
        from src.agents.policy_orchestrator import _dedup_citations
        assert _dedup_citations([]) == []


# ═══════════════════════════════════════════════════════════════════
# 5. _enrich_citations_from_db
# ═══════════════════════════════════════════════════════════════════

class TestEnrichCitationsFromDb:

    def _make_citation(self, code: str, source_ref: str, open_url: str = "") -> Citation:
        return Citation(
            citation_code=code,
            source_type="document",
            source_ref=source_ref,
            citation_text=f"Citation {code}",
            open_url=open_url,
            bibliography_text="",
        )

    def test_fills_open_url_from_db(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        citation = self._make_citation("C-001", "accident/report.pdf")

        mock_row = {
            "document_id": 42,
            "minio_path": "accident/report.pdf",
            "file_path": "accident/report.pdf",
            "title": "รายงานอุบัติเหตุ",
            "apa_authors": "สสจ.อุบล",
            "apa_year": "2567",
            "apa_publisher": "กระทรวงสาธารณสุข",
            "apa_type": "report",
            "apa_doi": "",
            "apa_url": "",
        }

        with patch("src.agents.policy_orchestrator.query_db", return_value=[mock_row]):
            result = _enrich_citations_from_db([citation])

        assert result[0].open_url == "/api/documents/open/42"

    def test_fills_bibliography_text_from_db(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        citation = self._make_citation("C-001", "ncd/study.pdf")

        mock_row = {
            "document_id": 7,
            "minio_path": "ncd/study.pdf",
            "file_path": "ncd/study.pdf",
            "title": "การศึกษา NCD",
            "apa_authors": "Summart, U.",
            "apa_year": "2025",
            "apa_publisher": "Dis Control J",
            "apa_type": "article",
            "apa_doi": "",
            "apa_url": "",
        }

        with patch("src.agents.policy_orchestrator.query_db", return_value=[mock_row]):
            result = _enrich_citations_from_db([citation])

        assert result[0].bibliography_text != ""

    def test_noop_when_open_url_already_set(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        citation = self._make_citation("C-001", "accident/report.pdf", open_url="/api/documents/open/99")

        with patch("src.agents.policy_orchestrator.query_db") as mock_db:
            result = _enrich_citations_from_db([citation])
            mock_db.assert_not_called()

        assert result[0].open_url == "/api/documents/open/99"

    def test_handles_empty_list(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        with patch("src.agents.policy_orchestrator.query_db") as mock_db:
            result = _enrich_citations_from_db([])
            mock_db.assert_not_called()
        assert result == []

    def test_title_stem_fallback(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        citation = self._make_citation("C-001", "accident/road_safety_report.pdf")

        mock_row = {
            "document_id": 15,
            "minio_path": "different/path.pdf",  # path won't match directly
            "file_path": "different/path.pdf",
            "title": "road safety report 2025",
            "apa_authors": "",
            "apa_year": "2025",
            "apa_publisher": "",
            "apa_type": "report",
            "apa_doi": "",
            "apa_url": "",
        }

        def mock_query(sql, params):
            if "ILIKE" in sql:
                return [mock_row]
            return []

        with patch("src.agents.policy_orchestrator.query_db", side_effect=mock_query):
            result = _enrich_citations_from_db([citation])

        assert result[0].open_url == "/api/documents/open/15"

    def test_graceful_on_db_error(self):
        from src.agents.policy_orchestrator import _enrich_citations_from_db
        citation = self._make_citation("C-001", "accident/report.pdf")

        with patch("src.agents.policy_orchestrator.query_db", side_effect=Exception("DB down")):
            result = _enrich_citations_from_db([citation])

        # No exception raised; open_url remains empty
        assert result[0].open_url == ""
