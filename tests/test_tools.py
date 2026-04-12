"""Test Agent RAG tools — accident domain and common tools."""
import pytest


class TestAccidentTools:
    """Test accident domain database RAG tools."""

    def test_get_accident_summary_returns_data(self):
        from src.tools.accident import get_accident_summary
        result = get_accident_summary.run()
        assert isinstance(result, str)
        assert "ไม่พบ" not in result, f"Should find data, got: {result[:200]}"
        assert "อุบัติเหตุ" in result

    def test_get_accident_summary_with_date_filter(self):
        from src.tools.accident import get_accident_summary
        result = get_accident_summary.run(
            start_date="2024-01-01", end_date="2024-12-31"
        )
        assert isinstance(result, str)
        assert "อุบัติเหตุ" in result or "ไม่พบ" in result

    def test_get_accident_hotspots_returns_data(self):
        from src.tools.accident import get_accident_hotspots
        result = get_accident_hotspots.run(top_n=5)
        assert isinstance(result, str)
        assert "ไม่พบ" not in result, f"Should find hotspots, got: {result[:200]}"
        assert "คะแนนเสี่ยง" in result

    def test_get_accident_time_distribution(self):
        from src.tools.accident import get_accident_time_distribution
        result = get_accident_time_distribution.run()
        assert isinstance(result, str)
        assert "ไม่พบ" not in result, f"Should find time data, got: {result[:200]}"
        assert "อุบัติเหตุ" in result

    def test_get_road_condition_risk(self):
        from src.tools.accident import get_road_condition_risk
        result = get_road_condition_risk.run()
        assert isinstance(result, str)
        assert "ไม่พบ" not in result, f"Should find road risk data, got: {result[:200]}"
        assert "สภาพถนน" in result or "อุบัติเหตุ" in result


class TestCommonTools:
    """Test common shared tools."""

    def test_get_geography_profile_bangkok(self):
        from src.tools.common import get_geography_profile
        result = get_geography_profile.run(province_name="กรุงเทพ")
        assert isinstance(result, str)
        assert "ไม่พบ" not in result, f"Should find Bangkok, got: {result[:200]}"
        assert "กรุงเทพ" in result

    def test_get_geography_profile_chiangmai(self):
        from src.tools.common import get_geography_profile
        result = get_geography_profile.run(province_name="เชียงใหม่")
        assert isinstance(result, str)
        assert "เชียงใหม่" in result

    def test_get_geography_profile_nonexistent(self):
        from src.tools.common import get_geography_profile
        result = get_geography_profile.run(province_name="ไม่มีจังหวัดนี้xyz")
        assert "ไม่พบ" in result

    def test_search_documents_returns_string(self):
        from src.tools.common import search_documents
        result = search_documents.run(topic="accident", keywords="อุบัติเหตุ")
        assert isinstance(result, str)
        # May return "ไม่พบเอกสาร" if no docs ingested yet — that's ok

    def test_get_indicator_catalog(self):
        from src.tools.common import get_indicator_catalog
        result = get_indicator_catalog.run(topic="accident")
        assert isinstance(result, str)
        # May be empty if no indicators seeded
