"""Short Chat Orchestrator — lightweight 3-agent pipeline for quick Q&A.

Pipeline: Request Interpreter → Quick Retrieval → Quick Answer Writer
Target: ~30-60 seconds, 500-1,000 word answers with inline citations.
"""
import logging
import time

from crewai import Crew, Process, Task

from src.config import get_settings
from src.agents.shared_foundation import build_foundation_agents, build_foundation_tasks
from src.agents.quick_answer_writer import create_quick_answer_writer, QUICK_ANSWER_WRITER_PROMPT
from src.agents.progress import emit_progress
from src.agents.agent_defaults import kickoff_with_retry
from src.schemas.short_chat import ShortChatResponse, ShortChatCitation

logger = logging.getLogger(__name__)


def run_short_chat(
    user_message: str,
    session_id: str | None = None,
) -> ShortChatResponse:
    """Run the Short Chat pipeline (3 agents, sequential).

    Returns a ShortChatResponse with content, citations, and follow-up questions.
    """
    start_time = time.time()
    s = get_settings()
    llm = f"gemini/{s.GEMINI_MODEL}"

    # Build foundation agents in short mode (Interpreter + Quick Retrieval only)
    foundation = build_foundation_agents(llm, mode="short")
    foundation_tasks = build_foundation_tasks(
        foundation, user_message, mode="short"
    )

    # Build Quick Answer Writer agent + task
    answer_writer = create_quick_answer_writer(llm)
    answer_task = Task(
        description=QUICK_ANSWER_WRITER_PROMPT.replace(
            "{context}", "{{interpret_output + retrieve_output}}"
        ).replace("{user_message}", user_message),
        expected_output=(
            "คำตอบสั้น 500-1,000 คำ ภาษาไทย Markdown พร้อม inline citations [C-xxx] "
            "และคำถามติดตาม 2-3 ข้อ"
        ),
        agent=answer_writer,
        context=[foundation_tasks["interpret"], foundation_tasks["retrieve"]],
    )

    # Run crew
    crew = Crew(
        agents=[foundation["interpreter"], foundation["retriever"], answer_writer],
        tasks=[foundation_tasks["interpret"], foundation_tasks["retrieve"], answer_task],
        process=Process.sequential,
        verbose=True,
    )

    logger.info("💬 [SHORT_CHAT] Starting pipeline: %s", user_message[:80])
    result = kickoff_with_retry(crew)
    elapsed = time.time() - start_time

    # Parse result into ShortChatResponse
    content = str(result)
    
    # Try to get retrieval context for open_url enrichment
    retrieval_json = foundation_tasks["retrieve"].output.raw if hasattr(foundation_tasks["retrieve"].output, "raw") else ""
    
    citations = _extract_citations(content, retrieval_context=retrieval_json)

    return ShortChatResponse(
        pipeline_used="short_chat",
        content=content,
        citations=citations,
        elapsed_seconds=round(elapsed, 1),
        follow_up_questions=_extract_follow_ups(content),
    )


