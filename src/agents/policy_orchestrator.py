"""Agent A0 — Policy Brief Orchestrator: wires the full Phase 3 pipeline.

Uses shared foundation agents (1-4) with NLM tools enabled, then adds
policy-specific domain analysts and report writer.
"""
import json
import logging
import re
import time
from datetime import datetime

from crewai import Agent, Crew, Task, Process

from src.config import get_settings
from src.tools.notebooklm import PROVINCE_NOTEBOOKS, SUPPORTED_PROVINCES
from src.agents.shared_foundation import (
    build_foundation_agents, build_foundation_tasks, FOUNDATION_AGENT_NAMES,
)
from src.agents.policy_rti import create_rti_policy_analyst, RTI_ANALYST_PROMPT
from src.agents.policy_mental import create_mental_health_analyst, MENTAL_ANALYST_PROMPT
from src.agents.policy_ncd import create_ncd_policy_analyst, NCD_ANALYST_PROMPT
from src.agents.citation_evidence import parse_evidence_context
from src.agents.policy_report_writer import create_policy_report_writer, POLICY_REPORT_WRITER_PROMPT
from src.schemas.response import Citation
from src.agents.progress import emit_progress

logger = logging.getLogger(__name__)

# Agent names for progress tracking (foundation 1-4 + policy-specific)
POLICY_AGENT_NAMES = FOUNDATION_AGENT_NAMES + [
    "RTI Analyst",
    "Mental Health Analyst",
    "NCD Analyst",
    "Policy Report Writer",
]


def _get_llm() -> str:
    s = get_settings()
    return f"gemini/{s.GEMINI_MODEL}"


def validate_province(province: str) -> tuple[bool, str]:
    """Check if province is supported. Returns (valid, notebook_id)."""
    notebook_id = PROVINCE_NOTEBOOKS.get(province, "")
    return bool(notebook_id), notebook_id


