"""ThaiJO search + research report + cache inspector endpoints."""
import asyncio
import concurrent.futures
import json
import logging
import uuid
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError

from src.tools.thaijo import search_thaijo
from src.config import get_settings
from src.schemas.thaijo_research import ThaiJOResearchRequest, ThaiJOResearchResponse
from src.agents.thaijo_research_orchestrator import run_thaijo_research, run_thaijo_research_with_progress
from src.agents.progress import create_progress_queue, remove_progress_queue

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/thaijo", tags=["thaijo"])

# Redis cache connection (shared with ThaiJO microservice)
# When running locally (not in Docker), redis hostname won't resolve — substitute localhost
_cache_prefix = settings.CACHE_PREFIX
_redis_url = settings.REDIS_URL
if "redis://redis:" in _redis_url:
    _redis_url = _redis_url.replace("redis://redis:", "redis://localhost:")
_redis = None
try:
    _redis = Redis.from_url(_redis_url, decode_responses=True, socket_connect_timeout=3)
    _redis.ping()
    logger.info("Redis cache connected: %s", _redis_url)
except RedisError as e:
    logger.warning("Redis cache unavailable (%s): %s — cache inspector endpoints will return 503", _redis_url, e)
    _redis = None


class ThaiJOSearchRequest(BaseModel):
    term: str = Field(..., description="Search term (Thai or English), 2-5 keywords")
    size: int = Field(5, ge=1, le=10, description="Number of articles (1-10)")
    page: int = Field(1, ge=1, description="Page number")
    strict: bool = Field(True, description="Exact match search")


class ThaiJOArticle(BaseModel):
    pdf_url: str
    summary: str
    reference: str | None
    source_type: str
    trust_level: str
    apa_type: str
    search_term: str


class ThaiJOSearchResponse(BaseModel):
    count: int
    results: list[ThaiJOArticle]
    error: str | None = None
    note: str | None = None


