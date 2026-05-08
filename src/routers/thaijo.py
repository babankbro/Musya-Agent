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

from src.tools.thaijo import search_thaijo, _is_valid_thaijo_url
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
    article_url: str = ""    # /article/view/ID page link
    title: str | None = None
    summary: str
    reference: str | None
    source_type: str
    trust_level: str
    apa_type: str
    apa_authors: str | None = None
    apa_year: str | None = None
    apa_journal: str | None = None
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

    # D2-2: strict=True returned 0 results → retry with strict=False (mirror agent behavior)
    if req.strict and data.get("count", 0) == 0 and not data.get("error"):
        logger.info("ThaiJO: strict=True returned 0 for term=%r — retrying with strict=False", req.term)
        raw_retry = search_thaijo.func(
            term=req.term,
            size=req.size,
            page=req.page,
            strict=False,
        )
        try:
            data_retry = json.loads(raw_retry)
            if data_retry.get("count", 0) > 0:
                data = data_retry
                data["note"] = "strict=True returned 0 results; retried with strict=False"
                logger.info(
                    "ThaiJO: strict=False retry found %d results for term=%r",
                    data["count"], req.term,
                )
        except json.JSONDecodeError:
            pass  # keep original empty result

    return ThaiJOSearchResponse(
        count=data.get("count", 0),
        results=[ThaiJOArticle(**{k: v for k, v in r.items() if k in ThaiJOArticle.model_fields}) for r in data.get("results", [])],
        note=data.get("note"),
    )


class MultiSearchRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1, max_length=10)
    size: int = Field(5, ge=1, le=10)
    strict: bool = True


class QueryResult(BaseModel):
    query: str
    count: int
    elapsed_ms: int
    cache_hit: bool
    status: str
    note: str | None = None
    error: str | None = None


class MultiSearchResponse(BaseModel):
    total_queries: int
    total_raw_results: int
    total_unique_articles: int
    articles: list[ThaiJOArticle]
    query_results: list[QueryResult]
    failed_queries: list[str]


