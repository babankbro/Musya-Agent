"""Shared Foundation — agents 1-4 reused by both Chat and Policy Brief pipelines.

Provides factory functions for the 4 shared agents and their tasks:
  1. Request Interpreter — parse user intent
  2. Data Retrieval — fetch data (Document RAG + DB + optional NLM)
  3. SQL Specialist — complex queries, chart-ready data
  4. Citation & Evidence — normalize evidence, APA citations

Usage:
    agents = build_foundation_agents(llm, include_nlm=False, include_thaijo=True, mode='full')
    tasks  = build_foundation_tasks(agents, user_message, mode='full', ...)
"""
import logging

from crewai import Agent, Task

from src.agents.request_interpreter import create_request_interpreter, REQUEST_INTERPRETER_PROMPT
from src.agents.retrieval import create_retrieval_agent
from src.agents.sql_specialist import create_sql_specialist
from src.agents.citation_evidence import (
    create_citation_evidence_agent,
    CITATION_EVIDENCE_PROMPT,
)

logger = logging.getLogger(__name__)

# Foundation agent names for progress tracking
FOUNDATION_AGENT_NAMES = [
    "Request Interpreter",
    "Retrieval Agent",
    "SQL Specialist",
    "Citation & Evidence",
]


def build_foundation_agents(
    llm: str,
    include_nlm: bool = False,
    include_thaijo: bool = True,
    province: str = "",
    notebook_id: str = "",
    mode: str = "full",
) -> dict:
    """Build the shared foundation agents.

    Args:
        llm: LLM identifier (e.g. "gemini/gemini-2.0-flash")
        include_nlm: If True, add NLM tools to the retrieval agent
        include_thaijo: If True, add search_thaijo tool to retrieval agent (default True)
        province: Province name (used for NLM retrieval context)
        notebook_id: NotebookLM notebook ID (used for NLM retrieval)
        mode: 'full' (4 agents) or 'short' (Interpreter + Quick Retrieval only)

    Returns:
        Dict with keys: interpreter, retriever, sql_specialist, citation_evidence
        In short mode: only interpreter and retriever are populated
    """
    interpreter = create_request_interpreter(llm)
    retriever = _create_retrieval_agent(llm, include_nlm, include_thaijo, province, notebook_id, mode)

    if mode == "short":
        return {
            "interpreter": interpreter,
            "retriever": retriever,
            "sql_specialist": None,
            "citation_evidence": None,
        }

    sql_specialist = create_sql_specialist(llm)
    citation_evidence = create_citation_evidence_agent(llm)

    return {
        "interpreter": interpreter,
        "retriever": retriever,
        "sql_specialist": sql_specialist,
        "citation_evidence": citation_evidence,
    }


