"""Orchestrator: CrewAI Crew that wires all agents together."""
import json
import logging
import re
import sys
import time
from crewai import Agent, Crew, Task, Process
from crewai.agents.parser import AgentAction, AgentFinish

from src.config import get_settings
from src.agents.request_interpreter import create_request_interpreter, REQUEST_INTERPRETER_PROMPT
from src.agents.retrieval import create_retrieval_agent
from src.agents.sql_specialist import create_sql_specialist
from src.agents.analyst_accident import create_accident_analyst, ACCIDENT_ANALYSIS_PROMPT
from src.agents.report_writer import create_report_writer, REPORT_WRITER_PROMPT
from src.agents.chart_builder import create_chart_builder, CHART_BUILDER_PROMPT
from src.schemas.response import AgentResponse, ChartSpec, TableSpec, Citation

logger = logging.getLogger(__name__)


def _get_llm():
    """Get the LLM instance for CrewAI agents."""
    s = get_settings()
    # CrewAI supports litellm format: "gemini/model-name"
    return f"gemini/{s.GEMINI_MODEL}"


def _step_callback(step_output) -> None:
    """Called after every agent step — logs thinking to terminal."""
    sep = "─" * 60
    if isinstance(step_output, AgentAction):
        logger.info(
            "\n%s\n🤔 [AGENT THINKING]\n"
            "  Thought  : %s\n"
            "  Action   : %s\n"
            "  Input    : %s\n"
            "%s",
            sep,
            getattr(step_output, 'thought', ''),
            getattr(step_output, 'tool', ''),
            getattr(step_output, 'tool_input', ''),
            sep,
        )
    elif isinstance(step_output, AgentFinish):
        output = getattr(step_output, 'output', str(step_output))
        logger.info(
            "\n%s\n✅ [AGENT FINISH]\n  Output: %s\n%s",
            sep,
            str(output)[:500],
            sep,
        )
    else:
        logger.info("\n%s\n📋 [AGENT STEP]\n%s\n%s", sep, str(step_output)[:500], sep)


def _task_callback(task_output) -> None:
    """Called after every task completes — logs the task result."""
    sep = "═" * 60
    logger.info(
        "\n%s\n🏁 [TASK COMPLETE] %s\n  Result: %s\n%s",
        sep,
        getattr(task_output, 'description', '')[:80],
        str(getattr(task_output, 'raw', task_output))[:600],
        sep,
    )


def build_crew() -> dict:
    """Build the Phase 1 crew with 6 core agents."""
    llm = _get_llm()

    interpreter = create_request_interpreter(llm)
    retriever = create_retrieval_agent(llm)
    sql_specialist = create_sql_specialist(llm)
    analyst = create_accident_analyst(llm)
    chart_builder = create_chart_builder(llm)
    writer = create_report_writer(llm)

    agents = {
        "interpreter": interpreter,
        "retriever": retriever,
        "sql_specialist": sql_specialist,
        "analyst": analyst,
        "chart_builder": chart_builder,
        "writer": writer,
    }

    return agents


