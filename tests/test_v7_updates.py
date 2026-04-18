"""Test v7.1 updates: Short Chat routing auto-detection and orchestrator logic."""
import pytest
from unittest.mock import patch, MagicMock
from src.agents.request_router import route_request
from src.agents.short_chat_orchestrator import _extract_follow_ups, _extract_citations

class TestRouterAutoDetection:
    
    def test_short_message_auto_detection(self):
        # Very short message should route to short_chat
        msg = "จุดเสี่ยงอุบลฯ มีที่ไหนบ้าง"
        result = route_request(msg)
        assert result["pipeline"] == "short_chat"
        assert "Short message detected" in result["reason"]

    def test_short_message_with_report_keyword(self):
        # Short message but asks for report -> should NOT auto-route to short_chat
        msg = "ขอรายงานจุดเสี่ยงอุบลฯ"
        
        # Bypass Agent/Task/Crew creation by mocking the router entirely
        # But we want to test the logic INSIDE route_request (auto-detect check)
        # So we mock create_request_router AND Crew to return a mock result
        
        with patch('src.agents.request_router.create_request_router') as mock_create:
            with patch('src.agents.request_router.Task') as mock_task:
                with patch('src.agents.request_router.Crew') as mock_crew_class:
                    mock_crew = MagicMock()
                    mock_crew.kickoff.return_value = '{"pipeline": "chat_pipeline", "confidence": 0.9, "reason": "llm decision"}'
                    mock_crew_class.return_value = mock_crew
                    
                    result = route_request(msg)
                    assert result["pipeline"] == "chat_pipeline"

    def test_long_message_normal_routing(self):
        # Long message -> should go to LLM router
        msg = "สถิติอุบัติเหตุในจังหวัดอุบลราชธานีในช่วงเทศกาลสงกรานต์ปี 2567 ที่ผ่านมามีแนวโน้มเป็นอย่างไรเมื่อเทียบกับปีก่อนหน้า"
        
        with patch('src.agents.request_router.create_request_router') as mock_create:
            with patch('src.agents.request_router.Task') as mock_task:
                with patch('src.agents.request_router.Crew') as mock_crew_class:
                    mock_crew = MagicMock()
                    mock_crew.kickoff.return_value = '{"pipeline": "chat_pipeline", "confidence": 0.9, "reason": "llm choice"}'
                    mock_crew_class.return_value = mock_crew
                    
                    result = route_request(msg)
                    assert result["pipeline"] == "chat_pipeline"

class TestShortChatHelpers:
    
    def test_extract_follow_ups_robust(self):
        text = """
สรุปสั้น: อุบัติเหตุสูงที่อำเภอเมือง [C-200]

คำถามติดตาม:
1. สาเหตุหลักคืออะไร?
2. มีจุดเสี่ยงอื่นอีกไหมในเขต 10?
3. ต้องการรายงานเต็มหรือไม่?

> ⚠️ หมายเหตุ: อ้างอิงเบื้องต้น
"""
        follow_ups = _extract_follow_ups(text)
        assert len(follow_ups) == 3
        assert follow_ups[0] == "สาเหตุหลักคืออะไร?"
        assert "เขต 10" in follow_ups[1]

    def test_extract_citations_and_urls(self):
        text = """
บทความระบุว่าเมาแล้วขับเป็นสาเหตุหลัก [C-200]
วารสารสาธารณสุขกล่าวถึงมาตรการ [C-201]

รายการอ้างอิง:
[C-200] สมชาย, 2564, ปัจจัยเสี่ยงอุบัติเหตุ
[C-201] มานะ, 2565, วารสารการแพทย์

⚠️ หมายเหตุ: อ้างอิงเบื้องต้น
"""
        # Mock retrieval context to test URL fuzzy matching
        retrieval_context = '[{"pdf_url": "https://thaijo.org/200", "title": "ปัจจัยเสี่ยงอุบัติเหตุ"}, {"pdf_url": "https://thaijo.org/201", "title": "วารสารการแพทย์"}]'
        
        citations = _extract_citations(text, retrieval_context)
        assert len(citations) == 2
        assert citations[0].code == "C-200"
        assert citations[0].open_url == "https://thaijo.org/200"
        assert citations[1].code == "C-201"
        assert citations[1].open_url == "https://thaijo.org/201"