def build_foundation_tasks(
    agents: dict,
    user_message: str,
    province: str = "",
    year: int = 0,
    notebook_id: str = "",
    topics: list[str] | None = None,
    include_nlm: bool = False,
    mode: str = "full",
) -> dict:
    """Build the shared foundation tasks.

    Args:
        agents: Dict from build_foundation_agents()
        user_message: Original user message
        province: Province name (for NLM context)
        year: Thai Buddhist year (for NLM context)
        notebook_id: NotebookLM notebook ID
        topics: List of topics for NLM fetching
        include_nlm: Whether NLM retrieval is active
        mode: 'full' (4 tasks) or 'short' (interpret + retrieve only)

    Returns:
        Dict with keys: interpret, retrieve, sql, citation — each a CrewAI Task
        In short mode: only interpret and retrieve are returned
    """
    # --- Task 1: Interpret the request ---
    interpret_desc = REQUEST_INTERPRETER_PROMPT.replace("{user_message}", user_message)
    interpret_task = Task(
        description=interpret_desc,
        expected_output="JSON object with topics, geography, time_range, report_type, focus, language",
        agent=agents["interpreter"],
    )

    # --- Task 2: Retrieve data ---
    retrieve_desc = (
        "จากผลการตีความคำขอ ให้ค้นหาข้อมูลที่เกี่ยวข้องทั้งหมดตามลำดับดังนี้:\n\n"
        "**ขั้นตอนที่ 1 (บังคับ): เรียก search_documents — ต้องทำก่อนเสมอ ห้ามข้าม**\n"
        f"   - ครั้งที่ 1: ใช้ keywords = คำขอต้นฉบับของผู้ใช้ทั้งประโยค: \"{user_message}\"\n"
        "                  topic = \"all\"  (ค้นทุกหมวดเพื่อให้ได้ผลที่ครอบคลุมที่สุด)\n"
        "   - ครั้งที่ 2: ใช้ keywords = คำสำคัญที่สกัดจากคำขอ (เช่น ชื่อจังหวัด + หัวข้อ)\n"
        "                  topic = หมวดที่เกี่ยวข้อง (accident / mental_health / nutrition)\n"
        "   - ผลลัพธ์จาก search_documents คือเนื้อหาเอกสารหลักสำหรับรายงานและ citation\n\n"
        "**ขั้นตอนที่ 2: ดึงข้อมูลสถิติจากฐานข้อมูล**\n"
        "   - ใช้ get_accident_summary, get_province_year_summary และ tools อื่นๆ ที่เกี่ยวข้อง\n\n"
        "**ขั้นตอนที่ 3: ดึงตัวชี้วัดที่เกี่ยวข้อง**\n"
        "   - เรียก get_indicator_catalog สำหรับ topic ที่เกี่ยวข้อง\n\n"
        "**ขั้นตอนที่ 4: รวบรวมข้อมูลพื้นที่ถ้าจำเป็น**\n"
        "   - เรียก get_geography_profile, get_accident_hotspots ถ้ามีการถามเรื่องพื้นที่\n\n"
        "⚠️ ขั้นตอนที่ 1 ครั้งที่ 1 ต้องส่ง keywords เป็นคำขอต้นฉบับเต็มประโยคเสมอ\n"
        "   เพื่อให้ embedding search จับความหมายได้ครบถ้วนที่สุด\n"
    )

    if include_nlm and province:
        nlm_topics = ", ".join(topics or ["rti", "mental", "ncd"])
        retrieve_desc += (
            f"\n5. **ดึงข้อมูลจาก NotebookLM** สำหรับรายงานตรวจราชการ:\n"
            f"   - จังหวัด: {province}\n"
            f"   - notebook_id: {notebook_id}\n"
            f"   - topics: {nlm_topics}\n"
            f"   - ปี: {year} (พ.ศ.)\n"
            f"   - ใช้ nlm_ask(province, topic, notebook_id) ทีละ topic\n"
            f"   - รอ 2 วินาทีระหว่าง query\n"
        )

    retrieve_desc += (
        "\nให้ค้นข้อมูลให้ครบถ้วนและระบุแหล่งที่มาทุกรายการ\n\n"
        "คำขอของผู้ใช้: " + user_message
    )

    retrieve_task = Task(
        description=retrieve_desc,
        expected_output="รวบรวมข้อมูลทั้งหมดที่ค้นมาได้ พร้อมระบุแหล่งที่มา",
        agent=agents["retriever"],
        context=[interpret_task],
    )

    # Short mode: return only interpret + retrieve tasks
    if mode == "short":
        return {
            "interpret": interpret_task,
            "retrieve": retrieve_task,
        }

    # --- Task 3: SQL Specialist ---
    sql_task = Task(
        description=(
            "วิเคราะห์คำขอและข้อมูลจาก retrieval agent แล้วดำเนินการดังนี้:\n\n"
            "1. **ถ้าต้องการแสดงกราฟ/แผนภูมิ**:\n"
            "   - เขียน SQL query เพื่อดึงข้อมูลในรูปแบบที่เหมาะสมกับการสร้างกราฟ\n"
            "   - ข้อมูลต้องมี labels (แกน X) และ values (แกน Y) ที่ชัดเจน\n"
            "   - รัน query และจัดรูปแบบผลลัพธ์ให้พร้อมสำหรับ Chart Builder\n\n"
            "2. **ถ้าต้องการข้อมูลเฉพาะเจาะจง** ที่ tools ปกติไม่มี:\n"
            "   - เขียน SQL query ที่เหมาะสม\n"
            "   - รัน query และอธิบายผลลัพธ์\n\n"
            "3. **ถ้าเป็นคำถามทั่วไป** ที่ไม่ต้องการกราฟและข้อมูลจาก retrieval เพียงพอ:\n"
            "   - ตอบว่า 'ข้อมูลจาก retrieval เพียงพอแล้ว ไม่ต้องใช้ custom SQL'\n\n"
            "**สำคัญ**: ถ้าคำขอเกี่ยวกับ trend, เปรียบเทียบ, สถิติรายปี/รายเดือน "
            "→ ต้องเตรียมข้อมูลสำหรับกราฟเสมอ\n\n"
            "คำขอของผู้ใช้: " + user_message
        ),
        expected_output=(
            "ข้อมูลในรูปแบบที่พร้อมสำหรับการสร้างกราฟ "
            "หรือผลลัพธ์ custom query หรือข้อความว่าไม่จำเป็น"
        ),
        agent=agents["sql_specialist"],
        context=[retrieve_task],
    )

    # --- Task 4: Citation & Evidence (APA 7th) ---
    citation_desc = CITATION_EVIDENCE_PROMPT
    if include_nlm and province:
        citation_desc += (
            f"\n\n**Context:** จังหวัด {province} ปี {year} (พ.ศ.)\n"
            f"notebook_id: {notebook_id}\n\n"
            "**APA Metadata สำหรับ NotebookLM sources:**\n"
            f"- apa_type: report\n"
            f"- apa_authors: สำนักงานสาธารณสุขจังหวัด{province}\n"
            f"- apa_year: {year}\n"
            f"- apa_publisher: กระทรวงสาธารณสุข\n"
            f"- trust_level: high (รายงานราชการ)\n\n"
            f"bibliography_text: สำนักงานสาธารณสุขจังหวัด{province}. ({year}). "
            f"*รายงานตรวจราชการฯ ปีงบประมาณ {year}*. กระทรวงสาธารณสุข.\n"
            f"inline: (สสจ.{province}, {year}, หน้า XX)\n\n"
            "จัดลำดับ citation code: C-001..C-099 (reports), C-100..C-199 (database)"
        )

    citation_task = Task(
        description=citation_desc,
        expected_output=(
            "JSON object with evidence_items, claims, citations, source_notes, "
            "reference_list, coverage — ดูรายละเอียด format ใน prompt"
        ),
        agent=agents["citation_evidence"],
        context=[retrieve_task, sql_task],
    )

    return {
        "interpret": interpret_task,
        "retrieve": retrieve_task,
        "sql": sql_task,
        "citation": citation_task,
    }


