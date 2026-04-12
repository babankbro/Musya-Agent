"""Retrieval Agent: fetches data from Document RAG and Database RAG."""
from crewai import Agent
from src.tools.common import search_documents, get_indicator_catalog, get_geography_profile
from src.tools.accident import (
    get_accident_summary,
    get_accident_hotspots,
    get_accident_time_distribution,
    get_road_condition_risk,
    get_province_year_summary,
    get_province_roads,
    get_all_provinces_ranking,
)


def create_retrieval_agent(llm) -> Agent:
    return Agent(
        role="Data Retrieval Specialist",
        goal="ค้นหาและรวบรวมข้อมูลจากทั้งเอกสาร (Document RAG) และฐานข้อมูลสุขภาพ (Database RAG) อย่างครบถ้วน",
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการค้นคืนข้อมูลสุขภาพ "
            "คุณสามารถค้นข้อมูลจากเอกสารนโยบาย รายงานวิชาการ และฐานข้อมูลสถิติได้ "
            "คุณต้องดึงข้อมูลให้ครบถ้วนทั้งเชิงปริมาณ (ตัวเลข สถิติ) และเชิงคุณภาพ (นโยบาย แนวทาง) "
            "โดยต้องระบุแหล่งที่มาของข้อมูลทุกรายการ"
        ),
        tools=[
            search_documents,
            get_indicator_catalog,
            get_geography_profile,
            get_province_year_summary,
            get_province_roads,
            get_all_provinces_ranking,
            get_accident_summary,
            get_accident_hotspots,
            get_accident_time_distribution,
            get_road_condition_risk,
        ],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
