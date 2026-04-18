"""Orchestrator: CrewAI Crew that wires all agents together."""
import json
import logging
import re
import sys
import time
from crewai import Agent, Crew, Task, Process, LLM
from crewai.agents.parser import AgentAction, AgentFinish

from src.config import get_settings
from src.db.pool import query_db
from src.utils.apa_formatter import format_apa_reference
from src.agents.shared_foundation import (
    build_foundation_agents, build_foundation_tasks, FOUNDATION_AGENT_NAMES,
)
from src.agents.citation_evidence import parse_evidence_context
from src.agents.analyst_accident import create_accident_analyst, ACCIDENT_ANALYSIS_PROMPT
from src.agents.research_synthesizer import create_research_synthesizer, RESEARCH_SYNTHESIZER_PROMPT
from src.agents.deep_analyst import create_deep_analyst, DEEP_ANALYST_PROMPT
from src.agents.report_writer import create_report_writer, REPORT_WRITER_PROMPT
from src.agents.chart_builder import create_chart_builder, CHART_BUILDER_PROMPT
from src.schemas.response import AgentResponse, ChartSpec, TableSpec, Citation
from src.agents.progress import emit_progress

logger = logging.getLogger(__name__)

# Agent names for progress tracking (foundation + chat-specific, 9 agents total)
CHAT_AGENT_NAMES = FOUNDATION_AGENT_NAMES + [
    "Accident Analyst",
    "Chart Builder",
    "Research Synthesizer",
    "Deep Analyst",
    "Report Composer",
]


