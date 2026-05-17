"""Tests for Accident Chat API endpoints.

TestQuickEndpoint  — fast, no LLM (6 tests against /quick)
TestAskValidation  — schema validation (4 tests)
TestSampleData     — static endpoints (2 tests)
TestPipelineSmoke  — slow, full LLM (1 test, skip by default)
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestQuickEndpoint:
    """POST /api/accident-chat/quick — raw SQL data, no LLM."""

    def test_hotspot_roads_default(self):
        resp = client.post("/api/accident-chat/quick", json={"tool": "hotspot_roads"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], str)
        assert len(data["data"]) > 0

    def test_kpi_trend_default(self):
        resp = client.post("/api/accident-chat/quick", json={"tool": "kpi_trend"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["data"], str)
        assert len(data["data"]) > 0

    def test_fatal_timeband_default(self):
        resp = client.post("/api/accident-chat/quick", json={"tool": "fatal_timeband"})
        assert resp.status_code == 200

    def test_behavior_stats_returns_disclaimer(self):
        resp = client.post("/api/accident-chat/quick", json={"tool": "behavior_stats", "topic": "helmet"})
        assert resp.status_code == 200
        data = resp.json()
        # Must contain a data limitation disclaimer
        assert any(
            kw in data["data"]
            for kw in ["fact_accident_person", "ข้อจำกัด", "ไม่มีข้อมูล"]
        )

    def test_province_executive_summary(self):
        resp = client.post(
            "/api/accident-chat/quick",
            json={"tool": "province_executive_summary", "province": "มุกดาหาร", "year": 2024},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["data"], str)

    def test_invalid_tool_returns_400(self):
        resp = client.post("/api/accident-chat/quick", json={"tool": "nonexistent_tool"})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "unknown_tool" in detail.get("error", "")


class TestAskValidation:
    """POST /api/accident-chat/ask — schema validation (no LLM invoked)."""

    def test_empty_question_returns_400(self):
        resp = client.post(
            "/api/accident-chat/ask",
            json={"question": "   ", "province": ""},
        )
        assert resp.status_code == 400

    def test_valid_request_schema_accepted(self):
        """Schema must be accepted (200 or 500 LLM error, never 422)."""
        resp = client.post(
            "/api/accident-chat/ask",
            json={
                "question": "แนวโน้มผู้เสียชีวิต",
                "province": "อุบลราชธานี",
                "year_start": 2022,
                "year_end": 2025,
            },
        )
        assert resp.status_code in (200, 500)

    def test_default_province_empty_accepted(self):
        resp = client.post(
            "/api/accident-chat/ask",
            json={"question": "ถนนเสี่ยงที่สุด"},
        )
        assert resp.status_code in (200, 500)

    def test_missing_question_field_returns_422(self):
        resp = client.post("/api/accident-chat/ask", json={"province": "ยโสธร"})
        assert resp.status_code == 422


class TestSampleData:
    """Static/metadata endpoints — must be fast."""

    def test_provinces_returns_all_5(self):
        resp = client.get("/api/accident-chat/provinces")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["provinces"]) == 5
        assert "อุบลราชธานี" in data["provinces"]

    def test_sample_questions_returns_4_groups(self):
        resp = client.get("/api/accident-chat/sample-questions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groups"]) == 4
        total_q = sum(len(g["questions"]) for g in data["groups"])
        assert total_q == 20


@pytest.mark.slow
class TestPipelineSmoke:
    """Full 2-agent LLM pipeline smoke test — skipped by default.

    Run explicitly: pytest tests/test_accident_chat.py -m slow
    """

    def test_ask_returns_answer(self):
        resp = client.post(
            "/api/accident-chat/ask",
            json={
                "question": "แนวโน้มผู้เสียชีวิตของจังหวัดมุกดาหารในช่วง 3 ปีที่ผ่านมา",
                "province": "มุกดาหาร",
                "year_start": 2022,
                "year_end": 2024,
            },
            timeout=180,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 50
        assert "question" in data
