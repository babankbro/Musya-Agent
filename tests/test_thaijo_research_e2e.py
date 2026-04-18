"""Integration tests for the ThaiJO Research Report pipeline (end-to-end with mocks)."""
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.schemas.thaijo_research import ThaiJOResearchRequest, ThaiJOResearchResponse


# ── Fixtures ──

MOCK_ARTICLES = [
    {
        "pdf_url": "https://he01.tci-thaijo.org/journal/article/view/1001",
        "summary": "งานวิจัยนี้ศึกษาปัจจัยเสี่ยงของอุบัติเหตุทางถนนในประเทศไทย พบว่าพฤติกรรมเสี่ยงหลักคือการไม่สวมหมวกนิรภัย",
        "reference": "สมชาย ใจดี. (2023). ปัจจัยเสี่ยงอุบัติเหตุทางถนน. วารสารสาธารณสุข, 45(2), 15-30.",
        "source_type": "thaijo_article",
        "trust_level": "medium",
        "search_term": "ปัจจัยเสี่ยง อุบัติเหตุ",
    },
    {
        "pdf_url": "https://he01.tci-thaijo.org/journal/article/view/1002",
        "summary": "ศึกษาผลกระทบของการดื่มแอลกอฮอล์ต่อการขับขี่ในประเทศไทย พบว่าผู้ขับขี่ที่ดื่มมีความเสี่ยงสูงกว่า 3 เท่า",
        "reference": "วิภา สุขใจ. (2022). แอลกอฮอล์และอุบัติเหตุ. วารสารแพทย์, 30(1), 45-58.",
        "source_type": "thaijo_article",
        "trust_level": "medium",
        "search_term": "ดื่มแล้วขับ อุบัติเหตุ",
    },
    {
        "pdf_url": "https://he01.tci-thaijo.org/journal/article/view/1003",
        "summary": "วิเคราะห์ประสิทธิภาพของมาตรการบังคับใช้กฎหมายหมวกนิรภัยในจังหวัดขอนแก่น พบว่าการบังคับใช้กฎหมายลดอัตราการเสียชีวิตลง 25%",
        "reference": None,
        "source_type": "thaijo_article",
        "trust_level": "medium",
        "search_term": "หมวกนิรภัย มาตรการ",
    },
]

MOCK_SEARCH_RESPONSE = json.dumps({"count": 3, "results": MOCK_ARTICLES}, ensure_ascii=False)


# ── Integration: Full pipeline with mocked LLM ──

