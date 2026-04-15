"""Unified Orchestrator: routes user requests to the correct pipeline.

Both pipelines share the same foundation agents (1-4):
  Request Interpreter → Data Retrieval → SQL Specialist → Citation & Evidence

Flow:
    User Message
        │
        ▼
    Request Router Agent  ─── decides ──→  chat_pipeline | policy_brief_pipeline
        │                                        │
        ▼                                        ▼
    === SHARED FOUNDATION (agents 1-4) ===  === SHARED FOUNDATION (agents 1-4 + NLM) ===
        │                                        │
        ▼                                        ▼
    Chat: Analyst → Chart → Writer         Policy: [RTI‖Mental‖NCD] → Report Writer
    → AgentResponse                        → PolicyBriefResponse (dict)
"""
import logging
import time
from typing import Optional

from src.agents.request_router import route_request
from src.agents.orchestrator import run_chat, run_chat_with_progress
from src.agents.policy_orchestrator import run_policy_brief, run_policy_brief_with_progress, validate_province
from src.schemas.response import AgentResponse
from src.tools.notebooklm import SUPPORTED_PROVINCES
from src.agents.progress import emit_progress

logger = logging.getLogger(__name__)


def run_unified(user_message: str, session_id: str | None = None) -> dict:
    """Unified entry point: route → run the correct pipeline → return result.

    Returns:
        dict with keys:
            - pipeline_used: str ("chat_pipeline" | "policy_brief_pipeline")
            - routing: dict (router decision details)
            - result: AgentResponse dict (chat) or PolicyBriefResponse dict (policy brief)
    """
    start_time = time.time()

    # ── Step 1: Route the request ──
    routing = route_request(user_message)
    pipeline = routing["pipeline"]
    params = routing.get("extracted_params", {})

    logger.info(
        "🔀 [UNIFIED] pipeline=%s confidence=%.2f reason=%s",
        pipeline,
        routing.get("confidence", 0),
        routing.get("reason", ""),
    )

    # ── Step 2: Execute the chosen pipeline ──
    if pipeline == "policy_brief_pipeline":
        result = _run_policy_brief_pipeline(user_message, params)
    else:
        result = _run_chat_pipeline(user_message, session_id)

    elapsed = time.time() - start_time

    # Inject unified metadata
    if isinstance(result, dict):
        meta = result.get("metadata", {})
    else:
        meta = getattr(result, "metadata", {}) or {}

    meta["unified_elapsed_seconds"] = round(elapsed, 1)
    meta["pipeline_used"] = pipeline
    meta["routing_confidence"] = routing.get("confidence", 0)
    meta["routing_reason"] = routing.get("reason", "")

    if isinstance(result, dict):
        result["metadata"] = meta
    elif hasattr(result, "metadata"):
        result.metadata = meta

    return {
        "pipeline_used": pipeline,
        "routing": routing,
        "result": result.model_dump() if isinstance(result, AgentResponse) else result,
    }


def _run_chat_pipeline(user_message: str, session_id: str | None) -> AgentResponse:
    """Execute chat pipeline (4 shared foundation + 3 chat-specific agents)."""
    logger.info("📊 [UNIFIED] Running chat_pipeline")
    return run_chat(user_message=user_message, session_id=session_id)


def _run_policy_brief_pipeline(user_message: str, params: dict) -> dict:
    """Execute policy brief pipeline (4 shared foundation + 4 policy-specific agents).

    Extracts province/topics/year from router params or falls back to defaults.
    """
    province = params.get("province", "")
    topics = params.get("topics", ["rti", "mental", "ncd"])
    year = params.get("year", 2564)

    # If router didn't extract province, try to find it in the message
    if not province:
        for p in SUPPORTED_PROVINCES:
            if p in user_message:
                province = p
                break

    # If still no province, return an error via chat pipeline instead
    if not province:
        logger.warning(
            "🔀 [UNIFIED] policy_brief requested but no province found — "
            "falling back to chat_pipeline"
        )
        return run_chat(user_message=user_message, session_id=None).model_dump()

    valid, _ = validate_province(province)
    if not valid:
        logger.warning(
            "🔀 [UNIFIED] province '%s' not supported — falling back to chat_pipeline",
            province,
        )
        return run_chat(user_message=user_message, session_id=None).model_dump()

    # Normalize topics
    valid_topics = [t for t in topics if t.lower() in ("rti", "mental", "ncd")]
    if not valid_topics:
        valid_topics = ["rti", "mental", "ncd"]

    logger.info(
        "📋 [UNIFIED] Running policy_brief_pipeline: province=%s topics=%s year=%d",
        province, valid_topics, year,
    )

    return run_policy_brief(
        province=province,
        topics=valid_topics,
        year=year,
    )