@router.post("/search", response_model=ThaiJOSearchResponse)
async def thaijo_search(req: ThaiJOSearchRequest) -> ThaiJOSearchResponse:
    """Search ThaiJO academic articles directly (bypasses agent pipeline).

    Useful for:
    - Testing ThaiJO microservice connectivity
    - Frontend integration (bibliography preview)
    - Manual citation lookup

    Returns articles with pdf_url (clickable TCI-THAIJO link), AI summary,
    and APA reference text extracted from TCI-THAIJO HTML.
    """
    if not settings.THAIJO_ENABLED:
        return ThaiJOSearchResponse(count=0, results=[], note="ThaiJO search is disabled")

    raw = search_thaijo.func(
        term=req.term,
        size=req.size,
        page=req.page,
        strict=req.strict,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse ThaiJO tool response: %s", e)
        raise HTTPException(status_code=502, detail="ThaiJO service returned invalid response")

    if "error" in data:
        return ThaiJOSearchResponse(count=0, results=[], error=data["error"])

    return ThaiJOSearchResponse(
        count=data.get("count", 0),
        results=[ThaiJOArticle(**r) for r in data.get("results", [])],
    )


@router.get("/status")
async def thaijo_status():
    """Check ThaiJO integration status and configuration."""
    return {
        "enabled": settings.THAIJO_ENABLED,
        "api_url": settings.THAIJO_API_URL,
        "timeout_seconds": settings.THAIJO_TIMEOUT,
        "default_size": settings.THAIJO_DEFAULT_SIZE,
        "max_size": settings.THAIJO_MAX_SIZE,
    }


# ======================== Cache Inspector ========================

class CacheEntry(BaseModel):
    key: str
    preview: str = ""
    size: int = 0


class CacheStats(BaseModel):
    total_keys: int
    total_size_bytes: int
    redis_connected: bool


@router.get("/cache", response_model=list[CacheEntry])
async def cache_list():
    """List all cached ThaiJO article summaries from Redis."""
    if not _redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    try:
        keys = _redis.keys(f"{_cache_prefix}:*")
        entries = []
        for k in keys:
            val = _redis.get(k)
            if val is None:
                continue
            preview = val[:100] + "..." if len(val) > 100 else val
            entries.append(CacheEntry(key=k, preview=preview, size=len(val)))
        return entries
    except RedisError as e:
        logger.error("Redis cache list failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@router.get("/cache/stats", response_model=CacheStats)
async def cache_stats():
    """Get cache statistics."""
    if not _redis:
        return CacheStats(total_keys=0, total_size_bytes=0, redis_connected=False)
    try:
        keys = _redis.keys(f"{_cache_prefix}:*")
        total_size = 0
        for k in keys:
            val = _redis.get(k)
            if val:
                total_size += len(val.encode("utf-8"))
        return CacheStats(
            total_keys=len(keys),
            total_size_bytes=total_size,
            redis_connected=True,
        )
    except RedisError as e:
        logger.error("Redis cache stats failed: %s", e)
        return CacheStats(total_keys=0, total_size_bytes=0, redis_connected=False)


@router.get("/cache/{key:path}")
async def cache_get(key: str):
    """Get full cached summary by key."""
    if not _redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    # Accept key with or without prefix
    if not key.startswith(_cache_prefix):
        key = f"{_cache_prefix}:{key}"
    try:
        val = _redis.get(key)
        if val is None:
            raise HTTPException(status_code=404, detail="Cache key not found")
        return {"key": key, "summary": val, "size": len(val)}
    except RedisError as e:
        logger.error("Redis cache get failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@router.delete("/cache/{key:path}")
async def cache_delete(key: str):
    """Delete a single cached entry."""
    if not _redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    if not key.startswith(_cache_prefix):
        key = f"{_cache_prefix}:{key}"
    try:
        deleted = _redis.delete(key)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Cache key not found")
        return {"deleted": True, "key": key}
    except RedisError as e:
        logger.error("Redis cache delete failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@router.delete("/cache")
async def cache_clear():
    """Clear all ThaiJO cached summaries."""
    if not _redis:
        raise HTTPException(status_code=503, detail="Redis not connected")
    try:
        keys = _redis.keys(f"{_cache_prefix}:*")
        if keys:
            deleted = _redis.delete(*keys)
        else:
            deleted = 0
        return {"deleted": deleted, "total_cleared": len(keys)}
    except RedisError as e:
        logger.error("Redis cache clear failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")


@router.post("/research", response_model=ThaiJOResearchResponse)
async def thaijo_research(req: ThaiJOResearchRequest) -> ThaiJOResearchResponse:
    """Generate a ThaiJO Research Report (literature review) for a given topic.

    Runs the 6-agent pipeline:
    TopicParser → Searcher → Screener → Citation → Synthesizer → Composer

    Returns a Markdown report with charts, tables, APA citations, and follow-up questions.
    """
    if not settings.THAIJO_ENABLED:
        return ThaiJOResearchResponse(
            content="ThaiJO search is disabled", topic="error",
            metadata={"error": "thaijo_disabled"},
        )

    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    logger.info("ThaiJO research request: topic=%r max_articles=%s", req.topic[:80], req.max_articles)

    try:
        return run_thaijo_research(
            topic=req.topic,
            max_articles=req.max_articles,
            max_queries=req.max_queries,
            min_relevance=req.min_relevance,
            session_id=req.session_id,
        )
    except Exception as e:
        logger.error("ThaiJO research failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Research pipeline failed: {str(e)}")


@router.post("/research/stream")
async def thaijo_research_stream(req: ThaiJOResearchRequest):
    """SSE streaming version of the ThaiJO Research Report pipeline.

    Event types:
      - start: Pipeline begins
      - search_progress: Search query results
      - screening: Article screening results
      - agent_progress: Agent status updates (running/done/error)
      - content: Final ThaiJOResearchResponse
      - done: Pipeline complete
    """
    if not settings.THAIJO_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "ThaiJO search is disabled"},
        )

    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    request_id = str(uuid.uuid4())

    async def event_generator():
        import queue as sync_queue

        progress_queue = create_progress_queue(request_id)

        try:
            yield f"data: {json.dumps({'type': 'start', 'message': 'เริ่มค้นหาบทความวิชาการ...', 'request_id': request_id}, ensure_ascii=False)}\n\n"

            loop = asyncio.get_event_loop()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            future = loop.run_in_executor(
                executor,
                run_thaijo_research_with_progress,
                req.topic,
                req.max_articles,
                req.max_queries,
                req.min_relevance,
                req.session_id,
                request_id,
            )

            while not future.done():
                try:
                    event = progress_queue.get_nowait()
                    evt_data = asdict(event)
                    # Map agent progress to semantic SSE event types
                    agent_name = evt_data.get("agent_name", "")
                    if "Searcher" in agent_name and evt_data.get("status") == "done":
                        evt_type = "search_progress"
                    elif "Screener" in agent_name and evt_data.get("status") == "done":
                        evt_type = "screening"
                    else:
                        evt_type = "agent_progress"
                    yield f"data: {json.dumps({'type': evt_type, 'data': evt_data}, ensure_ascii=False)}\n\n"
                except sync_queue.Empty:
                    pass
                await asyncio.sleep(0.1)

            # Drain remaining events
            while True:
                try:
                    event = progress_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'agent_progress', 'data': asdict(event)}, ensure_ascii=False)}\n\n"
                except sync_queue.Empty:
                    break

            result = future.result()
            yield f"data: {json.dumps({'type': 'content', 'data': result.model_dump()}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'pipeline': 'thaijo_research'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("ThaiJO research stream failed: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            remove_progress_queue(request_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
