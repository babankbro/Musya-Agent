"""Retrieval Agent: fetches data from Document RAG and Database RAG."""
from crewai import Agent
from src.tools.common import search_documents, get_indicator_catalog, get_geography_profile
from src.tools.thaijo import search_thaijo
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
        goal="ค้นหาและรวบรวมข้อมูลจากเอกสาร (Document RAG), ฐานข้อมูลสถิติ (Database RAG) และงานวิจัยจาก ThaiJO อย่างครบถ้วน โดยต้องหาข้อมูลอ้างอิงและแนวทางแก้ไขเพิ่มเติมเสมอ",
        backstory=(
            "คุณเป็นผู้เชี่ยวชาญด้านการค้นคืนข้อมูลสุขภาพและงานวิจัย "
            "คุณต้องดึงข้อมูลให้ครบถ้วนทั้งเชิงปริมาณ (ตัวเลข สถิติ) และเชิงคุณภาพ (นโยบาย แนวทาง) "
            "สำคัญมาก: ในการทำ Policy Brief หรือ Analyze Report คุณ **ต้อง** ใช้เครื่องมือ search_thaijo "
            "เพื่อค้นหาหลักฐานทางวิชาการ (evidence) และแนวทางแก้ไข (solutions) จาก ThaiJO ทุกครั้ง "
            "เพื่อให้รายงานมีข้อมูลสนับสนุนที่หนักแน่นและเพียงพอจากงานวิจัยที่เกี่ยวข้อง "
            "นอกจากนี้ต้องระบุแหล่งที่มาของข้อมูลทุกรายการอย่างชัดเจน "
            "เมื่อ Request Interpreter ระบุ academic_search_needed=true ให้ทำการค้นหาจาก ThaiJO ทันที"
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
            search_thaijo,
        ],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
