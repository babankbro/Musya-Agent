"""API integration tests for Zone 10 Accident Policy endpoints.

TestDataEndpoint  — fast, no LLM (6 tests)
TestPolicyRequest — schema validation (4 tests)
TestPipelineSmoke — slow, full LLM pipeline (1 test, skip by default)
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestDataEndpoint:
    """GET /api/accident-policy/zone10/data — no LLM, must be fast."""

    def test_default_returns_200(self):
        resp = client.get("/api/accident-policy/zone10/data")
        assert resp.status_code == 200

    def test_response_has_all_7_questions(self):
        resp = client.get("/api/accident-policy/zone10/data")
        data = resp.json()
        questions = data["questions"]
        expected_keys = {
            "Q1_hotspot_roads",
            "Q2_time_bands",
            "Q3_motorcycle_severity",
            "Q4_car_injuries",
            "Q5_environment_risk",
            "Q6_yearly_kpi",
            "Q7_monthly_risk",
        }
        assert set(questions.keys()) == expected_keys

    def test_response_has_zone_field(self):
        resp = client.get("/api/accident-policy/zone10/data")
        data = resp.json()
        assert data["zone"] == "เขตสุขภาพที่ 10"

    def test_all_questions_are_non_empty_strings(self):
        resp = client.get("/api/accident-policy/zone10/data")
        questions = resp.json()["questions"]
        for key, value in questions.items():
            assert isinstance(value, str) and len(value) > 0, f"{key} is empty"

    def test_no_errors_for_all_provinces(self):
        resp = client.get("/api/accident-policy/zone10/data")
        data = resp.json()
        assert data.get("errors", {}) == {}

    def test_single_province_filter(self):
        resp = client.get("/api/accident-policy/zone10/data?provinces=อุบลราชธานี")
        assert resp.status_code == 200
        data = resp.json()
        assert "อุบลราชธานี" in data["provinces"]

    def test_invalid_province_returns_400(self):
        resp = client.get("/api/accident-policy/zone10/data?provinces=กรุงเทพมหานคร")
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid_provinces"

    def test_multiple_province_filter(self):
        resp = client.get("/api/accident-policy/zone10/data?provinces=ยโสธร,อำนาจเจริญ,มุกดาหาร")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["provinces"]) == 3


class TestPolicyRequest:
    """POST /api/accident-policy/zone10 — schema validation (fast, no LLM calls)."""

    def test_empty_body_uses_defaults(self):
        resp = client.post("/api/accident-policy/zone10", json={})
        # Either 200 (success) or 500 (LLM error without key) — not 422
        assert resp.status_code in (200, 500)

    def test_invalid_province_returns_422(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={"provinces": ["กรุงเทพมหานคร"]},
        )
        assert resp.status_code == 422

    def test_invalid_year_range_order_returns_422(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={"provinces": ["อุบลราชธานี"], "year_range": [2026, 2021]},
        )
        assert resp.status_code == 422

    def test_year_range_wrong_length_returns_422(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={"provinces": ["อุบลราชธานี"], "year_range": [2021]},
        )
        assert resp.status_code == 422

    def test_invalid_question_id_returns_422(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={"provinces": ["อุบลราชธานี"], "questions": ["Q99"]},
        )
        assert resp.status_code == 422

    def test_valid_subset_questions_accepted(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={
                "provinces": ["ยโสธร", "อำนาจเจริญ"],
                "questions": ["Q1", "Q6"],
                "year_range": [2022, 2025],
            },
        )
        # Schema accepted — may be 200 or 500 (LLM), not 422
        assert resp.status_code in (200, 500)


@pytest.mark.slow
class TestPipelineSmoke:
    """Full LLM pipeline smoke test — excluded from default runs.

    Run explicitly: pytest tests/test_accident_policy_api.py -m slow
    """

    def test_full_pipeline_returns_policy_brief(self):
        resp = client.post(
            "/api/accident-policy/zone10",
            json={
                "provinces": ["ยโสธร"],
                "questions": ["Q1", "Q6"],
                "year_range": [2023, 2025],
            },
            timeout=300,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "policy_brief" in data
        assert len(data["policy_brief"]) > 100
        assert data["zone"] == "เขตสุขภาพที่ 10"
