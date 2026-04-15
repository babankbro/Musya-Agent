"""Router for Policy Brief API endpoints (Phase 3)."""
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.schemas.policy_brief import PolicyBriefRequest, PolicyBriefResponse, ProvincesResponse
from src.tools.notebooklm import PROVINCE_NOTEBOOKS, SUPPORTED_PROVINCES
from src.agents.policy_orchestrator import run_policy_brief, validate_province

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/policy-brief", tags=["policy-brief"])


@router.get("/provinces", response_model=ProvincesResponse)
async def list_provinces():
    """List all supported provinces for Policy Brief generation."""
    notebook_ids = list(set(PROVINCE_NOTEBOOKS.values()))
    return ProvincesResponse(
        provinces=SUPPORTED_PROVINCES,
        notebook_id=notebook_ids[0] if notebook_ids else "",
        health_zone="เขตสุขภาพที่ 10",
    )


@router.post("", response_model=PolicyBriefResponse)
async def create_policy_brief(request: PolicyBriefRequest):
    """Generate a Policy Brief for a province across RTI, Mental Health, and NCD topics.

    This endpoint runs the full Phase 3 pipeline:
    1. NLM Data Fetcher (Agent A1) — queries NotebookLM for all topics
    2. Parallel Analysts (A2/A3/A4) — RTI, Mental Health, NCD analysis
    3. Citation & Evidence Agent (A5) — normalises sources
    4. Policy Report Writer (A6) — synthesises final Policy Brief

    Expected runtime: ~2-3 minutes depending on NotebookLM response time.
    """
    valid, _ = validate_province(request.province)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_province",
                "message": f"ไม่รองรับจังหวัด '{request.province}'",
                "supported_provinces": SUPPORTED_PROVINCES,
            },
        )

    valid_topics = [t for t in request.topics if t.lower() in ("rti", "mental", "ncd")]
    if not valid_topics:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_topics",
                "message": "topics ต้องเป็น 'rti', 'mental', หรือ 'ncd'",
            },
        )

    logger.info(
        "[policy-brief] Starting: province=%s topics=%s year=%d",
        request.province, valid_topics, request.year,
    )

    try:
        result = run_policy_brief(
            province=request.province,
            topics=valid_topics,
            year=request.year,
            output_format=request.format,
        )
        return JSONResponse(content=result)

    except Exception as exc:
        logger.exception("[policy-brief] Pipeline error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={"error": "pipeline_failed", "message": str(exc)},
        )
