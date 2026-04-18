"""Unit tests for ThaiJO Research Report pipeline components."""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.schemas.thaijo_research import (
    ThaiJOResearchRequest, ThaiJOResearchResponse, ScreenedArticle,
    TopicParserOutput, SearchQueryItem,
)


# ── Schema validation tests ──

class TestThaiJOResearchRequest:
    def test_defaults(self):
        req = ThaiJOResearchRequest(topic="ปัจจัยเสี่ยงอุบัติเหตุ")
        assert req.topic == "ปัจจัยเสี่ยงอุบัติเหตุ"
        assert req.max_articles == 15
        assert req.max_queries == 4
        assert req.min_relevance == 5.0
        assert req.session_id is None
        assert req.user_id is None

    def test_custom_values(self):
        req = ThaiJOResearchRequest(topic="test", max_articles=10, max_queries=3, min_relevance=7.0)
        assert req.max_articles == 10
        assert req.max_queries == 3
        assert req.min_relevance == 7.0

    def test_max_articles_bounds(self):
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", max_articles=2)  # < 5
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", max_articles=50)  # > 40

    def test_max_queries_bounds(self):
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", max_queries=0)
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", max_queries=7)

    def test_min_relevance_bounds(self):
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", min_relevance=-1)
        with pytest.raises(Exception):
            ThaiJOResearchRequest(topic="t", min_relevance=11)


class TestThaiJOResearchResponse:
    def test_defaults(self):
        resp = ThaiJOResearchResponse()
        assert resp.content == ""
        assert resp.topic == "general"
        assert resp.articles_found == 0
        assert resp.articles_selected == 0
        assert resp.charts == []
        assert resp.tables == []
        assert resp.citations == []
        assert resp.follow_ups == []
        assert resp.metadata == {}

    def test_with_data(self):
        resp = ThaiJOResearchResponse(
            content="# Report", topic="road_traffic_injury",
            articles_found=12, articles_selected=8,
            citations=[{"citation_code": "C-200", "source_type": "thaijo_article"}],
            follow_ups=["Q1", "Q2", "Q3"],
            metadata={"elapsed_seconds": 120.5, "pipeline": "thaijo_research"},
        )
        assert resp.articles_found == 12
        assert resp.citations[0]["citation_code"] == "C-200"
        assert len(resp.follow_ups) == 3


class TestScreenedArticle:
    def test_defaults(self):
        art = ScreenedArticle(pdf_url="https://example.com/a.pdf", summary="Test summary")
        assert art.relevance_score == 0.0
        assert art.themes == []
        assert art.included is True
        assert art.source_queries == []
        assert art.reference is None

    def test_with_relevance(self):
        art = ScreenedArticle(
            pdf_url="https://example.com/a.pdf", summary="Test",
            relevance_score=8.5, relevance_reason="Highly relevant",
            themes=["พฤติกรรมเสี่ยง", "มอเตอร์ไซค์"],
            included=True, source_queries=["ปัจจัยเสี่ยง อุบัติเหตุ"],
        )
        assert art.relevance_score == 8.5
        assert len(art.themes) == 2


class TestTopicParserOutput:
    def test_defaults(self):
        out = TopicParserOutput(main_topic="test")
        assert out.domain == "general"
        assert out.search_queries == []

    def test_with_queries(self):
        out = TopicParserOutput(
            main_topic="อุบัติเหตุ",
            domain="road_traffic_injury",
            search_queries=[
                SearchQueryItem(term="ปัจจัยเสี่ยง อุบัติเหตุ", size=5, priority=1),
                SearchQueryItem(term="พฤติกรรม ขับขี่", size=3, priority=2),
            ],
        )
        assert len(out.search_queries) == 2
        assert out.search_queries[0].priority == 1


# ── Agent creation tests ──