def run_policy_brief(
    province: str,
    topics: list[str],
    year: int = 2564,
    output_format: str = "markdown",
) -> dict:
    """Run the full Phase 3 Policy Brief pipeline.

    Args:
        province: Province name in Thai (must be in SUPPORTED_PROVINCES)
        topics: List of topics: ['rti', 'mental', 'ncd']
        year: Thai Buddhist year (e.g. 2564)
        output_format: 'markdown' (default)

    Returns:
        dict matching PolicyBriefResponse schema.
    """
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    # --- Validate input ---
    valid, notebook_id = validate_province(province)
    if not valid:
        return {
            "province": province,
            "policy_brief": f"ไม่รองรับจังหวัด '{province}' — จังหวัดที่รองรับ: {', '.join(SUPPORTED_PROVINCES)}",
            "sections": {},
            "cross_topic_links": [],
            "charts": [],
            "citations": [],
            "metadata": {"error": "unsupported_province", "elapsed_seconds": 0},
        }

    topics = [t.lower() for t in topics if t.lower() in ("rti", "mental", "ncd")]
    if not topics:
        topics = ["rti", "mental", "ncd"]

    llm = _get_llm()

    # --- Build shared foundation agents (1-4) with NLM enabled ---
    foundation_agents = build_foundation_agents(
        llm, include_nlm=True, province=province, notebook_id=notebook_id,
    )

    # Policy-specific agents
    rti_analyst = create_rti_policy_analyst(llm)
    mental_analyst = create_mental_health_analyst(llm)
    ncd_analyst = create_ncd_policy_analyst(llm)
    report_writer = create_policy_report_writer(llm)

    # --- Tasks 1-4: Shared Foundation (with NLM) ---
    user_message = f"สร้างรายงานตรวจราชการ จังหวัด{province} ปี {year} หัวข้อ: {', '.join(topics)}"
    foundation_tasks = build_foundation_tasks(
        foundation_agents, user_message,
        province=province, year=year, notebook_id=notebook_id,
        topics=topics, include_nlm=True,
    )
    interpret_task = foundation_tasks["interpret"]
    retrieve_task = foundation_tasks["retrieve"]
    sql_task = foundation_tasks["sql"]
    citation_task = foundation_tasks["citation"]

    # --- Tasks 5-7: Parallel Domain Analyst Tasks (async_execution) ---
    base_context = (
        f"จังหวัด: {province} | ปี: {year} (พ.ศ.) | notebook_id: {notebook_id[:8]}...\n"
        "ใช้ข้อมูลจาก Retrieval Agent และ SQL Specialist ที่ผ่านมาเป็นบริบทหลัก"
    )

    rti_task = None
    mental_task = None
    ncd_task = None

    if "rti" in topics:
        rti_task = Task(
            description=(
                RTI_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล RTI จากข้อมูลที่ retrieval agent รวบรวมมา"
            ),
            expected_output="JSON ของ RTI Policy Analysis (situation, risk_factors, hotspots, recommendations, evidence_refs)",
            agent=rti_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    if "mental" in topics:
        mental_task = Task(
            description=(
                MENTAL_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล Mental Health จากข้อมูลที่ retrieval agent รวบรวมมา "
                "ปฏิบัติตาม safety guardrails อย่างเคร่งครัด"
            ),
            expected_output="JSON ของ Mental Health Policy Analysis พร้อม disclaimer",
            agent=mental_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    if "ncd" in topics:
        ncd_task = Task(
            description=(
                NCD_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล NCD จากข้อมูลที่ retrieval agent รวบรวมมา ตาม life-course framework"
            ),
            expected_output="JSON ของ NCD Policy Analysis (life_course_assessment, priority_districts, innovations, recommendations)",
            agent=ncd_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    analyst_tasks = [t for t in [rti_task, mental_task, ncd_task] if t is not None]

    # --- Task 8: Policy Report Writer ---
    report_task = Task(
        description=(
            POLICY_REPORT_WRITER_PROMPT + "\n\n"
            f"**Input:**\n"
            f"จังหวัด: {province}\n"
            f"ปี: {year} (พ.ศ.)\n"
            f"วันที่จัดทำ: {today}\n"
            f"topics: {', '.join(topics)}\n\n"
            "สังเคราะห์จากผลการวิเคราะห์ทุก analyst และ citation agent ข้างต้น"
        ),
        expected_output="Policy Brief ฉบับสมบูรณ์ในรูปแบบ Markdown พร้อม citations และ cross-topic section",
        agent=report_writer,
        context=analyst_tasks + [citation_task],
    )

    # --- Build and run Crew ---
    foundation_task_list = [interpret_task, retrieve_task, sql_task, citation_task]
    all_tasks = foundation_task_list + analyst_tasks + [report_task]
    all_agents = list(foundation_agents.values()) + [rti_analyst, mental_analyst, ncd_analyst, report_writer]

    crew = Crew(
        agents=all_agents,
        tasks=all_tasks,
        process=Process.sequential,
        verbose=True,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [POLICY BRIEF] province=%s topics=%s year=%d\n"
        "   pipeline: Interpreter → Retrieval(+NLM) → SQL → Citation → [RTI‖Mental‖NCD] → Report Writer\n%s",
        sep, province, topics, year, sep,
    )

    try:
        result = crew.kickoff()
        elapsed = time.time() - start_time
        logger.info("Policy Brief crew completed in %.1fs", elapsed)
        return _build_response(result, province, topics, year, notebook_id, elapsed, all_tasks)
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error("Policy Brief crew failed after %.1fs: %s", elapsed, exc)
        return {
            "province": province,
            "policy_brief": f"เกิดข้อผิดพลาดในการสร้าง Policy Brief: {exc}",
            "sections": {},
            "cross_topic_links": [],
            "charts": [],
            "citations": [],
            "metadata": {
                "error": str(exc),
                "elapsed_seconds": round(elapsed, 1),
                "pipeline": "phase3_policy_brief",
            },
        }


def _build_response(result, province: str, topics: list[str], year: int,
                    notebook_id: str, elapsed: float, all_tasks: list) -> dict:
    """Parse CrewAI result into PolicyBriefResponse dict."""
    tasks_output = getattr(result, "tasks_output", [])

    # Last task = Policy Report Writer (A6)
    report_raw = str(result)
    if tasks_output:
        last_out = tasks_output[-1]
        report_raw = getattr(last_out, "raw", None) or str(last_out)

    # Parse A6's per-domain JSON output
    domain_data = _parse_report_writer_output(report_raw)

    # Build sections: each value is a full Markdown string
    sections: dict = {}
    for topic in ("rti", "mental", "ncd"):
        key = f"{topic}_report"
        val = domain_data.get(key, "")
        if val:
            sections[topic] = val

    cross_links: list[str] = domain_data.get("cross_topic_links", [])
    priority_recs: list[dict] = domain_data.get("priority_recommendations", [])

    # Build backward-compat combined policy_brief from per-domain reports
    combined_parts = []
    for topic in topics:
        rpt = sections.get(topic, "")
        if rpt:
            combined_parts.append(rpt)
    if cross_links:
        combined_parts.append(
            "\n---\n\n## 🔗 ความเชื่อมโยงข้ามประเด็น\n\n"
            + "\n".join(f"- {lnk}" for lnk in cross_links)
        )
    policy_brief_text = "\n\n---\n\n".join(combined_parts) if combined_parts else report_raw

    # Parse citations from citation task (second-to-last task before report)
    citations: list[Citation] = []
    if len(tasks_output) >= 2:
        citation_raw = getattr(tasks_output[-2], "raw", None) or str(tasks_output[-2])
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
        except Exception as exc:
            logger.warning("Could not parse citations: %s", exc)

    return {
        "province": province,
        "policy_brief": policy_brief_text,
        "sections": sections,
        "cross_topic_links": cross_links,
        "priority_recommendations": priority_recs,
        "charts": [],
        "citations": [c.model_dump() for c in citations],
        "metadata": {
            "elapsed_seconds": round(elapsed, 1),
            "agent_count": 8,
            "pipeline": "shared_foundation_policy_brief",
            "notebook_id": notebook_id,
            "topics_analyzed": topics,
            "year": year,
        },
    }


def _parse_report_writer_output(raw: str) -> dict:
    """Parse A6 Report Writer JSON output that contains per-domain reports.

    Returns dict with keys: rti_report, mental_report, ncd_report,
    cross_topic_links, priority_recommendations.
    Falls back gracefully if JSON parsing fails.
    """
    # Try strict JSON first
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            # Validate expected keys are present
            if any(k in parsed for k in ("rti_report", "mental_report", "ncd_report")):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: treat the whole output as the combined policy_brief
    logger.warning("A6 output did not contain per-domain JSON — treating as combined brief")
    return {
        "rti_report": "",
        "mental_report": "",
        "ncd_report": "",
        "cross_topic_links": _extract_cross_topic_links_text(raw),
        "priority_recommendations": [],
        "_raw_fallback": raw,
    }


def _extract_cross_topic_links_text(text: str) -> list[str]:
    """Extract cross-topic linkage bullet points from free-text policy brief."""
    links: list[str] = []
    in_cross = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "cross-topic" in stripped.lower() or "ความเชื่อมโยงข้ามประเด็น" in stripped:
            in_cross = True
            continue
        if in_cross and stripped.startswith("#"):
            break
        if in_cross and stripped.startswith("-") and len(stripped) > 3:
            links.append(stripped.lstrip("- ").strip())
    return links[:8]


def run_policy_brief_with_progress(
    province: str,
    topics: list[str],
    year: int = 2564,
    request_id: str | None = None,
) -> dict:
    """Run the Policy Brief pipeline with progress tracking for streaming UI.

    Same as run_policy_brief but emits progress events as each agent completes.
    """
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    # Validate input
    valid, notebook_id = validate_province(province)
    if not valid:
        return {
            "province": province,
            "policy_brief": f"ไม่รองรับจังหวัด '{province}'",
            "sections": {},
            "cross_topic_links": [],
            "charts": [],
            "citations": [],
            "metadata": {"error": "unsupported_province", "elapsed_seconds": 0},
        }

    topics = [t.lower() for t in topics if t.lower() in ("rti", "mental", "ncd")]
    if not topics:
        topics = ["rti", "mental", "ncd"]

    llm = _get_llm()

    # --- Build shared foundation agents (1-4) with NLM enabled ---
    foundation_agents = build_foundation_agents(
        llm, include_nlm=True, province=province, notebook_id=notebook_id,
    )

    # Policy-specific agents
    rti_analyst = create_rti_policy_analyst(llm)
    mental_analyst = create_mental_health_analyst(llm)
    ncd_analyst = create_ncd_policy_analyst(llm)
    report_writer = create_policy_report_writer(llm)

    # Emit initial progress
    emit_progress(request_id, FOUNDATION_AGENT_NAMES[0], "running", f"กำลังตีความคำขอ {province}...")

    # --- Tasks 1-4: Shared Foundation (with NLM) ---
    user_message = f"สร้างรายงานตรวจราชการ จังหวัด{province} ปี {year} หัวข้อ: {', '.join(topics)}"
    foundation_tasks = build_foundation_tasks(
        foundation_agents, user_message,
        province=province, year=year, notebook_id=notebook_id,
        topics=topics, include_nlm=True,
    )
    interpret_task = foundation_tasks["interpret"]
    retrieve_task = foundation_tasks["retrieve"]
    sql_task = foundation_tasks["sql"]
    citation_task = foundation_tasks["citation"]

    # --- Tasks 5-7: Parallel Domain Analyst Tasks ---
    base_context = (
        f"จังหวัด: {province} | ปี: {year} (พ.ศ.) | notebook_id: {notebook_id[:8]}...\n"
        "ใช้ข้อมูลจาก Retrieval Agent และ SQL Specialist ที่ผ่านมาเป็นบริบทหลัก"
    )

    rti_task = None
    mental_task = None
    ncd_task = None

    if "rti" in topics:
        rti_task = Task(
            description=(
                RTI_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล RTI จากข้อมูลที่ retrieval agent รวบรวมมา"
            ),
            expected_output="JSON ของ RTI Policy Analysis",
            agent=rti_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    if "mental" in topics:
        mental_task = Task(
            description=(
                MENTAL_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล Mental Health จากข้อมูลที่ retrieval agent รวบรวมมา"
            ),
            expected_output="JSON ของ Mental Health Policy Analysis",
            agent=mental_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    if "ncd" in topics:
        ncd_task = Task(
            description=(
                NCD_ANALYST_PROMPT + "\n\n"
                f"**Context:**\n{base_context}\n"
                "วิเคราะห์เฉพาะข้อมูล NCD จากข้อมูลที่ retrieval agent รวบรวมมา"
            ),
            expected_output="JSON ของ NCD Policy Analysis",
            agent=ncd_analyst,
            context=[retrieve_task, sql_task, citation_task],
            async_execution=True,
        )

    analyst_tasks = [t for t in [rti_task, mental_task, ncd_task] if t is not None]

    # --- Task 8: Policy Report Writer ---
    report_task = Task(
        description=(
            POLICY_REPORT_WRITER_PROMPT + "\n\n"
            f"**Input:**\n"
            f"จังหวัด: {province}\n"
            f"ปี: {year} (พ.ศ.)\n"
            f"วันที่จัดทำ: {today}\n"
            f"topics: {', '.join(topics)}"
        ),
        expected_output="Policy Brief ฉบับสมบูรณ์ในรูปแบบ Markdown",
        agent=report_writer,
        context=analyst_tasks + [citation_task],
    )

    # Build task list and track progress
    foundation_task_list = [interpret_task, retrieve_task, sql_task, citation_task]
    all_tasks = foundation_task_list + analyst_tasks + [report_task]
    all_agents = list(foundation_agents.values()) + [rti_analyst, mental_analyst, ncd_analyst, report_writer]

    # Map task index to agent name for progress tracking
    task_agent_map = list(FOUNDATION_AGENT_NAMES)
    for t in analyst_tasks:
        if t == rti_task:
            task_agent_map.append("RTI Analyst")
        elif t == mental_task:
            task_agent_map.append("Mental Health Analyst")
        elif t == ncd_task:
            task_agent_map.append("NCD Analyst")
    task_agent_map.append("Policy Report Writer")

    current_task_idx = [0]

    def progress_task_callback(task_output):
        idx = current_task_idx[0]
        elapsed = time.time() - start_time
        agent_name = task_agent_map[idx] if idx < len(task_agent_map) else f"Agent {idx}"
        emit_progress(request_id, agent_name, "done", "เสร็จสิ้น", elapsed)

        # Emit "running" for next agent
        next_idx = idx + 1
        if next_idx < len(task_agent_map):
            emit_progress(request_id, task_agent_map[next_idx], "running", "กำลังทำงาน...")

        current_task_idx[0] = next_idx

    crew = Crew(
        agents=all_agents,
        tasks=all_tasks,
        process=Process.sequential,
        verbose=True,
        task_callback=progress_task_callback,
    )

    sep = "★" * 60
    logger.info(
        "\n%s\n🚀 [POLICY BRIEF+PROGRESS] province=%s topics=%s\n"
        "   pipeline: Interpreter → Retrieval(+NLM) → SQL → Citation → [RTI‖Mental‖NCD] → Report Writer\n%s",
        sep, province, topics, sep,
    )

    try:
        result = crew.kickoff()
        elapsed = time.time() - start_time
        logger.info("Policy Brief crew completed in %.1fs", elapsed)
        return _build_response(result, province, topics, year, notebook_id, elapsed, all_tasks)
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error("Policy Brief crew failed after %.1fs: %s", elapsed, exc)
        # Emit error for current agent
        if current_task_idx[0] < len(task_agent_map):
            emit_progress(request_id, task_agent_map[current_task_idx[0]], "error", str(exc)[:100], elapsed)
        return {
            "province": province,
            "policy_brief": f"เกิดข้อผิดพลาด: {exc}",
            "sections": {},
            "cross_topic_links": [],
            "charts": [],
            "citations": [],
            "metadata": {"error": str(exc), "elapsed_seconds": round(elapsed, 1)},
        }
