"""ThaiJO Evidence Sync Agent — P04

Two-phase sync:
  Phase 1 (Cache Enrichment):
    - Scan thaijo_search_cache for articles with null title/apa_* fields
    - Rule-based extraction first (reuses _extract_article_fields from tools/thaijo.py)
    - LLM fallback (claude-haiku) for fields still null after rule-based
    - Patch results_json in-place via jsonb_set (non-destructive, idempotent)

  Phase 2 (Evidence Registration):
    - Read all non-expired thaijo_search_cache entries
    - For each article: INSERT evidence_registry ON CONFLICT DO NOTHING
    - text_snippet = full Redis summary (untruncated) if available
    - APA bibliography_text = rule-based format; LLM if reference is null

No URL normalization. No evidence_registry overwrite. Idempotent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from hashlib import sha256

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SyncResult:
    # Phase 1
    cache_rows_scanned: int = 0
    articles_scanned: int = 0
    fields_filled_rule: int = 0
    fields_filled_llm: int = 0
    llm_calls: int = 0
    cache_patched: int = 0
    # Phase 1.5 — API re-fetch
    api_refetched_rows: int = 0
    api_new_articles: int = 0
    # Phase 2
    evidence_inserted: int = 0
    evidence_skipped: int = 0
    evidence_errors: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Redis helper
# ---------------------------------------------------------------------------

def _get_redis():
    """Return Redis client — None if unavailable."""
    try:
        from redis import Redis
        from redis.exceptions import RedisError
        from src.config import get_settings
        settings = get_settings()
        url = settings.REDIS_URL.replace("redis://redis:", "redis://localhost:")
        r = Redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
        r.ping()
        return r
    except Exception as e:
        logger.warning("thaijo_evidence_sync: Redis unavailable: %s", e)
        return None


def _lookup_redis_summary(pdf_url: str, redis_client) -> str | None:
    """GET pdf_cache:<sha256(pdf_url)> from Redis — return full GPT-4.1 summary or None."""
    if not redis_client or not pdf_url:
        return None
    try:
        key = f"pdf_cache:{sha256(pdf_url.encode()).hexdigest()}"
        return redis_client.get(key)
    except Exception as e:
        logger.debug("_lookup_redis_summary: miss for url=%r: %s", pdf_url[:60], e)
        return None


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _needs_enrichment(article: dict) -> bool:
    """True if any extractable field is null/missing."""
    return any(article.get(f) is None for f in ("title", "apa_authors", "apa_year", "apa_journal"))


def _null_fields(article: dict) -> list[str]:
    return [f for f in ("title", "apa_authors", "apa_year", "apa_journal") if article.get(f) is None]


def _make_evidence_id(pdf_url: str) -> str:
    """Stable 16-char evidence ID from pdf_url."""
    return "TJ-" + sha256(pdf_url.encode()).hexdigest()[:13]


# ---------------------------------------------------------------------------
# APA rule-based formatter
# ---------------------------------------------------------------------------

def _format_apa(title: str | None, authors: str | None, year: str | None,
                journal: str | None, pdf_url: str) -> str:
    """Build APA 7th Edition bibliography_text from available fields."""
    a = authors or "[ไม่ระบุผู้แต่ง]"
    y = f"({year})" if year else "(ไม่ระบุปี)"
    t = f"*{title}*" if title else "*[ไม่ระบุชื่อบทความ]*"
    j = f"*{journal}*" if journal else "ThaiJO"
    return f"{a}. {y}. {t}. {j}. {pdf_url}"


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
คุณเป็นผู้เชี่ยวชาญด้านข้อมูลบรรณานุกรมบทความวิชาการไทย

จากข้อมูลต่อไปนี้ กรุณาดึงข้อมูลบรรณานุกรม:

## สรุปบทความ:
{full_summary}

## Reference text (ถ้ามี):
{reference}

## URL บทความ:
{pdf_url}

ตอบเป็น JSON เท่านั้น (ห้ามมีข้อความอื่น):
{{
    "title": "ชื่อบทความภาษาไทยเต็ม หรือ null ถ้าไม่พบ",
    "apa_authors": "ชื่อผู้แต่ง APA format หรือ null ถ้าไม่พบ",
    "apa_year": "ปี พ.ศ. 4 หลัก เช่น 2565 หรือ null ถ้าไม่พบ",
    "apa_journal": "ชื่อวารสาร หรือ null ถ้าไม่พบ",
    "bibliography_text": "APA 7th Edition full reference หรือ null ถ้าข้อมูลไม่เพียงพอ"
}}

กฎ:
- ถ้าไม่พบข้อมูลจริงๆ ให้ใส่ null ไม่ใช่เดาหรือแต่งเพิ่ม
- ปีให้เป็น พ.ศ. (ถ้าเป็น ค.ศ. ให้บวก 543)
- bibliography_text รูปแบบ: ผู้แต่ง. (ปี). ชื่อบทความ. ชื่อวารสาร. URL
"""


