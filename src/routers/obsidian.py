"""Obsidian Knowledge Vault API router."""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from src.config import get_settings
from src.schemas.obsidian import (
    ObsidianSearchRequest,
    ObsidianSearchResponse,
    ObsidianAskRequest,
    ObsidianAskResponse,
    ObsidianStatusResponse,
    ObsidianVaultInfo,
    ObsidianIndexRequest,
    ObsidianIndexResult,
)
from src.tools.obsidian import _search_obsidian_impl, _read_note_impl, _list_notes_impl
from src.agents.progress import create_progress_queue, remove_progress_queue

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])


# ── Search ─────────────────────────────────────────────────────────────────────

@router.post("/search", response_model=ObsidianSearchResponse)
async def search_obsidian_notes(req: ObsidianSearchRequest):
    """Search Obsidian Knowledge Vault using pg_trgm full-text search.

    No LLM involved — direct database query, fast (<2s).
    """
    if not settings.OBSIDIAN_ENABLED:
        return ObsidianSearchResponse(count=0, results=[], query=req.query, vault_id=req.vault_id, note="Obsidian search disabled")

    raw = _search_obsidian_impl(
        query=req.query,
        province=req.province,
        district=req.district,
        tag=req.tag,
        note_type=req.note_type,
        vault_id=req.vault_id,
        top_k=req.top_k,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Internal search error")

    if "error" in data:
        return ObsidianSearchResponse(
            count=0, results=[], query=req.query, vault_id=req.vault_id,
            error=data["error"],
        )

    return ObsidianSearchResponse(
        count=data["count"],
        results=data["results"],
        query=req.query,
        vault_id=req.vault_id,
    )


# ── Note CRUD ──────────────────────────────────────────────────────────────────

@router.get("/notes/{note_id:path}")
async def get_obsidian_note(note_id: str):
    """Read full content of a single note by its ID."""
    raw = _read_note_impl(note_id)
    data = json.loads(raw)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return JSONResponse(content=data)


@router.get("/notes")
async def list_obsidian_notes(
    province: str = Query(default="", description="กรองตามจังหวัด"),
    district: str = Query(default="", description="กรองตามอำเภอ"),
    tag: str = Query(default="", description="กรองตาม tag"),
    note_type: str = Query(default="", description="MOC | district | report | research | policy"),
    vault_id: str = Query(default="health_region_10"),
):
    """List notes with optional filters."""
    raw = _list_notes_impl(
        province=province or None,
        district=district or None,
        tag=tag or None,
        note_type=note_type or None,
        vault_id=vault_id,
    )
    data = json.loads(raw)
    return JSONResponse(content=data)


# ── Ask pipeline ───────────────────────────────────────────────────────────────

@router.post("/ask", response_model=ObsidianAskResponse)
async def ask_obsidian(req: ObsidianAskRequest):
    """Run the 2-agent Obsidian Ask pipeline (synchronous).

    Pipeline: ObsidianSearcher → HealthKnowledgeAnswerWriter
    Expected runtime: 30–120 seconds.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="คำถามต้องไม่ว่างเปล่า")

    if not settings.OBSIDIAN_ENABLED:
        raise HTTPException(status_code=503, detail="Obsidian Knowledge Vault is disabled")

    logger.info("[obsidian] ask: %s | province=%s", req.question[:80], req.province)

    from src.agents.obsidian_agent import run_obsidian_ask
    try:
        result = run_obsidian_ask(
            question=req.question,
            province=req.province or "",
            vault_id=req.vault_id,
        )
        return JSONResponse(content=result.model_dump())
    except Exception as exc:
        logger.exception("[obsidian] ask error: %s", exc)
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.post("/ask/stream")
async def ask_obsidian_stream(req: ObsidianAskRequest):
    """Stream the Obsidian Ask pipeline via Server-Sent Events.

    Event types:
      - start: pipeline metadata
      - progress: agent step updates
      - result: final ObsidianAskResponse JSON
      - error: pipeline error
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="คำถามต้องไม่ว่างเปล่า")

    if not settings.OBSIDIAN_ENABLED:
        raise HTTPException(status_code=503, detail="Obsidian Knowledge Vault is disabled")

    request_id = str(uuid.uuid4())
    q = create_progress_queue(request_id)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'start', 'request_id': request_id, 'pipeline': 'obsidian_ask', 'agents': ['Obsidian Knowledge Searcher', 'Health Knowledge Answer Writer']}, ensure_ascii=False)}\n\n"

        from src.agents.obsidian_agent import run_obsidian_ask_with_progress
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            None,
            lambda: run_obsidian_ask_with_progress(
                question=req.question,
                province=req.province or "",
                vault_id=req.vault_id,
                request_id=request_id,
            ),
        )

        while not future.done():
            try:
                import queue as _queue
                event = q.get_nowait()
                payload = {
                    "type": "progress",
                    "agent_name": event.agent_name,
                    "agent_icon": event.agent_icon,
                    "status": event.status,
                    "message": event.message,
                    "elapsed_seconds": event.elapsed_seconds,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception:
                await asyncio.sleep(0.3)

        import queue as _queue
        while True:
            try:
                event = q.get_nowait()
                payload = {
                    "type": "progress",
                    "agent_name": event.agent_name,
                    "agent_icon": event.agent_icon,
                    "status": event.status,
                    "message": event.message,
                    "elapsed_seconds": event.elapsed_seconds,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception:
                break

        try:
            result = await future
            yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            remove_progress_queue(request_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Status & Vault management ──────────────────────────────────────────────────

@router.get("/status", response_model=ObsidianStatusResponse)
async def obsidian_status():
    """Return vault registry and note counts."""
    try:
        from src.db.pool import query_db
        vaults = query_db(
            "SELECT vault_id, name, vault_path, description, note_count, indexed_at "
            "FROM obsidian_vaults ORDER BY vault_id",
            (),
        )
        total = query_db("SELECT COUNT(*) AS cnt FROM obsidian_notes", ())[0]["cnt"]

        vault_list = [
            ObsidianVaultInfo(
                vault_id=v["vault_id"],
                name=v["name"],
                vault_path=v["vault_path"],
                description=v.get("description"),
                note_count=v.get("note_count") or 0,
                indexed_at=str(v["indexed_at"]) if v.get("indexed_at") else None,
            )
            for v in vaults
        ]
        return ObsidianStatusResponse(
            enabled=settings.OBSIDIAN_ENABLED,
            vaults=vault_list,
            total_notes=total,
        )
    except Exception as exc:
        logger.exception("[obsidian] status error: %s", exc)
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@router.get("/vaults")
async def list_vaults():
    """List all registered vaults."""
    try:
        from src.db.pool import query_db
        rows = query_db(
            "SELECT vault_id, name, vault_path, description, note_count, indexed_at "
            "FROM obsidian_vaults ORDER BY vault_id",
            (),
        )
        return JSONResponse(content={"vaults": [dict(r) for r in rows]})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


# ── Indexer ────────────────────────────────────────────────────────────────────

@router.post("/index", response_model=ObsidianIndexResult)
async def index_vault(req: ObsidianIndexRequest):
    """Trigger vault indexing (walks FS and UPSERTs notes into DB).

    This is a long-running operation (~1-10 minutes for large vaults).
    Runs synchronously — consider calling from CLI script for production.
    """
    logger.info("[obsidian] index requested for vault_id=%s", req.vault_id)
    loop = asyncio.get_event_loop()
    try:
        from scripts.index_obsidian import index_vault as _index
        result = await loop.run_in_executor(None, lambda: _index(req.vault_id))
        return JSONResponse(content=result)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Index script not found. Run: python scripts/index_obsidian.py",
        )
    except Exception as exc:
        logger.exception("[obsidian] index error: %s", exc)
        raise HTTPException(status_code=500, detail={"error": str(exc)})