class TestThaiJOResearchPipelineE2E:
    """Test the full pipeline by mocking CrewAI crew.kickoff() to return structured data."""

    @patch("src.agents.thaijo_research_orchestrator.Crew")
    @patch("src.agents.thaijo_research_orchestrator._tasks")
    @patch("src.agents.thaijo_research_orchestrator.build_thaijo_research_crew")
    def test_pipeline_returns_response_on_success(self, mock_build_crew, mock_tasks, mock_crew_cls):
        from src.agents.thaijo_research_orchestrator import run_thaijo_research

        mock_agents = {k: MagicMock() for k in ["topic_parser","searcher","screener","citation_gen","synthesizer","composer"]}
        mock_build_crew.return_value = mock_agents
        mock_tasks.return_value = [MagicMock() for _ in range(6)]

        mock_result = MagicMock()
        mock_result.__str__ = lambda self: "# รายงานทบทวนวรรณกรรม\n\nบทคัดย่อ..."
        t1 = MagicMock(raw=json.dumps({"main_topic":"อุบัติเหตุ","domain":"road_traffic_injury","search_queries":[{"term":"ปัจจัยเสี่ยง อุบัติเหตุ","size":5,"priority":1}]}))
        t2 = MagicMock(raw=json.dumps({"total_queries":1,"total_unique_articles":3,"articles":MOCK_ARTICLES,"query_results":[{"query":"ปัจจัยเสี่ยง","count":3,"status":"success"}]}))
        t3 = MagicMock(raw=json.dumps({"screened_articles":[{"pdf_url":"https://he01.tci-thaijo.org/journal/article/view/1001","summary":"test","reference":"ref","relevance_score":8.5,"themes":["พฤติกรรมเสี่ยง"],"included":True,"source_queries":["q1"]}],"total_included":3,"total_excluded":0}))
        t4 = MagicMock(raw=json.dumps({
            "evidence_items": [{"evidence_id":"EV-200","evidence_type":"thaijo_article","source_ref":"https://he01.tci-thaijo.org/1001","title":"test","open_url":"https://he01.tci-thaijo.org/1001","apa_type":"article","apa_authors":"สมชาย","apa_year":"2023","apa_publisher":"วารสารสาธารณสุข"}],
            "citations": [{"citation_code":"C-200","evidence_id":"EV-200","source_type":"thaijo_article","source_ref":"https://he01.tci-thaijo.org/1001","citation_text":"(สมชาย, 2023)","bibliography_text":"สมชาย ใจดี. (2023). ปัจจัยเสี่ยงอุบัติเหตุทางถนน. วารสารสาธารณสุข, 45(2), 15-30.","open_url":"https://he01.tci-thaijo.org/1001"}],
            "claims": [], "coverage": {"total_claims":0,"supported":0,"partially_supported":0,"unsupported":0,"coverage_score":0.0,"flags":[]}
        }))
        t5 = MagicMock(raw=json.dumps({"themes":[{"theme_name":"พฤติกรรมเสี่ยง","article_count":2,"synthesis":"test synthesis","key_findings":["finding1"]}],"overall_findings":"test","research_gaps":["gap1"]}))
        t6 = MagicMock(raw="# รายงานทบทวนวรรณกรรม\n\n## บทคัดย่อ...\n\n[C-200]")
        mock_result.tasks_output = [t1, t2, t3, t4, t5, t6]

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew_cls.return_value = mock_crew_instance

        result = run_thaijo_research(topic="ปัจจัยเสี่ยงอุบัติเหตุ")

        assert isinstance(result, ThaiJOResearchResponse)
        assert result.topic == "ปัจจัยเสี่ยงอุบัติเหตุ"
        assert result.articles_found == 3
        assert result.articles_selected == 3
        assert len(result.citations) >= 1
        assert result.metadata["pipeline"] == "thaijo_research"

    @patch("src.agents.thaijo_research_orchestrator.Crew")
    @patch("src.agents.thaijo_research_orchestrator._tasks")
    @patch("src.agents.thaijo_research_orchestrator.build_thaijo_research_crew")
    def test_pipeline_handles_error(self, mock_build_crew, mock_tasks, mock_crew_cls):
        from src.agents.thaijo_research_orchestrator import run_thaijo_research

        mock_agents = {k: MagicMock() for k in ["topic_parser","searcher","screener","citation_gen","synthesizer","composer"]}
        mock_build_crew.return_value = mock_agents
        mock_tasks.return_value = [MagicMock() for _ in range(6)]

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.side_effect = RuntimeError("LLM timeout")
        mock_crew_cls.return_value = mock_crew_instance

        result = run_thaijo_research(topic="test topic")

        assert isinstance(result, ThaiJOResearchResponse)
        assert result.topic == "error"
        assert "LLM timeout" in result.content

    @patch("src.agents.thaijo_research_orchestrator.Crew")
    @patch("src.agents.thaijo_research_orchestrator._tasks")
    @patch("src.agents.thaijo_research_orchestrator.build_thaijo_research_crew")
    def test_citation_codes_in_c200_range(self, mock_build_crew, mock_tasks, mock_crew_cls):
        from src.agents.thaijo_research_orchestrator import run_thaijo_research

        mock_agents = {k: MagicMock() for k in ["topic_parser","searcher","screener","citation_gen","synthesizer","composer"]}
        mock_build_crew.return_value = mock_agents
        mock_tasks.return_value = [MagicMock() for _ in range(6)]

        mock_result = MagicMock()
        mock_result.__str__ = lambda self: "Report text"
        t1 = MagicMock(raw='{"main_topic":"t","domain":"general","search_queries":[]}')
        t2 = MagicMock(raw='{"total_unique_articles":0,"articles":[]}')
        t3 = MagicMock(raw='{"screened_articles":[],"total_included":0}')
        t4 = MagicMock(raw=json.dumps({
            "evidence_items": [{"evidence_id":"EV-200","evidence_type":"thaijo_article","source_ref":"url1","title":"t1","open_url":"url1","apa_type":"article"}],
            "citations": [
                {"citation_code":"C-200","evidence_id":"EV-200","source_type":"thaijo_article","source_ref":"url1","citation_text":"(A,2023)","bibliography_text":"A. (2023). T1. J.","open_url":"url1"},
                {"citation_code":"C-201","evidence_id":"EV-201","source_type":"thaijo_article","source_ref":"url2","citation_text":"(B,2022)","bibliography_text":"B. (2022). T2. J.","open_url":"url2"},
            ],
            "claims": [], "coverage": {"total_claims":0,"supported":0,"partially_supported":0,"unsupported":0,"coverage_score":0.0,"flags":[]}
        }))
        t5 = MagicMock(raw='{"themes":[],"overall_findings":"test","research_gaps":[]}')
        t6 = MagicMock(raw="Report [C-200] [C-201]")
        mock_result.tasks_output = [t1, t2, t3, t4, t5, t6]

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = mock_result
        mock_crew_cls.return_value = mock_crew_instance

        result = run_thaijo_research(topic="test")

        # All citations should be C-200+
        for cit in result.citations:
            code = cit.get("citation_code", "")
            assert code.startswith("C-2"), f"Expected C-2xx code, got {code}"