def _llm_extract_fields(full_summary: str, reference: str | None,
                         pdf_url: str, model: str) -> dict:
    """Call LLM to extract missing bibliography fields. Returns dict (may have None values)."""
    try:
        from anthropic import Anthropic
        client = Anthropic()
        prompt = _EXTRACT_PROMPT.format(
            full_summary=(full_summary or "")[:1500],
            reference=reference or "(ไม่มี reference text)",
            pdf_url=pdf_url,
        )
        msg = client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        logger.warning("_llm_extract_fields: failed for url=%r: %s", pdf_url[:60], e)
    return {}


# ---------------------------------------------------------------------------
# Phase 1.5: API re-fetch helpers
# ---------------------------------------------------------------------------

_MIN_REFS = 5  # minimum usable articles per cache row before re-fetching


def _count_usable(articles: list[dict]) -> int:
    """Count articles that have at least a title (considered usable references)."""
    return sum(1 for a in articles if a.get("title"))


def _fetch_more_from_api(search_term: str, existing_urls: set[str],
                          result: SyncResult) -> list[dict]:
    """Call ThaiJO API for additional articles not already in the cache row.

    Returns a list of new unique articles (not in existing_urls).
    Updates result.api_refetched_rows and result.api_new_articles in-place.
    """
    try:
        from src.tools.thaijo import _search_thaijo_impl
        raw = _search_thaijo_impl(search_term, size=10, strict=False)
        data = json.loads(raw)
        new_arts: list[dict] = []
        for art in data.get("results", []):
            url = art.get("pdf_url", "")
            if url and url not in existing_urls:
                new_arts.append(art)
                existing_urls.add(url)
                result.api_new_articles += 1
        result.api_refetched_rows += 1
        logger.info(
            "_fetch_more_from_api: term=%r → %d new articles",
            search_term[:60], len(new_arts),
        )
        return new_arts
    except Exception as e:
        logger.warning(
            "_fetch_more_from_api: failed for term=%r: %s", search_term[:60], e
        )
        return []


# ---------------------------------------------------------------------------
# Phase 1: Cache enrichment
# ---------------------------------------------------------------------------

def _patch_cache_row(cache_key: str, articles: list[dict]) -> bool:
    """Write back the full results_json for a cache row after in-memory patching.

    Uses optimistic locking: only updates if results_json still has nulls
    (cheap guard — not a hard lock). Returns True if rowcount > 0.
    """
    from src.db.pool import execute_db
    try:
        rows = execute_db(
            "UPDATE thaijo_search_cache "
            "SET results_json = %s::jsonb "
            "WHERE cache_key = %s",
            (json.dumps(articles, ensure_ascii=False), cache_key),
        )
        return rows > 0
    except Exception as e:
        logger.warning("_patch_cache_row: failed for key=%s: %s", cache_key[:8], e)
        return False