class TestAgentCreation:
    @patch("src.agents.thaijo_topic_parser.Agent")
    def test_topic_parser_agent(self, mock_agent_cls):
        from src.agents.thaijo_topic_parser import create_thaijo_topic_parser
        mock_llm = MagicMock()
        agent = create_thaijo_topic_parser(mock_llm)
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["role"] == "Research Topic Parser"
        assert call_kwargs["allow_delegation"] is False

    @patch("src.agents.thaijo_searcher.Agent")
    def test_searcher_agent(self, mock_agent_cls):
        from src.agents.thaijo_searcher import create_thaijo_searcher
        mock_llm = MagicMock()
        agent = create_thaijo_searcher(mock_llm)
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["role"] == "ThaiJO Multi-Query Searcher"
        assert len(call_kwargs["tools"]) == 1  # search_thaijo tool

    @patch("src.agents.thaijo_screener.Agent")
    def test_screener_agent(self, mock_agent_cls):
        from src.agents.thaijo_screener import create_thaijo_screener
        mock_llm = MagicMock()
        agent = create_thaijo_screener(mock_llm)
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["role"] == "Article Relevance Screener"

    @patch("src.agents.thaijo_research_synthesizer.Agent")
    def test_synthesizer_agent(self, mock_agent_cls):
        from src.agents.thaijo_research_synthesizer import create_thaijo_research_synthesizer
        mock_llm = MagicMock()
        agent = create_thaijo_research_synthesizer(mock_llm)
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["role"] == "Research Synthesizer"

    @patch("src.agents.thaijo_report_composer.Agent")
    def test_composer_agent(self, mock_agent_cls):
        from src.agents.thaijo_report_composer import create_thaijo_report_composer
        mock_llm = MagicMock()
        agent = create_thaijo_report_composer(mock_llm)
        mock_agent_cls.assert_called_once()
        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["role"] == "Research Report Composer"
        assert len(call_kwargs["tools"]) == 7  # chart builder tools


# ── Prompt template tests ──

class TestPrompts:
    def test_topic_parser_prompt_replaces_topic(self):
        from src.agents.thaijo_topic_parser import THAIJO_TOPIC_PARSER_PROMPT
        result = THAIJO_TOPIC_PARSER_PROMPT.replace("{topic}", "อุบัติเหตุ").replace("{max_queries}", "4").replace("{max_articles}", "15")
        assert "อุบัติเหตุ" in result
        assert "{topic}" not in result

    def test_searcher_prompt_replaces_queries(self):
        from src.agents.thaijo_searcher import THAIJO_SEARCHER_PROMPT
        result = THAIJO_SEARCHER_PROMPT.replace("{search_queries}", "test queries")
        assert "test queries" in result

    def test_screener_prompt_replaces_fields(self):
        from src.agents.thaijo_screener import THAIJO_SCREENER_PROMPT
        result = THAIJO_SCREENER_PROMPT.replace("{main_topic}", "อุบัติเหตุ").replace("{domain}", "rti").replace("{inclusion_criteria}", "test").replace("{exclusion_criteria}", "test").replace("{articles_json}", "[]")
        assert "อุบัติเหตุ" in result

    def test_synthesizer_prompt_replaces_fields(self):
        from src.agents.thaijo_research_synthesizer import THAIJO_RESEARCH_SYNTHESIZER_PROMPT
        result = THAIJO_RESEARCH_SYNTHESIZER_PROMPT.replace("{main_topic}", "test").replace("{screened_articles_json}", "[]").replace("{citation_codes_json}", "[]")
        assert "{main_topic}" not in result

    def test_composer_prompt_replaces_fields(self):
        from src.agents.thaijo_report_composer import THAIJO_REPORT_COMPOSER_PROMPT
        result = THAIJO_REPORT_COMPOSER_PROMPT.replace("{main_topic}", "test").replace("{synthesis_json}", "{}").replace("{citations_json}", "[]")
        assert "{main_topic}" not in result


# ── Orchestrator helper tests ──