def _create_retrieval_agent(
    llm: str,
    include_nlm: bool,
    include_thaijo: bool,
    province: str,
    notebook_id: str,
    mode: str = "full",
) -> "Agent":
    """Create retrieval agent with optional NLM and ThaiJO tools.

    - include_nlm=True: adds nlm_ask + get_supported_provinces (policy brief)
    - include_thaijo=True: adds search_thaijo tool (default on)
    - mode='short': builds minimal retriever with only 3 tools
    """
    from src.tools.common import search_documents, get_indicator_catalog, get_geography_profile
    from src.tools.accident import get_accident_summary
    from src.tools.thaijo import search_thaijo

    if mode == "short":
        # Minimal retriever for Short Chat: search_documents + get_accident_summary + search_thaijo
        tools = [search_documents, get_accident_summary]
        if include_thaijo:
            tools.append(search_thaijo)

        return Agent(
            role="Quick Retrieval Specialist",
            goal=(
                "ค้นหาข้อมูลที่เกี่ยวข้องอย่างรวดเร็ว (1 round) "
                "จากเอกสารและฐานข้อมูลสถิติอุบัติเหตุ"
            ),
            backstory=(
                "คุณเป็นผู้เชี่ยวชาญด้านการค้นคืนข้อมูลสุขภาพ "
                "สำหรับการตอบคำถามสั้น คุณค้นข้อมูลอย่างรวดเร็ว 1 รอบ "
                "ใช้ search_documents สำหรับค้นเอกสาร "
                "และ get_accident_summary สำหรับสถิติอุบัติเหตุ "
                + ("และ search_thaijo สำหรับบทความวิชาการ " if include_thaijo else "")
                + "ระบุแหล่งที่มาทุกรายการ"
            ),
            tools=tools,
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )

    # Full mode: use the standard retrieval agent
    agent = create_retrieval_agent(llm)

    # ThaiJO is already included in create_retrieval_agent (tool 11)
    # If include_thaijo=False, remove it
    if not include_thaijo:
        from src.tools.thaijo import search_thaijo as _thaijo_tool
        agent.tools = [t for t in agent.tools if t is not _thaijo_tool]

    if include_nlm:
        from src.tools.notebooklm import nlm_ask, get_supported_provinces

        # Extend the agent's tools list with NLM tools
        agent.tools = list(agent.tools) + [nlm_ask, get_supported_provinces]

        # Extend backstory with NLM context
        agent.backstory += (
            "\n\nนอกจากนี้ คุณยังสามารถดึงข้อมูลจากรายงานตรวจราชการสาธารณสุข "
            "ผ่าน NotebookLM ได้ โดยใช้เครื่องมือ nlm_ask(province, topic, notebook_id) "
            "สำหรับ 3 หัวข้อ: RTI (อุบัติเหตุ), Mental Health (สุขภาพจิต), NCD (โรคไม่ติดต่อ) "
            f"จังหวัดเป้าหมาย: {province}, notebook_id: {notebook_id}"
        )

    return agent
