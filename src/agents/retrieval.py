"""Retrieval Agent: fetches data from Document RAG and Database RAG."""
from crewai import Agent
from src.agents.agent_defaults import agent_retry_kwargs
from src.tools.common import search_documents, get_indicator_catalog, get_geography_profile
from src.tools.thaijo import search_thaijo
from src.tools.obsidian import search_obsidian
from src.tools.accident import (
    get_accident_summary,
    get_accident_hotspots,
    get_accident_time_distribution,
    get_road_condition_risk,
    get_province_year_summary,
    get_province_roads,
    get_all_provinces_ranking,
)


def create_retrieval_agent(llm, extra_tools: list | None = None, extra_backstory: str = "", include_thaijo: bool = True, include_obsidian: bool = True) -> Agent:
    tools = [
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
    ]
    if include_thaijo:
        tools.append(search_thaijo)
    if include_obsidian:
        tools.append(search_obsidian)

    if extra_tools:
        tools.extend(extra_tools)

    backstory = (
        "คุณเป็นผู้เชี่ยวชาญด้านการค้นคืนข้อมูลสุขภาพและงานวิจัย "
        "คุณต้องดึงข้อมูลให้ครบถ้วนทั้งเชิงปริมาณ (ตัวเลข สถิติ) และเชิงคุณภาพ (นโยบาย แนวทาง) "
        "สำคัญมาก: ในการทำ Policy Brief หรือ Analyze Report คุณ **ต้อง** ใช้เครื่องมือ search_thaijo "
        "เพื่อค้นหาหลักฐานทางวิชาการ (evidence) และแนวทางแก้ไข (solutions) จาก ThaiJO ทุกครั้ง "
        "เพื่อให้รายงานมีข้อมูลสนับสนุนที่หนักแน่นและเพียงพอจากงานวิจัยที่เกี่ยวข้อง "
        "นอกจากนี้ใช้ search_obsidian เพื่อค้นหาข้อมูล KPI รายอำเภอ นโยบาย และผลการตรวจราชการ "
        "จาก Obsidian Knowledge Vault เขตสุขภาพที่ 10 เมื่อคำถามเกี่ยวข้องกับข้อมูลเฉพาะพื้นที่ "
        "ต้องระบุแหล่งที่มาของข้อมูลทุกรายการอย่างชัดเจน "
        "เมื่อ Request Interpreter ระบุ academic_search_needed=true ให้ทำการค้นหาจาก ThaiJO ทันที"
    )
    if extra_backstory:
        backstory += "\n\n" + extra_backstory

    return Agent(
        role="Data Retrieval Specialist",
        goal="ค้นหาและรวบรวมข้อมูลจากเอกสาร (Document RAG), ฐานข้อมูลสถิติ (Database RAG) และงานวิจัยจาก ThaiJO อย่างครบถ้วน โดยต้องหาข้อมูลอ้างอิงและแนวทางแก้ไขเพิ่มเติมเสมอ",
        backstory=backstory,
        tools=tools,
        llm=llm,
        verbose=True,
        allow_delegation=False,
        **agent_retry_kwargs(),
    )
