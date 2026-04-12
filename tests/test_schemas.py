"""Test Pydantic schemas for request/response validation."""
import pytest
from src.schemas.request import ChatRequest, ReportRequest
from src.schemas.response import AgentResponse, ChartSpec, TableSpec, Citation


class TestChatRequest:

    def test_valid_request(self):
        req = ChatRequest(message="สรุปอุบัติเหตุ")
        assert req.message == "สรุปอุบัติเหตุ"
        assert req.session_id is None
        assert req.user_id is None

    def test_with_session(self):
        req = ChatRequest(message="test", session_id="s123", user_id="u1")
        assert req.session_id == "s123"
        assert req.user_id == "u1"

    def test_empty_message_fails(self):
        with pytest.raises(Exception):
            ChatRequest()


class TestReportRequest:

    def test_defaults(self):
        req = ReportRequest(topic="accident")
        assert req.topic == "accident"
        assert req.geography == ""
        assert req.report_type == "health_plan"
        assert req.focus_areas == []


class TestAgentResponse:

    def test_minimal_response(self):
        resp = AgentResponse(content="Hello")
        assert resp.content == "Hello"
        assert resp.topic == "general"
        assert resp.charts == []
        assert resp.tables == []
        assert resp.citations == []
        assert resp.follow_ups == []

    def test_full_response(self):
        resp = AgentResponse(
            content="รายงานอุบัติเหตุ",
            topic="accident",
            charts=[ChartSpec(chart_type="bar", title="อุบัติเหตุรายเดือน")],
            tables=[TableSpec(table_name="สรุป", columns=["เดือน", "จำนวน"], rows=[["ม.ค.", 10]])],
            citations=[Citation(citation_code="C-001", source_type="database", source_ref="mart_accident_summary")],
            follow_ups=["คำถามติดตาม 1", "คำถามติดตาม 2"],
            metadata={"elapsed_seconds": 5.0},
        )
        assert resp.topic == "accident"
        assert len(resp.charts) == 1
        assert resp.charts[0].chart_type == "bar"
        assert len(resp.tables) == 1
        assert resp.tables[0].rows[0][1] == 10
        assert len(resp.citations) == 1
        assert len(resp.follow_ups) == 2


class TestChartSpec:

    def test_chart_spec(self):
        chart = ChartSpec(chart_type="line", title="Trend")
        assert chart.x_label == ""
        assert chart.data == {}


class TestTableSpec:

    def test_table_spec(self):
        table = TableSpec(table_name="T1", columns=["A", "B"], rows=[[1, 2]])
        assert len(table.columns) == 2
        assert table.rows[0] == [1, 2]
