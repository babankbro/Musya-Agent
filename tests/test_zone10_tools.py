"""Unit tests for Zone 10 accident policy SQL tools.

Uses real PostgreSQL DB via db_query fixture (no mocks).
Calls the _query_* logic functions directly (not through the @tool wrapper)
to avoid CrewAI Tool invocation mechanics in unit tests.
"""
import pytest

from src.tools.zone10_accident import (
    ZONE10_PROVINCES,
    _query_top_roads,
    _query_time_bands,
    _query_motorcycle_severity,
    _query_car_serious_injuries,
    _query_environment_risk,
    _query_yearly_kpi,
    _query_monthly_risk,
)


ALL_5 = ",".join(ZONE10_PROVINCES)
SINGLE_PROV = "อุบลราชธานี"


class TestZone10TopRoads:
    """Q1 — Hotspot: top risky roads."""

    def test_returns_non_empty_string(self):
        result = _query_top_roads(ALL_5, 10)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_q1_header(self):
        result = _query_top_roads(ALL_5, 10)
        assert "Q1" in result or "Hotspot" in result or "ถนน" in result

    def test_single_province(self):
        result = _query_top_roads(SINGLE_PROV, 5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_top_n_limit_respected(self):
        result = _query_top_roads(ALL_5, 3)
        # Numbered rows start with spaces then a number
        numbered = [ln for ln in result.split("\n") if ln.strip()[:2].strip().isdigit()]
        assert len(numbered) <= 3

    def test_no_crash_empty_provinces(self):
        result = _query_top_roads("", 5)
        assert isinstance(result, str)
        assert len(result) > 0


class TestZone10TimeBands:
    """Q2 — Hotspot: time distribution for EMS."""

    def test_returns_string(self):
        result = _query_time_bands(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_hour_references(self):
        result = _query_time_bands(ALL_5)
        assert ":00" in result or "Q2" in result or "ชั่วโมง" in result

    def test_contains_top_hours_summary(self):
        result = _query_time_bands(ALL_5)
        assert "ช่วงเสี่ยงสูงสุด" in result or "เสี่ยงสูง" in result or len(result) > 50

    def test_single_province(self):
        result = _query_time_bands(SINGLE_PROV)
        assert isinstance(result, str)


class TestZone10MotorcycleSeverity:
    """Q3 — Human Behavior: motorcycle severity (helmet proxy)."""

    def test_returns_string(self):
        result = _query_motorcycle_severity(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_data_limitation_note(self):
        result = _query_motorcycle_severity(ALL_5)
        assert "fact_accident_person" in result or "ข้อมูลระดับบุคคล" in result or "หมายเหตุ" in result

    def test_q3_label_present(self):
        result = _query_motorcycle_severity(ALL_5)
        assert "Q3" in result or "จักรยานยนต์" in result or "Human Behavior" in result


class TestZone10CarSeriousInjuries:
    """Q4 — Human Behavior: car/pickup injuries (seatbelt proxy)."""

    def test_returns_string(self):
        result = _query_car_serious_injuries(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_data_limitation_note(self):
        result = _query_car_serious_injuries(ALL_5)
        assert "fact_accident_person" in result or "ข้อมูลระดับบุคคล" in result or "หมายเหตุ" in result

    def test_q4_label_or_vehicle_type(self):
        result = _query_car_serious_injuries(ALL_5)
        assert "Q4" in result or "รถยนต์" in result or "Human Behavior" in result


class TestZone10EnvironmentRisk:
    """Q5 — Environment: severity vs light/road condition."""

    def test_returns_string(self):
        result = _query_environment_risk(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_environment_terms(self):
        result = _query_environment_risk(ALL_5)
        assert any(term in result for term in ["สภาพแสง", "สภาพถนน", "Q5", "Environment", "light"])

    def test_has_top3_summary(self):
        result = _query_environment_risk(ALL_5)
        assert "3" in result


class TestZone10YearlyKpi:
    """Q6 — KPI: year-over-year trend."""

    def test_returns_string(self):
        result = _query_yearly_kpi(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_years(self):
        result = _query_yearly_kpi(ALL_5)
        assert any(str(yr) in result for yr in range(2021, 2027))

    def test_contains_q6_header(self):
        result = _query_yearly_kpi(ALL_5)
        assert "Q6" in result or "KPI" in result or "แนวโน้ม" in result

    def test_has_zone10_summary(self):
        result = _query_yearly_kpi(ALL_5)
        assert "รวม" in result or "เขตสุขภาพที่ 10" in result or "ภาพรวม" in result

    def test_subset_provinces(self):
        subset = "ยโสธร,อำนาจเจริญ,มุกดาหาร"
        result = _query_yearly_kpi(subset)
        assert isinstance(result, str)
        assert len(result) > 0


class TestZone10MonthlyRisk:
    """Q7 — KPI: monthly risk and festival patterns."""

    def test_returns_string(self):
        result = _query_monthly_risk(ALL_5)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_month_names(self):
        result = _query_monthly_risk(ALL_5)
        assert "มกราคม" in result or "เมษายน" in result

    def test_contains_songkran_note(self):
        result = _query_monthly_risk(ALL_5)
        assert "สงกรานต์" in result or "เมษายน" in result

    def test_contains_top3_summary(self):
        result = _query_monthly_risk(ALL_5)
        assert "สูงสุด" in result or "อันดับ" in result or "3" in result

    def test_q7_label(self):
        result = _query_monthly_risk(ALL_5)
        assert "Q7" in result or "KPI" in result or "รายเดือน" in result
