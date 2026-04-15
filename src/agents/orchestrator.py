"""Orchestrator: CrewAI Crew that wires all agents together."""
import json
import logging
import re
import sys
import time
from crewai import Agent, Crew, Task, Process
from crewai.agents.parser import AgentAction, AgentFinish

from src.config import get_settings
from src.agents.shared_foundation import (
    build_foundation_agents, build_foundation_tasks, FOUNDATION_AGENT_NAMES,
)
from src.agents.citation_evidence import parse_evidence_context
from src.agents.analyst_accident import create_accident_analyst, ACCIDENT_ANALYSIS_PROMPT
from src.agents.report_writer import create_report_writer, REPORT_WRITER_PROMPT
from src.agents.chart_builder import create_chart_builder, CHART_BUILDER_PROMPT
from src.schemas.response import AgentResponse, ChartSpec, TableSpec, Citation
from src.agents.progress import emit_progress

logger = logging.getLogger(__name__)

# Agent names for progress tracking (foundation + chat-specific)
CHAT_AGENT_NAMES = FOUNDATION_AGENT_NAMES + [
    "Accident Analyst",
    "Chart Builder",
    "Report Writer",
]


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
    """Build the crew with 7 core agents: 4 shared foundation + 3 chat-specific."""
    llm = _get_llm()

    # Shared foundation agents (1-4)
    foundation = build_foundation_agents(llm, include_nlm=False)

    # Chat-specific agents (5-7)
    analyst = create_accident_analyst(llm)
    chart_builder = create_chart_builder(llm)
    writer = create_report_writer(llm)

    return {
        **foundation,
        "analyst": analyst,
        "chart_builder": chart_builder,
        "writer": writer,
    }


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

    # --- Tasks 1-4: Shared Foundation ---
    foundation = build_foundation_tasks(agents, user_message)
    interpret_task = foundation["interpret"]
    retrieve_task = foundation["retrieve"]
    sql_task = foundation["sql"]
    citation_task = foundation["citation"]

    # --- Task 5: Analyze ---
    analyze_task = Task(
        description=ACCIDENT_ANALYSIS_PROMPT,
        expected_output="ผลการวิเคราะห์ข้อมูลอุบัติเหตุ รวมถึง key_findings, trends, risk_areas, recommended_actions",
        agent=agents["analyst"],
        context=[retrieve_task, sql_task, citation_task],
    )

    # --- Task 6: Build charts ---
    chart_build_task = Task(
        description=CHART_BUILDER_PROMPT,
        expected_output=(
            "JSON array ของ ChartSpec objects พร้อม render บน ChartRenderer "
            "แต่ละ item มี fields: type, title, data.labels, data.datasets, options, source_note"
        ),
        agent=agents["chart_builder"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 7: Write report ---
    write_task = Task(
        description=REPORT_WRITER_PROMPT,
        expected_output=(
            "รายงานภาษาไทยในรูปแบบ Markdown ที่มีโครงสร้างชัดเจน "
            "พร้อม inline citation [C-001] และ reference list ท้ายรายงาน "
            "รวมถึงข้อเสนอคำถามติดตาม 3 ข้อ"
        ),
        agent=agents["writer"],
        context=[analyze_task, chart_build_task, citation_task],
    )

    # --- Build and run Crew ---
    crew = Crew(
        agents=list(agents.values()),
        tasks=[interpret_task, retrieve_task, sql_task, citation_task, analyze_task, chart_build_task, write_task],
        process=Process.sequential,
        verbose=True,
        step_callback=_step_callback,
        task_callback=_task_callback,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [CREW START] message: %s\n   agents: Request Interpreter → Retrieval → SQL → Citation & Evidence → Analyst → Chart Builder → Report Writer\n%s",
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

    # Extract charts from chart_build_task output (now index 5)
    charts = _extract_charts_from_result(result)
    follow_ups = _extract_follow_ups(raw_output)

    # Extract citations from Citation & Evidence Agent output (task index 3)
    citations = []
    evidence_summary = {}
    tasks_output = getattr(result, "tasks_output", None)
    if tasks_output and len(tasks_output) >= 4:
        citation_raw = getattr(tasks_output[3], "raw", None) or str(tasks_output[3])
        try:
            ev_ctx = parse_evidence_context(citation_raw)
            citations = [
                Citation(
                    citation_code=c.citation_code,
                    source_type=c.source_type,
                    source_ref=c.source_ref,
                    citation_text=c.citation_text,
                )
                for c in ev_ctx.citations
            ]
            evidence_summary = {
                "total_evidence": len(ev_ctx.evidence_items),
                "total_citations": len(ev_ctx.citations),
                "total_claims": len(ev_ctx.claims),
                "coverage_score": ev_ctx.coverage_report.coverage_score,
            }
        except Exception as e:
            logger.warning("Failed to parse citation output: %s", e)

    return AgentResponse(
        content=raw_output,
        topic="accident",
        charts=charts,
        tables=[],
        citations=citations,
        follow_ups=follow_ups,
        metadata={
            "elapsed_seconds": elapsed,
            "agent_count": 7,
            "pipeline": "phase2_with_citation_evidence",
            "chart_count": len(charts),
            "citation_count": len(citations),
            **evidence_summary,
        },
    )


def _extract_charts_from_result(result) -> list[ChartSpec]:
    """Extract ChartSpec objects from the chart_build_task output (task index 5)."""
    # CrewAI stores per-task outputs in result.tasks_output list
    tasks_output = getattr(result, "tasks_output", None)
    chart_raw = None

    if tasks_output and len(tasks_output) >= 6:
        # Index 5 = chart_build_task (after interpret, retrieve, sql, citation, analyze)
        chart_task_out = tasks_output[5]
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


def run_chat_with_progress(
    user_message: str,
    session_id: str | None = None,
    request_id: str | None = None,
) -> AgentResponse:
    """Run the chat pipeline with progress tracking for streaming UI.

    Emits progress events as each agent completes.
    """
    start_time = time.time()
    agents = build_crew()

    # Track task completion times
    task_times = {}

    def make_task_callback(agent_idx: int):
        """Create a task callback that emits progress for a specific agent."""
        agent_name = CHAT_AGENT_NAMES[agent_idx] if agent_idx < len(CHAT_AGENT_NAMES) else f"Agent {agent_idx}"

        def callback(task_output):
            elapsed = time.time() - start_time
            task_times[agent_idx] = elapsed
            emit_progress(request_id, agent_name, "done", "เสร็จสิ้น", elapsed)
            _task_callback(task_output)  # Also call original logger

        return callback

    # Emit initial progress for first agent
    emit_progress(request_id, CHAT_AGENT_NAMES[0], "running", "กำลังตีความคำขอ...")

    # --- Tasks 1-4: Shared Foundation ---
    foundation = build_foundation_tasks(agents, user_message)
    interpret_task = foundation["interpret"]
    retrieve_task = foundation["retrieve"]
    sql_task = foundation["sql"]
    citation_task = foundation["citation"]

    # --- Task 5: Analyze ---
    analyze_task = Task(
        description=ACCIDENT_ANALYSIS_PROMPT,
        expected_output="ผลการวิเคราะห์ข้อมูลอุบัติเหตุ รวมถึง key_findings, trends, risk_areas, recommended_actions",
        agent=agents["analyst"],
        context=[retrieve_task, sql_task, citation_task],
    )

    # --- Task 6: Build charts ---
    chart_build_task = Task(
        description=CHART_BUILDER_PROMPT,
        expected_output=(
            "JSON array ของ ChartSpec objects พร้อม render บน ChartRenderer "
            "แต่ละ item มี fields: type, title, data.labels, data.datasets, options, source_note"
        ),
        agent=agents["chart_builder"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 7: Write report ---
    write_task = Task(
        description=REPORT_WRITER_PROMPT,
        expected_output=(
            "รายงานภาษาไทยในรูปแบบ Markdown ที่มีโครงสร้างชัดเจน "
            "พร้อม inline citation [C-001] และ reference list ท้ายรายงาน "
            "รวมถึงข้อเสนอคำถามติดตาม 3 ข้อ"
        ),
        agent=agents["writer"],
        context=[analyze_task, chart_build_task, citation_task],
    )

    tasks = [interpret_task, retrieve_task, sql_task, citation_task, analyze_task, chart_build_task, write_task]

    # Custom task callback that emits progress
    current_task_idx = [0]  # Use list to allow mutation in closure

    def progress_task_callback(task_output):
        idx = current_task_idx[0]
        elapsed = time.time() - start_time
        agent_name = CHAT_AGENT_NAMES[idx] if idx < len(CHAT_AGENT_NAMES) else f"Agent {idx}"
        emit_progress(request_id, agent_name, "done", "เสร็จสิ้น", elapsed)

        # Emit "running" for next agent
        next_idx = idx + 1
        if next_idx < len(CHAT_AGENT_NAMES):
            emit_progress(request_id, CHAT_AGENT_NAMES[next_idx], "running", "กำลังทำงาน...")

        current_task_idx[0] = next_idx
        _task_callback(task_output)

    # --- Build and run Crew ---
    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        step_callback=_step_callback,
        task_callback=progress_task_callback,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [CREW+PROGRESS] message: %s\n%s",
        sep, user_message[:120], sep
    )

    try:
        result = crew.kickoff()
        elapsed = time.time() - start_time
        logger.info(f"Crew completed in {elapsed:.1f}s")
        return _parse_crew_result(result, elapsed)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Crew failed after {elapsed:.1f}s: {e}")
        # Emit error for current agent
        if current_task_idx[0] < len(CHAT_AGENT_NAMES):
            emit_progress(request_id, CHAT_AGENT_NAMES[current_task_idx[0]], "error", str(e)[:100], elapsed)
        return AgentResponse(
            content=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}",
            topic="error",
            metadata={"error": str(e), "elapsed_seconds": elapsed},
        )