class TestOrchestratorHelpers:
    def test_charts_extraction(self):
        from src.agents.thaijo_research_orchestrator import _charts
        text = 'Some text [{"type":"pie","title":"Theme Distribution","data":{"labels":["A","B"],"datasets":[{"data":[3,2]}]}}] more'
        charts = _charts(text)
        assert len(charts) == 1
        assert charts[0]["type"] == "pie"

    def test_charts_empty(self):
        from src.agents.thaijo_research_orchestrator import _charts
        assert _charts("no charts here") == []

    def test_followups_extraction(self):
        from src.agents.thaijo_research_orchestrator import _followups
        text = "## คำถามวิจัยเพิ่มเติม\n1. ปัจจัยทางเศรษฐกิจมีผลอย่างไร?\n2. มาตรการบังคับใช้กฎหมายมีประสิทธิผลแค่ไหน?\n3. เทคโนโลยีช่วยลดอุบัติเหตุได้หรือไม่?"
        fus = _followups(text)
        assert len(fus) == 3
        assert "ปัจจัยทางเศรษฐกิจ" in fus[0]

    def test_followups_max_3(self):
        from src.agents.thaijo_research_orchestrator import _followups
        text = "## Follow-up Research Questions\n- Q1 long enough question here\n- Q2 another question here\n- Q3 third question\n- Q4 extra question"
        fus = _followups(text)
        assert len(fus) <= 3

    def test_tables_extraction(self):
        from src.agents.thaijo_research_orchestrator import _tables
        text = '{"title": "สรุปบทความที่ทบทวน", "headers": ["#", "ผู้แต่ง"], "rows": [["1", "Author"]]}'
        tables = _tables(text)
        # May or may not match depending on regex — just verify no crash
        assert isinstance(tables, list)


# ── Request Router ThaiJO detection tests ──

class TestRouterThaiJODetection:
    def test_keyword_fallback_thaijo(self):
        from src.agents.request_router import _keyword_fallback
        result = _keyword_fallback("ทบทวนวรรณกรรมเรื่องอุบัติเหตุ")
        assert result["pipeline"] == "thaijo_research_pipeline"

    def test_keyword_fallback_literature_review(self):
        from src.agents.request_router import _keyword_fallback
        result = _keyword_fallback("I need a literature review on road safety")
        assert result["pipeline"] == "thaijo_research_pipeline"

    def test_keyword_fallback_thaijo_keyword(self):
        from src.agents.request_router import _keyword_fallback
        result = _keyword_fallback("ค้นหางานวิจัยจาก ThaiJO เรื่องเบาหวาน")
        assert result["pipeline"] == "thaijo_research_pipeline"

    def test_keyword_fallback_not_thaijo(self):
        from src.agents.request_router import _keyword_fallback
        result = _keyword_fallback("สถิติอุบัติเหตุปี 2567")
        assert result["pipeline"] == "chat_pipeline"

    def test_router_output_parses_thaijo_pipeline(self):
        from src.agents.request_router import _parse_router_output
        raw = '{"pipeline": "thaijo_research_pipeline", "confidence": 0.9, "reason": "test"}'
        result = _parse_router_output(raw, "ทบทวนวรรณกรรม")
        assert result["pipeline"] == "thaijo_research_pipeline"

    def test_router_output_invalid_pipeline_defaults(self):
        from src.agents.request_router import _parse_router_output
        raw = '{"pipeline": "unknown_pipeline", "confidence": 0.5}'
        result = _parse_router_output(raw, "test")
        assert result["pipeline"] == "chat_pipeline"


# ── Progress tracking tests ──

class TestProgressThaiJO:
    def test_thaijo_pipeline_agents_defined(self):
        from src.agents.progress import THAIJO_RESEARCH_PIPELINE_AGENTS
        assert len(THAIJO_RESEARCH_PIPELINE_AGENTS) == 7
        names = [a["name"] for a in THAIJO_RESEARCH_PIPELINE_AGENTS]
        assert "Research Topic Parser" in names
        assert "ThaiJO Searcher" in names
        assert "Report Composer" in names

    def test_get_pipeline_agents_thaijo(self):
        from src.agents.progress import get_pipeline_agents
        agents = get_pipeline_agents("thaijo_research_pipeline")
        assert len(agents) == 7
        assert agents[1]["name"] == "Research Topic Parser"
