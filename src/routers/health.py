"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/debug/patch-status")
async def patch_status():
    """Check whether the 429 backoff monkey-patch is active."""
    from crewai.agent.core import Agent as CrewAgent
    patched = getattr(CrewAgent, "_429_patched", False)
    return {"crewai_agent_429_patched": patched}


@router.get("/api/health")
async def health_check():
    """Check connectivity to PostgreSQL, MinIO, and ChromaDB."""
    status = {"status": "ok", "services": {}}

    # Check PostgreSQL
    try:
        from src.db.pool import get_async_pool
        pool = await get_async_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        status["services"]["postgres"] = "ok"
    except Exception as e:
        status["services"]["postgres"] = f"error: {e}"
        status["status"] = "degraded"

    # Check MinIO
    try:
        from src.db.minio_client import get_minio_client
        from src.config import get_settings
        s = get_settings()
        client = get_minio_client()
        client.bucket_exists(s.MINIO_BUCKET)
        status["services"]["minio"] = "ok"
    except Exception as e:
        status["services"]["minio"] = f"error: {e}"
        status["status"] = "degraded"

    # Check pgvector
    try:
        from src.rag.vector_store import health_check as pgvector_health
        ok = pgvector_health()
        if ok:
            status["services"]["pgvector"] = "ok"
        else:
            status["services"]["pgvector"] = "error: connection failed"
            status["status"] = "degraded"
    except Exception as e:
        status["services"]["pgvector"] = f"error: {e}"
        status["status"] = "degraded"

    return status