def _get_llm(tier: str = "fast") -> LLM:
    """Get a tiered LLM instance for CrewAI agents.

    Args:
        tier: "fast" for foundation/simple agents, "pro" for analyst/writer agents.

    Returns:
        CrewAI LLM object configured for the requested tier.
    """
    s = get_settings()
    if tier == "pro":
        return LLM(
            model=f"gemini/{s.GEMINI_MODEL_PRO}",
            temperature=0.3,
            max_tokens=s.REPORT_MAX_TOKENS,
        )
    # Default: fast tier
    return LLM(
        model=f"gemini/{s.GEMINI_MODEL}",
        temperature=0.2,
        max_tokens=4096,
    )


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
    """Build the crew with 9 core agents: 4 shared foundation + 5 chat-specific.

    Pipeline: Interpreter → Retrieval → SQL → Citation →
              Analyst → Chart Builder → Research Synthesizer → Deep Analyst → Report Composer

    Uses tiered LLMs:
    - fast tier: foundation agents (interpreter, retriever, sql, citation)
    - pro tier: analyst, chart builder, synthesizer, deep analyst, report composer
    """
    llm_fast = _get_llm("fast")
    llm_pro = _get_llm("pro")

    # Shared foundation agents (1-4) — fast tier
    foundation = build_foundation_agents(llm_fast, include_nlm=False)

    # Chat-specific agents (5-9) — pro tier for quality
    analyst = create_accident_analyst(llm_pro)
    chart_builder = create_chart_builder(llm_pro)
    synthesizer = create_research_synthesizer(llm_pro)
    deep_analyst = create_deep_analyst(llm_pro)
    writer = create_report_writer(llm_pro)

    return {
        **foundation,
        "analyst": analyst,
        "chart_builder": chart_builder,
        "synthesizer": synthesizer,
        "deep_analyst": deep_analyst,
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
        expected_output=(
            "ผลการวิเคราะห์ข้อมูลอุบัติเหตุเชิงลึก รวมถึง key_findings (5+ ข้อพร้อมบริบท), "
            "trends (รายปีพร้อมอธิบายสาเหตุ), risk_areas, risk_groups, Haddon Matrix, "
            "recommended_actions (แบ่ง 3 ระยะพร้อม KPI), chart_candidates, ข้อจำกัดข้อมูล"
        ),
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

    # --- Task 7: Research Synthesizer (NEW) ---
    research_synth_task = Task(
        description=RESEARCH_SYNTHESIZER_PROMPT,
        expected_output=(
            "4 บล็อกย่อหน้าเชิงบรรยาย รวม 1,200–2,000 คำ: "
            "Block 1 สถานการณ์ภาพรวม, Block 2 กลุ่มเสี่ยงและปัจจัย, "
            "Block 3 ผลดำเนินงานและ GAP, Block 4 บริบทเชิงพื้นที่รายอำเภอ"
        ),
        agent=agents["synthesizer"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 8: Deep Analyst (NEW) ---
    deep_analysis_task = Task(
        description=DEEP_ANALYST_PROMPT,
        expected_output=(
            "การวิเคราะห์ 4 มิติ รวม 1,000–1,500 คำ: "
            "Root Cause (Haddon Matrix เชิงลึก), การเปรียบเทียบเชิงพื้นที่, "
            "ผลกระทบเชิงนโยบาย (Policy Gaps + ข้อเสนอ), การคาดการณ์แนวโน้ม"
        ),
        agent=agents["deep_analyst"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 9: Write report (Report Composer) ---
    write_task = Task(
        description=REPORT_WRITER_PROMPT,
        expected_output=(
            "รายงานสุขภาพภาษาไทยในรูปแบบ Markdown ความยาว 2,000–4,000 คำ "
            "ครอบคลุม 5 ส่วน: บทสรุปผู้บริหาร, สถานการณ์, มาตรการ, ผลดำเนินงาน, GAP "
            "พร้อม inline citation [C-xxx] ทุกตัวเลขสำคัญ, ตาราง KPI, reference list APA 7th "
            "และข้อเสนอคำถามติดตาม 3 ข้อ"
        ),
        agent=agents["writer"],
        context=[research_synth_task, deep_analysis_task, chart_build_task, citation_task],
    )

    # --- Build and run Crew ---
    crew = Crew(
        agents=list(agents.values()),
        tasks=[
            interpret_task, retrieve_task, sql_task, citation_task,
            analyze_task, chart_build_task,
            research_synth_task, deep_analysis_task, write_task,
        ],
        process=Process.sequential,
        verbose=True,
        step_callback=_step_callback,
        task_callback=_task_callback,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [CREW START] message: %s\n"
        "   pipeline: Interpreter → Retrieval → SQL → Citation → "
        "Analyst → Charts → Research Synthesizer → Deep Analyst → Report Composer\n%s",
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
            citations = _enrich_citations_from_db(_dedup_citations([
                Citation(
                    citation_code=c.citation_code,
                    source_type=c.source_type,
                    source_ref=c.source_ref,
                    citation_text=c.citation_text,
                    open_url=c.open_url,
                    bibliography_text=c.bibliography_text,
                )
                for c in ev_ctx.citations
            ]))
            evidence_summary = {
                "total_evidence": len(ev_ctx.evidence_items),
                "total_citations": len(citations),
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
            "agent_count": 9,
            "pipeline": "phase3_research_synthesizer_deep_analyst",
            "chart_count": len(charts),
            "citation_count": len(citations),
            **evidence_summary,
        },
    )


def _dedup_citations(citations: list[Citation]) -> list[Citation]:
    """Deduplicate citations by source_ref — keep the first occurrence per unique source."""
    seen: dict[str, Citation] = {}
    for c in citations:
        key = c.source_ref.strip() or c.citation_code
        if key not in seen:
            seen[key] = c
    return list(seen.values())


def _enrich_citations_from_db(citations: list[Citation]) -> list[Citation]:
    """Fill open_url and correct bibliography_text from document_registry.

    Processes all citations. Lookup order:
      1. Exact minio_path / file_path match on source_ref
      2. Title-stem ILIKE match on source_ref
      3. Author-keyword ILIKE match on apa_authors using first word of bibliography_text
    Always overwrites bibliography_text with DB value (corrects LLM hallucinations).
    """
    if not citations:
        return citations

    try:
        reg_map: dict[str, dict] = {}

        # ── Pass 1: exact path match ──
        source_refs = list({c.source_ref for c in citations if c.source_ref})
        if source_refs:
            ph = ",".join(["%s"] * len(source_refs))
            rows = query_db(
                f"SELECT * FROM document_registry WHERE minio_path IN ({ph}) OR file_path IN ({ph})",
                source_refs + source_refs,
            )
            for row in rows:
                for key in (row.get("minio_path", ""), row.get("file_path", "")):
                    if key:
                        reg_map[key] = row

        # ── Pass 2: title-stem ILIKE on still-unmatched source_refs ──
        unmatched_refs = [c.source_ref for c in citations if c.source_ref and c.source_ref not in reg_map]
        for src in unmatched_refs:
            stem = src.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if len(stem) >= 4:
                rows2 = query_db(
                    "SELECT * FROM document_registry WHERE title ILIKE %s LIMIT 1",
                    (f"%{stem}%",),
                )
                if rows2:
                    reg_map[src] = rows2[0]

        # ── Pass 3: author-keyword ILIKE for any citation still missing open_url ──
        import re as _re
        for c in citations:
            if c.open_url:  # already resolved
                continue
            # Try bib-text author keyword
            bib = (c.bibliography_text or c.citation_text or "").strip()
            if not bib:
                continue
            # First word before comma/period/space = last name / org keyword
            first_word = _re.split(r'[,\.\s]', bib)[0].strip()
            if len(first_word) < 3:
                continue
            rows3 = query_db(
                "SELECT * FROM document_registry "
                "WHERE apa_authors ILIKE %s OR title ILIKE %s LIMIT 1",
                (f"%{first_word}%", f"%{first_word}%"),
            )
            if rows3:
                # Store under multiple keys for reliable lookup below
                if c.source_ref:
                    reg_map[c.source_ref] = rows3[0]
                if c.citation_code:
                    reg_map[c.citation_code] = rows3[0]
                reg_map[bib[:40]] = rows3[0]

        # ── Apply enrichment ──
        for c in citations:
            row = (
                reg_map.get(c.source_ref)
                or reg_map.get(c.citation_code or "")
                or reg_map.get((c.bibliography_text or c.citation_text or "")[:40])
            )
            if row:
                doc_id = row.get("document_id")
                if doc_id:
                    c.open_url = f"/api/documents/open/{doc_id}"
                # Always overwrite bibliography_text from DB (correct LLM hallucinations)
                c.bibliography_text = format_apa_reference(row)
    except Exception as exc:
        logger.debug("_enrich_citations_from_db failed: %s", exc)

    return citations


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
        expected_output=(
            "ผลการวิเคราะห์ข้อมูลอุบัติเหตุเชิงลึก รวมถึง key_findings (5+ ข้อพร้อมบริบท), "
            "trends (รายปีพร้อมอธิบายสาเหตุ), risk_areas, risk_groups, Haddon Matrix, "
            "recommended_actions (แบ่ง 3 ระยะพร้อม KPI), chart_candidates, ข้อจำกัดข้อมูล"
        ),
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

    # --- Task 7: Research Synthesizer (NEW) ---
    research_synth_task = Task(
        description=RESEARCH_SYNTHESIZER_PROMPT,
        expected_output=(
            "4 บล็อกย่อหน้าเชิงบรรยาย รวม 1,200–2,000 คำ: "
            "Block 1 สถานการณ์ภาพรวม, Block 2 กลุ่มเสี่ยงและปัจจัย, "
            "Block 3 ผลดำเนินงานและ GAP, Block 4 บริบทเชิงพื้นที่รายอำเภอ"
        ),
        agent=agents["synthesizer"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 8: Deep Analyst (NEW) ---
    deep_analysis_task = Task(
        description=DEEP_ANALYST_PROMPT,
        expected_output=(
            "การวิเคราะห์ 4 มิติ รวม 1,000–1,500 คำ: "
            "Root Cause (Haddon Matrix เชิงลึก), การเปรียบเทียบเชิงพื้นที่, "
            "ผลกระทบเชิงนโยบาย (Policy Gaps + ข้อเสนอ), การคาดการณ์แนวโน้ม"
        ),
        agent=agents["deep_analyst"],
        context=[retrieve_task, sql_task, analyze_task, citation_task],
    )

    # --- Task 9: Write report (Report Composer) ---
    write_task = Task(
        description=REPORT_WRITER_PROMPT,
        expected_output=(
            "รายงานสุขภาพภาษาไทยในรูปแบบ Markdown ความยาว 2,000–4,000 คำ "
            "ครอบคลุม 5 ส่วน: บทสรุปผู้บริหาร, สถานการณ์, มาตรการ, ผลดำเนินงาน, GAP "
            "พร้อม inline citation [C-xxx] ทุกตัวเลขสำคัญ, ตาราง KPI, reference list APA 7th "
            "และข้อเสนอคำถามติดตาม 3 ข้อ"
        ),
        agent=agents["writer"],
        context=[research_synth_task, deep_analysis_task, chart_build_task, citation_task],
    )

    tasks = [
        interpret_task, retrieve_task, sql_task, citation_task,
        analyze_task, chart_build_task,
        research_synth_task, deep_analysis_task, write_task,
    ]

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
        "\n%s\n🚀 [CREW+PROGRESS] message: %s\n"
        "   pipeline: Interpreter → Retrieval → SQL → Citation → "
        "Analyst → Charts → Research Synthesizer → Deep Analyst → Report Composer\n%s",
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