def run_unified_with_progress(
    user_message: str,
    session_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Unified entry point with progress tracking for streaming.

    Same as run_unified but emits progress events to the queue identified by request_id.
    """
    start_time = time.time()

    # ── Step 1: Route the request ──
    emit_progress(request_id, "Request Router", "running", "กำลังวิเคราะห์คำขอ...")
    routing = route_request(user_message)
    pipeline = routing["pipeline"]
    params = routing.get("extracted_params", {})
    emit_progress(request_id, "Request Router", "done", f"→ {pipeline}", time.time() - start_time)

    logger.info(
        "🔀 [UNIFIED+PROGRESS] pipeline=%s confidence=%.2f",
        pipeline,
        routing.get("confidence", 0),
    )

    # ── Step 2: Execute the chosen pipeline with progress ──
    if pipeline == "policy_brief_pipeline":
        result = _run_policy_brief_pipeline_with_progress(user_message, params, request_id)
    else:
        result = _run_chat_pipeline_with_progress(user_message, session_id, request_id)

    elapsed = time.time() - start_time

    # Inject unified metadata
    if isinstance(result, dict):
        meta = result.get("metadata", {})
    else:
        meta = getattr(result, "metadata", {}) or {}

    meta["unified_elapsed_seconds"] = round(elapsed, 1)
    meta["pipeline_used"] = pipeline
    meta["routing_confidence"] = routing.get("confidence", 0)
    meta["routing_reason"] = routing.get("reason", "")

    if isinstance(result, dict):
        result["metadata"] = meta
    elif hasattr(result, "metadata"):
        result.metadata = meta

    return {
        "pipeline_used": pipeline,
        "routing": routing,
        "result": result.model_dump() if isinstance(result, AgentResponse) else result,
    }


def _run_chat_pipeline_with_progress(
    user_message: str, session_id: Optional[str], request_id: str
) -> AgentResponse:
    """Execute chat pipeline with progress tracking."""
    logger.info("📊 [UNIFIED+PROGRESS] Running chat_pipeline")
    return run_chat_with_progress(
        user_message=user_message,
        session_id=session_id,
        request_id=request_id,
    )


def _run_policy_brief_pipeline_with_progress(
    user_message: str, params: dict, request_id: str
) -> dict:
    """Execute policy brief pipeline with progress tracking."""
    province = params.get("province", "")
    topics = params.get("topics", ["rti", "mental", "ncd"])
    year = params.get("year", 2564)

    # If router didn't extract province, try to find it in the message
    if not province:
        for p in SUPPORTED_PROVINCES:
            if p in user_message:
                province = p
                break

    # If still no province, return an error via chat pipeline instead
    if not province:
        logger.warning("🔀 [UNIFIED+PROGRESS] no province — falling back to chat_pipeline")
        return run_chat_with_progress(
            user_message=user_message, session_id=None, request_id=request_id
        ).model_dump()

    valid, _ = validate_province(province)
    if not valid:
        logger.warning("🔀 [UNIFIED+PROGRESS] province '%s' not supported", province)
        return run_chat_with_progress(
            user_message=user_message, session_id=None, request_id=request_id
        ).model_dump()

    valid_topics = [t for t in topics if t.lower() in ("rti", "mental", "ncd")]
    if not valid_topics:
        valid_topics = ["rti", "mental", "ncd"]

    logger.info(
        "📋 [UNIFIED+PROGRESS] Running policy_brief_pipeline: province=%s topics=%s",
        province, valid_topics,
    )

    return run_policy_brief_with_progress(
        province=province,
        topics=valid_topics,
        year=year,
        request_id=request_id,
    )
