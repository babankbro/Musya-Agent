"""Test orchestrator helper functions (without calling full CrewAI pipeline)."""
import pytest
from src.agents.orchestrator import _extract_follow_ups, _parse_crew_result, build_crew


class TestExtractFollowUps:

    def test_extracts_thai_follow_ups(self):
        text = """
## สรุป
รายงานอุบัติเหตุ...

## คำถามติดตาม
1. อัตราการเกิดอุบัติเหตุในแต่ละจังหวัดเป็นอย่างไร?
2. มาตรการป้องกันอุบัติเหตุที่ได้ผลมากที่สุดคืออะไร?
3. แนวโน้มอุบัติเหตุในปี 2025 เป็นอย่างไร?
"""
        follow_ups = _extract_follow_ups(text)
        assert len(follow_ups) == 3
        assert "จังหวัด" in follow_ups[0]

    def test_extracts_bulleted_follow_ups(self):
        text = """
สรุปข้อมูล...

คำถามต่อ:
- แนวโน้มอุบัติเหตุเป็นอย่างไร?
- พื้นที่ไหนมีความเสี่ยงสูงสุด?
- ควรมีมาตรการอะไรเพิ่มเติม?
"""
        follow_ups = _extract_follow_ups(text)
        assert len(follow_ups) == 3

    def test_returns_empty_when_no_follow_ups(self):
        text = "รายงานสั้นๆ ไม่มีคำถามติดตาม"
        follow_ups = _extract_follow_ups(text)
        assert follow_ups == []

    def test_max_three_follow_ups(self):
        text = """
คำถามติดตาม:
1. คำถามที่ 1?
2. คำถามที่ 2?
3. คำถามที่ 3?
4. คำถามที่ 4?
5. คำถามที่ 5?
"""
        follow_ups = _extract_follow_ups(text)
        assert len(follow_ups) <= 3


class TestParseCrewResult:

    def test_parse_basic_result(self):
        class MockResult:
            def __str__(self):
                return "รายงานอุบัติเหตุทางถนน\n\nคำถามติดตาม\n1. สาเหตุหลักคืออะไร?"

        resp = _parse_crew_result(MockResult(), 5.0)
        assert resp.content == str(MockResult())
        assert resp.topic == "accident"
        assert resp.metadata["elapsed_seconds"] == 5.0
        assert resp.metadata["agent_count"] == 9
        assert len(resp.follow_ups) >= 1


class TestBuildCrew:

    def test_build_crew_returns_agents_dict(self):
        agents = build_crew()
        assert isinstance(agents, dict)
        assert "interpreter" in agents
        assert "retriever" in agents
        assert "analyst" in agents
        assert "writer" in agents