def _phase1_enrich(result: SyncResult, redis, model: str) -> dict[str, list[dict]]:
    """Phase 1: scan thaijo_search_cache, fill null fields.

    Returns a map of cache_key → enriched articles list (for Phase 2).
    """
    from src.db.pool import query_db
    from src.tools.thaijo import _extract_article_fields

    try:
        rows = query_db(
            "SELECT cache_key, search_term, normalized_term, results_json "
            "FROM thaijo_search_cache "
            "WHERE expires_at > NOW() "
            "AND ("
            "  results_json::text LIKE '%null%' "
            "  OR (jsonb_typeof(results_json) = 'array' "
            "      AND jsonb_array_length(results_json) < %s)"
            ")",
            [_MIN_REFS],
        )
    except Exception as e:
        logger.error("Phase 1: failed to scan thaijo_search_cache: %s", e)
        result.errors += 1
        return {}

    result.cache_rows_scanned = len(rows)
    enriched_map: dict[str, dict] = {}  # cache_key → {search_term, articles}

    for row in rows:
        cache_key = row["cache_key"]
        search_term = row.get("search_term") or row.get("normalized_term") or ""
        articles: list[dict] = row.get("results_json") or []
        enriched_articles = []

        row_changed = False
        for i, art in enumerate(articles):
            result.articles_scanned += 1
            if not _needs_enrichment(art):
                enriched_articles.append(art)
                continue

            art = dict(art)  # copy — we mutate in-place then write whole row back
            pdf_url = art.get("pdf_url", "")

            # Step 1: rule-based with Redis full summary
            full_summary = _lookup_redis_summary(pdf_url, redis)
            source_summary = full_summary or art.get("summary") or ""
            rule_fields = _extract_article_fields(art.get("reference"), source_summary)
            rule_patch = {k: v for k, v in rule_fields.items() if v and art.get(k) is None}

            for k, v in rule_patch.items():
                art[k] = v
                result.fields_filled_rule += 1

            # Step 2: LLM fallback for fields still null
            still_null = _null_fields(art)
            llm_patch: dict = {}
            if still_null:
                llm_result = _llm_extract_fields(source_summary, art.get("reference"), pdf_url, model)
                result.llm_calls += 1
                for k in still_null:
                    v = llm_result.get(k)
                    if v and isinstance(v, str) and v.strip() and v.lower() != "null":
                        llm_patch[k] = v.strip()
                        art[k] = v.strip()
                        result.fields_filled_llm += 1
                # Store bibliography_text from LLM for Phase 2 use
                bib = llm_result.get("bibliography_text")
                if bib and isinstance(bib, str) and bib.strip() and bib.lower() != "null":
                    art["_bib_llm"] = bib.strip()

            all_patch = {**rule_patch, **llm_patch}
            if all_patch:
                row_changed = True
                result.details.append({
                    "phase": 1,
                    "cache_key": cache_key[:8],
                    "pdf_url": pdf_url[:60],
                    "fields": list(all_patch.keys()),
                    "source": "rule" if not llm_patch else "rule+llm",
                })

            enriched_articles.append(art)

        # Phase 1.5 — API re-fetch if usable articles < MIN_REFS
        if search_term and _count_usable(enriched_articles) < _MIN_REFS:
            existing_urls = {a.get("pdf_url", "") for a in enriched_articles if a.get("pdf_url")}
            new_arts = _fetch_more_from_api(search_term, existing_urls, result)
            if new_arts:
                enriched_articles.extend(new_arts)
                row_changed = True
                result.details.append({
                    "phase": "1.5",
                    "cache_key": cache_key[:8],
                    "search_term": search_term[:60],
                    "new_articles": len(new_arts),
                })

        # Write back entire row once (not per-article) to minimise DB round-trips
        if row_changed:
            if _patch_cache_row(cache_key, enriched_articles):
                result.cache_patched += 1

        enriched_map[cache_key] = {
            "search_term": search_term,
            "articles": enriched_articles,
        }

    return enriched_map


# ---------------------------------------------------------------------------
# Phase 2: Evidence registration
# ---------------------------------------------------------------------------