def run_chat(user_message: str, session_id: str | None = None) -> AgentResponse:
    """Run the full agent pipeline for a chat message.
    
    Args:
        user_message: The user's input text
        session_id: Optional session ID for context
    
    Returns:
        AgentResponse with content, charts, tables, citations, and follow-ups.
    """
    start_time = time.time()
    agents = build_crew()
    llm = _get_llm()

    # --- Task 1: Interpret the request ---
    interpret_desc = REQUEST_INTERPRETER_PROMPT.replace("{user_message}", user_message)
    interpret_task = Task(
        description=interpret_desc,
        expected_output="JSON object with topics, geography, time_range, report_type, focus, language",
        agent=agents["interpreter"],
    )

    # --- Task 2: Retrieve data ---
    retrieve_task = Task(
        description=(
            "จากผลการตีความคำขอ ให้ค้นหาข้อมูลที่เกี่ยวข้องทั้งหมด:\n"
            "1. ค้นเอกสารที่เกี่ยวข้องจาก Document RAG\n"
            "2. ดึงข้อมูลสถิติจากฐานข้อมูล\n"
            "3. ดึงตัวชี้วัดที่เกี่ยวข้อง\n"
            "4. รวบรวมข้อมูลพื้นที่ถ้าจำเป็น\n\n"
            "ให้ค้นข้อมูลให้ครบถ้วนและระบุแหล่งที่มาทุกรายการ\n\n"
            "คำขอของผู้ใช้: " + user_message
        ),
        expected_output="รวบรวมข้อมูลทั้งหมดที่ค้นมาได้ พร้อมระบุแหล่งที่มา",
        agent=agents["retriever"],
        context=[interpret_task],
    )

    # --- Task 3: SQL Specialist (prepare chart-ready data) ---
    sql_task = Task(
        description=(
            "วิเคราะห์คำขอและข้อมูลจาก retrieval agent แล้วดำเนินการดังนี้:\n\n"
            "1. **ถ้าต้องการแสดงกราฟ/แผนภูมิ**:\n"
            "   - เขียน SQL query เพื่อดึงข้อมูลในรูปแบบที่เหมาะสมกับการสร้างกราฟ\n"
            "   - ข้อมูลต้องมี labels (แกน X) และ values (แกน Y) ที่ชัดเจน\n"
            "   - ตัวอย่าง: SELECT year_no, accident_count, death_count FROM ... ORDER BY year_no\n"
            "   - รัน query และจัดรูปแบบผลลัพธ์ให้พร้อมสำหรับ Chart Builder\n\n"
            "2. **ถ้าต้องการข้อมูลเฉพาะเจาะจง** ที่ tools ปกติไม่มี:\n"
            "   - เขียน SQL query ที่เหมาะสม (เช่น custom filtering, grouping, calculations)\n"
            "   - รัน query และอธิบายผลลัพธ์\n\n"
            "3. **ถ้าเป็นคำถามทั่วไป** ที่ไม่ต้องการกราฟและข้อมูลจาก retrieval เพียงพอ:\n"
            "   - ตอบว่า 'ข้อมูลจาก retrieval เพียงพอแล้ว ไม่ต้องใช้ custom SQL'\n\n"
            "**สำคัญ**: ถ้าคำขอเกี่ยวกับ trend, เปรียบเทียบ, สถิติรายปี/รายเดือน → ต้องเตรียมข้อมูลสำหรับกราฟเสมอ\n\n"
            "คำขอของผู้ใช้: " + user_message
        ),
        expected_output="ข้อมูลในรูปแบบที่พร้อมสำหรับการสร้างกราฟ (ถ้าต้องการกราฟ) หรือผลลัพธ์ custom query หรือข้อความว่าไม่จำเป็น",
        agent=agents["sql_specialist"],
        context=[retrieve_task],
    )

    # --- Task 4: Analyze ---
    analyze_task = Task(
        description=ACCIDENT_ANALYSIS_PROMPT,
        expected_output="ผลการวิเคราะห์ข้อมูลอุบัติเหตุ รวมถึง key_findings, trends, risk_areas, recommended_actions",
        agent=agents["analyst"],
        context=[retrieve_task, sql_task],
    )

    # --- Task 5: Build charts ---
    chart_build_task = Task(
        description=CHART_BUILDER_PROMPT,
        expected_output=(
            "JSON array ของ ChartSpec objects พร้อม render บน ChartRenderer "
            "แต่ละ item มี fields: type, title, data.labels, data.datasets, options, source_note"
        ),
        agent=agents["chart_builder"],
        context=[retrieve_task, sql_task, analyze_task],
    )

    # --- Task 6: Write report ---
    write_task = Task(
        description=REPORT_WRITER_PROMPT,
        expected_output=(
            "รายงานภาษาไทยในรูปแบบ Markdown ที่มีโครงสร้างชัดเจน "
            "พร้อมข้อเสนอกราฟและตาราง "
            "รวมถึงข้อเสนอคำถามติดตาม 3 ข้อ"
        ),
        agent=agents["writer"],
        context=[analyze_task, chart_build_task],
    )

    # --- Build and run Crew ---
    crew = Crew(
        agents=list(agents.values()),
        tasks=[interpret_task, retrieve_task, sql_task, analyze_task, chart_build_task, write_task],
        process=Process.sequential,
        verbose=True,
        step_callback=_step_callback,
        task_callback=_task_callback,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [CREW START] message: %s\n   agents: Request Interpreter → Retrieval → SQL Specialist → Analyst → Chart Builder → Report Writer\n%s",
        sep, user_message[:120], sep
    )

    try:
        result = crew.kickoff()
        elapsed = time.time() - start_time
        logger.info(f"Crew completed in {elapsed:.1f}s")

        # Parse the result into AgentResponse
        return _parse_crew_result(result, elapsed)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Crew failed after {elapsed:.1f}s: {e}")
        return AgentResponse(
            content=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}",
            topic="error",
            metadata={"error": str(e), "elapsed_seconds": elapsed},
        )