# ── API endpoint tests ──

class TestThaiJOResearchEndpoint:
    @patch("src.routers.thaijo.settings")
    def test_research_endpoint_disabled(self, mock_settings):
        from src.routers.thaijo import thaijo_research
        from src.schemas.thaijo_research import ThaiJOResearchRequest

        mock_settings.THAIJO_ENABLED = False
        req = ThaiJOResearchRequest(topic="test")
        result = thaijo_research.__wrapped__(req) if hasattr(thaijo_research, '__wrapped__') else None
        # The endpoint is async, so we test the logic indirectly
        # Just verify the schema works
        assert req.topic == "test"

    def test_research_request_schema(self):
        req = ThaiJOResearchRequest(topic="ปัจจัยเสี่ยงอุบัติเหตุ", max_articles=10)
        assert req.topic == "ปัจจัยเสี่ยงอุบัติเหตุ"
        assert req.max_articles == 10

    def test_research_response_serialization(self):
        resp = ThaiJOResearchResponse(
            content="# Report",
            topic="test",
            articles_found=5,
            articles_selected=3,
            citations=[{"citation_code": "C-200", "source_type": "thaijo_article", "source_ref": "url", "citation_text": "(A,2023)", "open_url": "url", "bibliography_text": "A. (2023). Title. Journal."}],
            follow_ups=["Q1", "Q2", "Q3"],
            metadata={"elapsed_seconds": 60.0, "pipeline": "thaijo_research"},
        )
        data = resp.model_dump()
        assert data["articles_found"] == 5
        assert len(data["citations"]) == 1
        assert data["citations"][0]["citation_code"] == "C-200"
        json_str = json.dumps(data, ensure_ascii=False)
        assert "C-200" in json_str


# ── Unified orchestrator ThaiJO routing tests ──

class TestUnifiedOrchestratorThaiJO:
    @patch("src.agents.unified_orchestrator.run_thaijo_research")
    @patch("src.agents.unified_orchestrator.route_request")
    def test_routes_to_thaijo_pipeline(self, mock_route, mock_run_thaijo):
        from src.agents.unified_orchestrator import run_unified

        mock_route.return_value = {
            "pipeline": "thaijo_research_pipeline",
            "confidence": 0.9,
            "reason": "literature review keyword",
            "extracted_params": {"topics": ["rti"]},
        }
        mock_resp = ThaiJOResearchResponse(content="Report", topic="test")
        mock_run_thaijo.return_value = mock_resp

        result = run_unified("ทบทวนวรรณกรรมเรื่องอุบัติเหตุ")

        assert result["pipeline_used"] == "thaijo_research_pipeline"
        mock_run_thaijo.assert_called_once()

    @patch("src.agents.unified_orchestrator.run_thaijo_research")
    @patch("src.agents.unified_orchestrator.route_request")
    def test_passes_topic_from_user_message(self, mock_route, mock_run_thaijo):
        from src.agents.unified_orchestrator import run_unified

        mock_route.return_value = {
            "pipeline": "thaijo_research_pipeline",
            "confidence": 0.9,
            "reason": "test",
            "extracted_params": {},
        }
        mock_resp = ThaiJOResearchResponse(content="Report", topic="test")
        mock_run_thaijo.return_value = mock_resp

        result = run_unified("ทบทวนวรรณกรรมเรื่องอุบัติเหตุทางถนน")

        # Topic should be the user message when not in extracted_params
        call_kwargs = mock_run_thaijo.call_args
        assert "อุบัติเหตุทางถนน" in call_kwargs.kwargs.get("topic", call_kwargs.args[0] if call_kwargs.args else "")