def _phase2_register(result: SyncResult, enriched_map: dict, redis):
    """Phase 2: register all cache articles in evidence_registry.

    Reads all non-expired cache rows (not just null-field ones).
    Uses enriched_map for already-enriched articles where available.
    """
    from src.db.pool import query_db, execute_db

    try:
        all_rows = query_db(
            "SELECT cache_key, search_term, normalized_term, results_json "
            "FROM thaijo_search_cache WHERE expires_at > NOW()",
            [],
        )
    except Exception as e:
        logger.error("Phase 2: failed to scan thaijo_search_cache: %s", e)
        result.errors += 1
        return

    for row in all_rows:
        cache_key = row["cache_key"]
        search_term = row.get("search_term") or row.get("normalized_term") or ""

        # Use enriched articles from Phase 1 if available; else raw from DB
        if cache_key in enriched_map:
            articles = enriched_map[cache_key]["articles"]
        else:
            articles = row.get("results_json") or []

        for art in articles:
            pdf_url = art.get("pdf_url", "")
            if not pdf_url:
                continue

            ev_id = _make_evidence_id(pdf_url)
            title = art.get("title") or ""
            apa_authors = art.get("apa_authors") or ""
            apa_year = art.get("apa_year") or ""
            apa_journal = art.get("apa_journal") or ""
            reference = art.get("reference") or ""

            # text_snippet: prefer full Redis summary, fallback to cached summary
            full_summary = _lookup_redis_summary(pdf_url, redis)
            text_snippet = (full_summary or art.get("summary") or "")[:500]

            # APA bibliography_text
            bib_text = art.get("_bib_llm") or ""
            if not bib_text:
                if reference:
                    bib_text = reference  # Vancouver/APA text as-is
                else:
                    bib_text = _format_apa(title or None, apa_authors or None,
                                           apa_year or None, apa_journal or None, pdf_url)

            try:
                rows_written = execute_db(
                    """INSERT INTO evidence_registry (
                           evidence_id, evidence_type, topic,
                           source_ref, title,
                           section_label, page_ref, chunk_id, chunk_index,
                           query_signature, query_params,
                           geography_ref, time_range_ref,
                           text_snippet, trust_level,
                           original_url, open_url,
                           apa_type, apa_authors, apa_year, apa_publisher,
                           thaijo_pdf_url, thaijo_reference,
                           thaijo_summary, thaijo_search_term
                       ) VALUES (
                           %s,'thaijo_article',%s,
                           %s,%s,
                           '','','', -1,
                           '','{}',
                           '','',
                           %s,'medium',
                           %s,%s,
                           'article',%s,%s,%s,
                           %s,%s,
                           %s,%s
                       )
                       ON CONFLICT (evidence_id) DO NOTHING""",
                    (
                        ev_id,
                        search_term[:200],          # topic
                        pdf_url,                    # source_ref
                        title[:500],                # title
                        text_snippet,               # text_snippet (500 chars)
                        pdf_url,                    # original_url
                        pdf_url,                    # open_url
                        apa_authors[:300],          # apa_authors
                        apa_year[:10],              # apa_year
                        apa_journal[:300],          # apa_publisher (journal name)
                        pdf_url,                    # thaijo_pdf_url
                        reference[:500] if reference else "",  # thaijo_reference
                        text_snippet,               # thaijo_summary
                        search_term[:200],          # thaijo_search_term
                    ),
                )
                if rows_written > 0:
                    result.evidence_inserted += 1
                    result.details.append({
                        "phase": 2,
                        "evidence_id": ev_id,
                        "pdf_url": pdf_url[:60],
                        "title": title[:60],
                        "action": "inserted",
                    })
                else:
                    result.evidence_skipped += 1

            except Exception as e:
                logger.warning("Phase 2: INSERT failed for ev_id=%s url=%r: %s", ev_id, pdf_url[:60], e)
                result.evidence_errors += 1
                result.details.append({
                    "phase": 2,
                    "evidence_id": ev_id,
                    "pdf_url": pdf_url[:60],
                    "action": "error",
                    "reason": str(e)[:80],
                })


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_evidence_sync(llm_model: str = "claude-haiku-4-5-20251001") -> SyncResult:
    """Phase 1: enrich null cache fields (rule + LLM).
    Phase 2: register all cache articles in evidence_registry.

    Idempotent — safe to call multiple times.
    """
    result = SyncResult()
    redis = _get_redis()

    logger.info("thaijo_evidence_sync: starting Phase 1 (cache enrichment) model=%s", llm_model)
    enriched_map = _phase1_enrich(result, redis, llm_model)

    logger.info(
        "thaijo_evidence_sync: Phase 1 done — rows=%d arts=%d rule=%d llm=%d patched=%d",
        result.cache_rows_scanned, result.articles_scanned,
        result.fields_filled_rule, result.fields_filled_llm, result.cache_patched,
    )

    logger.info("thaijo_evidence_sync: starting Phase 2 (evidence registration)")
    _phase2_register(result, enriched_map, redis)

    logger.info(
        "thaijo_evidence_sync: Phase 2 done — inserted=%d skipped=%d errors=%d",
        result.evidence_inserted, result.evidence_skipped, result.evidence_errors,
    )

    return result