def run_short_chat_with_progress(
    user_message: str,
    session_id: str | None = None,
    request_id: str | None = None,
) -> ShortChatResponse:
    """Same as run_short_chat but emits progress events for SSE streaming."""
    start_time = time.time()
    s = get_settings()
    llm = f"gemini/{s.GEMINI_MODEL}"

    # Step 1: Request Interpreter
    emit_progress(request_id, "Request Interpreter", "running", "กำลังวิเคราะห์คำถาม...")
    foundation = build_foundation_agents(llm, mode="short")
    foundation_tasks = build_foundation_tasks(foundation, user_message, mode="short")

    # Step 2: Quick Retrieval
    emit_progress(request_id, "Quick Retrieval", "running", "กำลังค้นหาข้อมูล...")

    # Build Quick Answer Writer
    answer_writer = create_quick_answer_writer(llm)
    answer_task = Task(
        description=QUICK_ANSWER_WRITER_PROMPT.replace(
            "{context}", "{{interpret_output + retrieve_output}}"
        ).replace("{user_message}", user_message),
        expected_output=(
            "คำตอบสั้น 500-1,000 คำ ภาษาไทย Markdown พร้อม inline citations [C-xxx] "
            "และคำถามติดตาม 2-3 ข้อ"
        ),
        agent=answer_writer,
        context=[foundation_tasks["interpret"], foundation_tasks["retrieve"]],
    )

    crew = Crew(
        agents=[foundation["interpreter"], foundation["retriever"], answer_writer],
        tasks=[foundation_tasks["interpret"], foundation_tasks["retrieve"], answer_task],
        process=Process.sequential,
        verbose=True,
    )

    logger.info("💬 [SHORT_CHAT] Starting pipeline (with progress): %s", user_message[:80])
    result = kickoff_with_retry(crew)
    elapsed = time.time() - start_time

    # Emit done events
    emit_progress(request_id, "Request Interpreter", "done", "วิเคราะห์คำถามเสร็จ")
    emit_progress(request_id, "Quick Retrieval", "done", "ค้นหาข้อมูลเสร็จ")
    emit_progress(request_id, "Quick Answer Writer", "done", "เขียนคำตอบเสร็จ")

    content = str(result)
    
    # Try to get retrieval context for open_url enrichment
    retrieval_json = foundation_tasks["retrieve"].output.raw if hasattr(foundation_tasks["retrieve"].output, "raw") else ""
    
    citations = _extract_citations(content, retrieval_context=retrieval_json)

    return ShortChatResponse(
        pipeline_used="short_chat",
        content=content,
        citations=citations,
        elapsed_seconds=round(elapsed, 1),
        follow_up_questions=_extract_follow_ups(content),
    )


def _extract_citations(text: str, retrieval_context: str = "") -> list[ShortChatCitation]:
    """Extract [C-xxx] citations and their bibliography from text."""
    import re
    import json
    
    seen = set()
    citations = []
    
    # First, find the References section
    ref_section = ""
    ref_match = re.search(r"(?:รายการอ้างอิง|References)[:\s]*(.*)", text, re.DOTALL | re.IGNORECASE)
    if ref_match:
        ref_section = ref_match.group(1)
        # Stop at the disclaimer or follow-up
        ref_section = re.split(r"(?:⚠️|คำถามติดตาม|Follow-up)", ref_section)[0]
    
    # Find all [C-xxx] codes in the main text
    codes_in_text = re.findall(r"\[C-(\d+)\]", text)
    
    # Map codes to bibliography in the ref section
    ref_map = {}
    if ref_section:
        for match in re.finditer(r"\[C-(\d+)\]\s*(.+?)(?=\[C-|\n|$)", ref_section, re.DOTALL):
            code = f"C-{match.group(1)}"
            bib = match.group(2).strip()
            ref_map[code] = bib
            
    # Parse retrieval context to find URLs
    url_map = {}
    if retrieval_context:
        try:
            # The context might be a JSON string or a list of JSON-like objects
            # Search for URLs or document titles
            data = json.loads(retrieval_context)
            if isinstance(data, list):
                for item in data:
                    url = item.get("open_url") or item.get("pdf_url")
                    title = item.get("title") or item.get("reference")
                    if url and title:
                        url_map[title] = url
        except:
            pass
            
    # Combine
    unique_codes = []
    for c in codes_in_text:
        code = f"C-{c}"
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)
            
    for code in unique_codes:
        bib = ref_map.get(code, "")
        url = ""
        # Try to find a URL by fuzzy matching the bibliography text with the url_map
        if bib:
            for title, u in url_map.items():
                if title in bib or bib in title:
                    url = u
                    break
        
        citations.append(ShortChatCitation(code=code, bibliography_text=bib, open_url=url))
        
    return citations


def _extract_follow_ups(text: str) -> list[str]:
    """Extract follow-up questions from text (numbered list at the end)."""
    import re
    
    # Try to find the follow-up questions section first
    section_match = re.search(r"(?:คำถามติดตาม|Follow-up)[:\s]*(.*)", text, re.DOTALL | re.IGNORECASE)
    search_text = section_match.group(1) if section_match else text
    
    # Match numbered questions (optionally ending with ?)
    matches = re.findall(r"(?:^|\n)\s*\d+\.\s*(.+?)(?=\n|$)", search_text)
    
    if matches:
        # Clean up and limit to 3
        cleaned = [m.strip() for m in matches if len(m.strip()) > 5]
        return cleaned[-3:]
    
    return []