def _parse_crew_result(result, elapsed: float) -> AgentResponse:
    """Parse CrewAI result into a structured AgentResponse."""
    raw_output = str(result)

    # Try to extract charts from the tasks_output list (index 3 = chart_build_task)
    charts = _extract_charts_from_result(result)
    follow_ups = _extract_follow_ups(raw_output)

    return AgentResponse(
        content=raw_output,
        topic="accident",
        charts=charts,
        tables=[],
        citations=[],
        follow_ups=follow_ups,
        metadata={
            "elapsed_seconds": elapsed,
            "agent_count": 6,
            "pipeline": "phase1_accident_with_sql",
            "chart_count": len(charts),
        },
    )


def _extract_charts_from_result(result) -> list[ChartSpec]:
    """Extract ChartSpec objects from the chart_build_task output (task index 4)."""
    # CrewAI stores per-task outputs in result.tasks_output list
    tasks_output = getattr(result, "tasks_output", None)
    chart_raw = None

    if tasks_output and len(tasks_output) >= 5:
        # Index 4 = chart_build_task (after interpret, retrieve, sql, analyze)
        chart_task_out = tasks_output[4]
        chart_raw = getattr(chart_task_out, "raw", None) or str(chart_task_out)
    else:
        # Fallback: try to find a JSON array block anywhere in the full output
        chart_raw = str(result)

    return _parse_chart_specs(chart_raw or "")


def _parse_chart_specs(text: str) -> list[ChartSpec]:
    """Parse a JSON array of chart specs from agent output text."""
    charts: list[ChartSpec] = []
    if not text:
        return charts

    # Find the outermost JSON array in the text
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return charts

    candidate = text[start: end + 1]
    try:
        items = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        # Try to find a JSON block inside ```json ... ``` fences
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if not match:
            return charts
        try:
            items = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            return charts

    if not isinstance(items, list):
        return charts

    valid_types = {"bar", "line", "pie", "doughnut"}
    for item in items:
        if not isinstance(item, dict):
            continue
        chart_type = str(item.get("type", "")).lower()
        if chart_type not in valid_types:
            continue
        data = item.get("data", {})
        if not isinstance(data, dict):
            continue
        if "labels" not in data or "datasets" not in data:
            continue
        try:
            charts.append(
                ChartSpec(
                    type=chart_type,
                    title=str(item.get("title", "กราฟ")),
                    data=data,
                    options=item.get("options", {}),
                    source_note=str(item.get("source_note", "")),
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed ChartSpec: %s", exc)

    return charts


def _extract_follow_ups(text: str) -> list[str]:
    """Extract suggested follow-up questions from agent output."""
    follow_ups = []
    lines = text.split("\n")
    in_followup = False

    for line in lines:
        stripped = line.strip()
        if any(keyword in stripped.lower() for keyword in ["คำถามติดตาม", "คำถามต่อ", "follow-up", "ถามเพิ่มเติม"]):
            in_followup = True
            continue
        if in_followup and stripped:
            # Remove bullet points and numbering
            cleaned = stripped.lstrip("- •·*").lstrip("0123456789.").strip()
            if cleaned and len(cleaned) > 5:
                follow_ups.append(cleaned)
            if len(follow_ups) >= 3:
                break

    return follow_ups[:3]