@router.post("/multi-search", response_model=MultiSearchResponse)
async def thaijo_multi_search(req: MultiSearchRequest) -> MultiSearchResponse:
    """Server-side multi-query ThaiJO search with deduplication.

    Runs each query sequentially, deduplicates by pdf_url, and returns
    merged unique articles with source_query tracking.
    """
    import time as _time

    if not settings.THAIJO_ENABLED:
        return MultiSearchResponse(
            total_queries=len(req.queries), total_raw_results=0,
            total_unique_articles=0, articles=[], query_results=[], failed_queries=req.queries,
        )

    seen_urls: set[str] = set()
    unique_articles: list[ThaiJOArticle] = []
    query_results: list[QueryResult] = []
    failed_queries: list[str] = []
    total_raw = 0

    for q in req.queries:
        t0 = _time.time()
        try:
            raw = search_thaijo.func(term=q, size=req.size, page=1, strict=req.strict)
            data = json.loads(raw)
            elapsed = int((_time.time() - t0) * 1000)
            cache_hit = elapsed < 500

            if req.strict and data.get("count", 0) == 0 and not data.get("error"):
                raw2 = search_thaijo.func(term=q, size=req.size, page=1, strict=False)
                data2 = json.loads(raw2)
                if data2.get("count", 0) > 0:
                    data = data2
                    data["note"] = "strict=False retry"

            count = data.get("count", 0)
            total_raw += count

            for r in data.get("results", []):
                url = r.get("pdf_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    fields = {k: v for k, v in r.items() if k in ThaiJOArticle.model_fields}
                    unique_articles.append(ThaiJOArticle(**fields))

            query_results.append(QueryResult(
                query=q, count=count, elapsed_ms=elapsed, cache_hit=cache_hit,
                status="success" if not data.get("error") else "error",
                note=data.get("note"), error=data.get("error"),
            ))
        except Exception as exc:
            elapsed = int((_time.time() - t0) * 1000)
            logger.warning("multi-search: query failed term=%r: %s", q, exc)
            failed_queries.append(q)
            query_results.append(QueryResult(
                query=q, count=0, elapsed_ms=elapsed, cache_hit=False,
                status="error", error=str(exc)[:80],
            ))

    return MultiSearchResponse(
        total_queries=len(req.queries),
        total_raw_results=total_raw,
        total_unique_articles=len(unique_articles),
        articles=unique_articles,
        query_results=query_results,
        failed_queries=failed_queries,
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


# ======================== Evidence Registry Sync ========================

class SyncEvidenceResult(BaseModel):
    synced: int = 0
    cleared: int = 0
    unchanged: int = 0
    errors: int = 0
    details: list[dict] = []


@router.post("/sync-evidence", response_model=SyncEvidenceResult)
async def sync_evidence_registry() -> SyncEvidenceResult:
    """Sync evidence_registry ThaiJO entries using confirmed URLs from thaijo_search_cache.

    For each thaijo_article row in evidence_registry:
      1. Normalize thaijo_search_term and look up thaijo_search_cache for real pdf_urls
      2. If current open_url is already in cache → unchanged (confirmed)
      3. If thaijo_pdf_url (original, from migration 015) is in cache → synced (restore)
      4. If current open_url fails URL pattern or is not in cache → cleared
      5. If no cache data available → unchanged (no action)

    Idempotent: calling twice leaves confirmed entries unchanged.
    """
    import re as _re
    from src.db.pool import query_db as _query_db, execute_db as _execute_db
    from src.tools.thaijo import _is_valid_thaijo_url

    def _normalize(t: str) -> str:
        return _re.sub(r'\s+', ' ', (t or "").lower().strip())

    try:
        rows = _query_db(
            """SELECT evidence_id, source_ref, open_url,
                      thaijo_search_term, thaijo_pdf_url
               FROM evidence_registry
               WHERE evidence_type = 'thaijo_article'
               ORDER BY evidence_id""",
            [],
        )
    except Exception as e:
        logger.error("sync-evidence: failed to query evidence_registry: %s", e)
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    synced = cleared = unchanged = errors = 0
    details: list[dict] = []

    for row in rows:
        ev_id = row["evidence_id"]
        current_url = row.get("open_url") or ""
        search_term = row.get("thaijo_search_term") or ""
        stored_pdf_url = row.get("thaijo_pdf_url") or ""

        if not search_term:
            unchanged += 1
            details.append({"id": ev_id, "action": "unchanged", "reason": "no_search_term"})
            continue

        try:
            norm = _normalize(search_term)

            # Try exact normalized_term match first, then partial
            cache_rows = _query_db(
                """SELECT results_json FROM thaijo_search_cache
                   WHERE normalized_term = %s AND expires_at > NOW()
                   ORDER BY api_called_at DESC LIMIT 1""",
                (norm,),
            )
            if not cache_rows and len(norm) > 10:
                cache_rows = _query_db(
                    """SELECT results_json FROM thaijo_search_cache
                       WHERE normalized_term LIKE %s AND expires_at > NOW()
                       ORDER BY hit_count DESC LIMIT 1""",
                    (f"%{norm[:30]}%",),
                )

            if not cache_rows:
                unchanged += 1
                details.append({"id": ev_id, "action": "unchanged", "reason": "no_cache_entry"})
                continue

            articles = cache_rows[0].get("results_json") or []
            cached_urls: set[str] = {a.get("pdf_url", "") for a in articles if a.get("pdf_url")}

            # Priority 1: current URL confirmed in cache — no change needed
            if current_url and current_url in cached_urls:
                unchanged += 1
                details.append({"id": ev_id, "action": "unchanged", "reason": "url_confirmed"})
                continue

            # Priority 2: restore from thaijo_pdf_url (migration 015 original URL)
            if stored_pdf_url and stored_pdf_url in cached_urls:
                _execute_db(
                    "UPDATE evidence_registry SET open_url = %s WHERE evidence_id = %s",
                    (stored_pdf_url, ev_id),
                )
                synced += 1
                details.append({"id": ev_id, "action": "synced", "url": stored_pdf_url[:80]})
                continue

            # Priority 3: current URL fails pattern check → clear
            if current_url and not _is_valid_thaijo_url(current_url):
                _execute_db(
                    "UPDATE evidence_registry SET open_url = '' WHERE evidence_id = %s",
                    (ev_id,),
                )
                cleared += 1
                details.append({"id": ev_id, "action": "cleared", "reason": "invalid_pattern"})
                continue

            # Priority 4: current URL valid pattern but not in cache → likely hallucinated
            if current_url and cached_urls:
                _execute_db(
                    "UPDATE evidence_registry SET open_url = '' WHERE evidence_id = %s",
                    (ev_id,),
                )
                cleared += 1
                details.append({"id": ev_id, "action": "cleared", "reason": "not_in_cache"})
                continue

            unchanged += 1
            details.append({"id": ev_id, "action": "unchanged", "reason": "no_match"})

        except Exception as e:
            logger.error("sync-evidence: error for evidence_id=%s: %s", ev_id, e)
            errors += 1
            details.append({"id": ev_id, "action": "error", "reason": str(e)[:80]})

    logger.info(
        "sync-evidence complete: synced=%d cleared=%d unchanged=%d errors=%d total=%d",
        synced, cleared, unchanged, errors, len(rows),
    )
    return SyncEvidenceResult(
        synced=synced,
        cleared=cleared,
        unchanged=unchanged,
        errors=errors,
        details=details,
    )


# ======================== Evidence Registry Debug ========================

class EvidenceRow(BaseModel):
    evidence_id: str
    open_url: str
    source_ref: str
    original_url: str
    title: str
    url_ok: bool
    is_download_url: bool


class EvidenceListResponse(BaseModel):
    total: int
    bad_url_count: int
    rows: list[EvidenceRow]


class FixEvidenceUrlsResult(BaseModel):
    fixed: int
    already_ok: int
    errors: int


@router.get("/evidence", response_model=EvidenceListResponse)
async def list_thaijo_evidence(bad_only: bool = False) -> EvidenceListResponse:
    """List evidence_registry rows for thaijo_article with URL health flags.

    Args:
        bad_only: If true, return only rows with invalid or download URLs.
    """
    import re as _re
    from src.db.pool import query_db as _query_db

    try:
        rows = _query_db(
            "SELECT evidence_id, open_url, source_ref, original_url, title "
            "FROM evidence_registry WHERE evidence_type = 'thaijo_article' "
            "ORDER BY extracted_at DESC LIMIT 500",
            [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    _download_re = _re.compile(r"/article/download/\d+")

    result_rows = []
    for r in rows:
        ou = r.get("open_url") or ""
        sr = r.get("source_ref") or ""
        is_download = bool(_download_re.search(ou) or _download_re.search(sr))
        url_ok = bool(ou and _is_valid_thaijo_url(ou) and not is_download)
        if bad_only and url_ok:
            continue
        result_rows.append(EvidenceRow(
            evidence_id=r.get("evidence_id", ""),
            open_url=ou,
            source_ref=sr,
            original_url=r.get("original_url") or "",
            title=r.get("title") or "",
            url_ok=url_ok,
            is_download_url=is_download,
        ))

    bad_count = sum(1 for r in result_rows if not r.url_ok)
    return EvidenceListResponse(total=len(result_rows), bad_url_count=bad_count, rows=result_rows)


@router.post("/fix-evidence-urls", response_model=FixEvidenceUrlsResult)
async def fix_evidence_urls() -> FixEvidenceUrlsResult:
    """Normalize download/extra-segment URLs in evidence_registry for thaijo_article rows.

    For every thaijo_article row, normalizes open_url, source_ref, and original_url
    by stripping /download/NNN and /view/NNN/MMM → /view/NNN suffixes.
    Idempotent: rows already correct are counted as already_ok.
    """
    import re as _re
    from src.db.pool import query_db as _query_db, execute_db as _execute_db
    from src.tools.thaijo import _normalize_to_view_url

    try:
        rows = _query_db(
            "SELECT evidence_id, open_url, source_ref, original_url "
            "FROM evidence_registry WHERE evidence_type = 'thaijo_article'",
            [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    fixed = already_ok = errors = 0
    for r in rows:
        ev_id = r.get("evidence_id", "")
        ou = r.get("open_url") or ""
        sr = r.get("source_ref") or ""
        orig = r.get("original_url") or ""

        new_ou = _normalize_to_view_url(ou) if ou else ""
        new_sr = _normalize_to_view_url(sr) if sr else ""
        new_orig = _normalize_to_view_url(orig) if orig else ""

        if new_ou == ou and new_sr == sr and new_orig == orig:
            already_ok += 1
            continue

        try:
            _execute_db(
                "UPDATE evidence_registry SET open_url=%s, source_ref=%s, original_url=%s "
                "WHERE evidence_id=%s",
                (new_ou, new_sr, new_orig, ev_id),
            )
            logger.info(
                "fix-evidence-urls: fixed %s open_url %r→%r", ev_id, ou[:60], new_ou[:60]
            )
            fixed += 1
        except Exception as e:
            logger.error("fix-evidence-urls: error for %s: %s", ev_id, e)
            errors += 1

    logger.info("fix-evidence-urls complete: fixed=%d already_ok=%d errors=%d", fixed, already_ok, errors)
    return FixEvidenceUrlsResult(fixed=fixed, already_ok=already_ok, errors=errors)


# ======================== Evidence Sync (P04) ========================

class EvidenceSyncResult(BaseModel):
    cache_rows_scanned: int = 0
    articles_scanned: int = 0
    fields_filled_rule: int = 0
    fields_filled_llm: int = 0
    llm_calls: int = 0
    cache_patched: int = 0
    api_refetched_rows: int = 0
    api_new_articles: int = 0
    evidence_inserted: int = 0
    evidence_skipped: int = 0
    evidence_errors: int = 0
    errors: int = 0
    details: list[dict] = []


@router.post("/evidence-sync", response_model=EvidenceSyncResult)
async def evidence_sync(model: str = "claude-haiku-4-5-20251001") -> EvidenceSyncResult:
    """Sync ThaiJO cache → enrich null fields (rule + LLM) → register in evidence_registry.

    Phase 1: Scan thaijo_search_cache for articles with null title/apa_* fields.
             Rule-based extraction first; LLM (claude-haiku) fallback for remaining nulls.
             Patches thaijo_search_cache JSONB in-place (non-destructive, idempotent).

    Phase 2: Register all cache articles in evidence_registry with full APA metadata
             and summary text from Redis pdf_cache. ON CONFLICT DO NOTHING (idempotent).

    Args:
        model: LLM model for field extraction fallback (default: claude-haiku-4-5).
    """
    from src.agents.thaijo_evidence_sync import run_evidence_sync
    result = run_evidence_sync(llm_model=model)
    return EvidenceSyncResult(**asdict(result))


# ======================== Evidence Registry Audit ========================

class EvidenceAuditEntry(BaseModel):
    evidence_id: str
    title: str
    open_url: str
    in_cache: bool
    cache_url: str = ""  # actual URL found in cache (may differ from open_url)


class EvidenceAuditResponse(BaseModel):
    total: int
    ok: list[EvidenceAuditEntry] = []
    missing_url: list[EvidenceAuditEntry] = []
    unverified_url: list[EvidenceAuditEntry] = []


@router.get("/evidence-audit", response_model=EvidenceAuditResponse)
async def evidence_audit() -> EvidenceAuditResponse:
    """Audit evidence_registry ThaiJO entries: check each open_url against thaijo_search_cache.

    Returns three buckets:
      - ok:             open_url verified in cache (exact or prefix match)
      - missing_url:    open_url is empty or blank
      - unverified_url: open_url present but not found in cache
    """
    import re as _re
    from src.db.pool import query_db as _query_db

    try:
        rows = _query_db(
            "SELECT evidence_id, title, open_url "
            "FROM evidence_registry WHERE evidence_type = 'thaijo_article' "
            "ORDER BY evidence_id",
            [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    ok_list: list[EvidenceAuditEntry] = []
    missing_list: list[EvidenceAuditEntry] = []
    unverified_list: list[EvidenceAuditEntry] = []

    for r in rows:
        ev_id = r.get("evidence_id", "")
        title = r.get("title") or ""
        open_url = r.get("open_url") or ""

        entry = EvidenceAuditEntry(
            evidence_id=ev_id,
            title=title,
            open_url=open_url,
            in_cache=False,
        )

        if not open_url:
            missing_list.append(entry)
            continue

        # Check cache: exact JSONB match first, then article-ID prefix fallback
        in_cache = False
        cache_url = ""
        try:
            exact_rows = _query_db(
                "SELECT 1 FROM thaijo_search_cache "
                "WHERE results_json @> %s::jsonb AND expires_at > NOW() LIMIT 1",
                (json.dumps([{"pdf_url": open_url}]),),
            )
            if exact_rows:
                in_cache = True
                cache_url = open_url
            else:
                # Prefix fallback by article ID
                article_id_match = _re.search(r'/article/view/(\d+)', open_url)
                if article_id_match:
                    article_id = article_id_match.group(1)
                    prefix_rows = _query_db(
                        "SELECT results_json FROM thaijo_search_cache "
                        "WHERE results_json::text LIKE %s AND expires_at > NOW() LIMIT 1",
                        (f'%/article/view/{article_id}%',),
                    )
                    if prefix_rows:
                        articles = prefix_rows[0].get("results_json") or []
                        for art in (articles if isinstance(articles, list) else []):
                            art_url = art.get("pdf_url", "")
                            if f'/article/view/{article_id}' in art_url:
                                in_cache = True
                                cache_url = art_url
                                break
        except Exception as e:
            logger.warning("evidence-audit: cache check failed for %s: %s", ev_id, e)
            in_cache = True  # fail open

        entry.in_cache = in_cache
        entry.cache_url = cache_url
        if in_cache:
            ok_list.append(entry)
        else:
            unverified_list.append(entry)

    total = len(ok_list) + len(missing_list) + len(unverified_list)
    logger.info(
        "evidence-audit: total=%d ok=%d missing=%d unverified=%d",
        total, len(ok_list), len(missing_list), len(unverified_list),
    )
    return EvidenceAuditResponse(
        total=total,
        ok=ok_list,
        missing_url=missing_list,
        unverified_url=unverified_list,
    )


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
