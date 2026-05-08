"""ThaiJO academic article search tool for Data Retrieval Agent."""
import json
import logging
import re
from hashlib import sha256
from typing import Optional

import httpx
from crewai.tools import tool

from src.config import get_settings

logger = logging.getLogger("musya.tools.thaijo")

settings = get_settings()

# Valid ThaiJO URL patterns — both view (article page) and download (actual PDF) are accepted.
# /article/view/ID        = article landing page
# /article/view/ID/FILEID = versioned article page (also valid)
# /article/download/ID/FILEID = actual PDF download (the real PDF link)
_THAIJO_BASE = r'https://(?:he0[1-9]\.)?tci-thaijo\.org/index\.php/[^/]+'
THAIJO_URL_PATTERN = re.compile(
    rf'^{_THAIJO_BASE}/article/view/\d+(?:/\d+)?'
    rf'|^{_THAIJO_BASE}/article/download/\d+/\d+'
)

# Matches /article/download/ARTICLE_ID/FILE_ID — kept to convert LLM-hallucinated download
# URLs that lack a file ID, or to build article_url from pdf_url
_DOWNLOAD_URL_RE = re.compile(
    r'^(https://(?:he0[1-9]\.)?tci-thaijo\.org/index\.php/[^/]+)/article/download/(\d+)/(\d+)'
)

# Matches any embedded ThaiJO URL inside prose text — stripped from summary before LLM sees it
_EMBEDDED_URL_RE = re.compile(
    r'https?://(?:he0[1-9]\.)?tci-thaijo\.org/index\.php/[^\s<>"\u0E00-\u0E7F]+'
)


def _normalize_to_view_url(url: str) -> str:
    """Return the /article/view/ID article page URL for a given ThaiJO URL.

    - /article/download/ID/FILEID → /article/view/ID  (strip file segment)
    - /article/view/ID            → unchanged
    - /article/view/ID/FILEID     → /article/view/ID  (strip version segment)
    - anything else               → unchanged

    Used to derive the article page link from a pdf_url (download link).
    """
    if not url:
        return url
    m = _DOWNLOAD_URL_RE.match(url)
    if m:
        normalized = f"{m.group(1)}/article/view/{m.group(2)}"
        logger.debug("ThaiJO: download→view: %r → %r", url[:80], normalized[:80])
        return normalized
    # Strip optional /FILEID from /article/view/ID/FILEID
    view_m = re.match(
        r'^(https://(?:he0[1-9]\.)?tci-thaijo\.org/index\.php/[^/]+/article/view/\d+)(?:/\d+)?$',
        url,
    )
    if view_m:
        return view_m.group(1)
    return url


def _is_valid_thaijo_url(url: str) -> bool:
    """Return True if url matches known ThaiJO article view patterns."""
    return bool(url and THAIJO_URL_PATTERN.match(url))


def _strip_embedded_urls(text: str) -> str:
    """Remove embedded ThaiJO URLs from summary prose.

    The ThaiJO microservice occasionally embeds clickable URLs (including
    /download/ links) inside the Thai summary text.  When the LLM Searcher
    reads those summaries it may copy the embedded URL into pdf_url instead
    of the validated tool-level pdf_url.  Stripping them at source prevents
    that hallucination path.
    """
    if not text:
        return text
    return _EMBEDDED_URL_RE.sub('', text).strip()


# Regex for year inside Vancouver/NLM reference: e.g. "[internet]. 2017 Aug."
_REF_YEAR_RE = re.compile(r'\[internet\]\.\s+(\d{4})')
# Regex for year inside APA reference: e.g. ". (2022)."
_APA_YEAR_RE = re.compile(r'\.\s*\((\d{4})\)')
# Regex for APA authors + year block: captures authors before ". (YEAR)."
_APA_AUTHORS_RE = re.compile(r'^(.+?)\.\s*\(\d{4}\)')
# Regex for APA journal: journal name before ", VOL(ISSUE)" or ", VOL," — commas excluded from capture
_APA_JOURNAL_RE = re.compile(r'\.\s*([^,\.]+),\s*\d')
# Regex for APA title: text between ". (YEAR). " and the next ". JOURNAL"
_APA_TITLE_RE = re.compile(r'\.\s*\(\d{4}\)\.\s*(.+?)\.\s*[^\.\,]+,\s*\d', re.DOTALL)
# Regex for title quoted in GPT-4.1 summary: **สรุปบทความวิชาการ: "TITLE"**
_SUMMARY_TITLE_RE = re.compile(
    r'\*\*\s*สรุปบทความวิชาการ\s*:\s*["\u201c\u201d](.+?)["\u201c\u201d]\s*\*\*',
    re.DOTALL,
)


def _extract_article_fields(reference: str | None, summary: str) -> dict:
    """Pre-extract title, apa_authors, apa_year, apa_journal from microservice data.

    Title strategy (priority order):
      1. Quoted title in GPT-4.1 summary header  **สรุปบทความวิชาการ: "TITLE"**
      2. APA reference title: text between ". (YEAR). " and ". JOURNAL, vol"
      3. Vancouver reference title: segment between first ". " and journal ". [internet]"
      4. Summary first sentence (plain-text fallback — avoids null)

    Year / Authors / Journal: Vancouver format tried first, APA as fallback.

    Returns dict with keys: title, apa_authors, apa_year, apa_journal (all may be None).
    """
    result = {"title": None, "apa_authors": None, "apa_year": None, "apa_journal": None}

    # ── Priority 1: title from GPT-4.1 summary header ──
    if summary:
        m = _SUMMARY_TITLE_RE.search(summary)
        if m:
            result["title"] = m.group(1).strip()

    if not reference:
        # ── Priority 4 (no reference): first sentence of summary ──
        if not result["title"] and summary:
            result["title"] = _title_from_summary(summary)
        return result

    is_vancouver = "[internet]" in reference
    is_apa = not is_vancouver and _APA_YEAR_RE.search(reference) is not None

    # ── Year ──
    if is_vancouver:
        year_m = _REF_YEAR_RE.search(reference)
        if year_m:
            result["apa_year"] = year_m.group(1)
    elif is_apa:
        year_m = _APA_YEAR_RE.search(reference)
        if year_m:
            result["apa_year"] = year_m.group(1)

    # ── Authors ──
    if is_apa:
        # APA: "AUTHORS. (YEAR). Title…"  — capture everything before ". (YEAR)"
        am = _APA_AUTHORS_RE.match(reference)
        if am:
            result["apa_authors"] = am.group(1).strip()
    if not result["apa_authors"]:
        # Vancouver fallback: everything before first ". "
        first_dot = reference.find(". ")
        if first_dot > 0:
            result["apa_authors"] = reference[:first_dot].strip()

    # ── Journal & Title (Vancouver) ──
    if is_vancouver:
        first_dot = reference.find(". ")
        internet_pos = reference.find("[internet]")
        if internet_pos > 0 and first_dot > 0:
            after_authors = reference[first_dot + 2:]
            internet_in_after = after_authors.find("[internet]")
            if internet_in_after > 0:
                before_internet = after_authors[:internet_in_after]
                last_dot = before_internet.rfind(". ")
                if last_dot >= 0:
                    journal_candidate = before_internet[last_dot + 2:].strip()
                    if journal_candidate:
                        result["apa_journal"] = journal_candidate
                    if not result["title"]:
                        ref_title = before_internet[:last_dot].strip()
                        if ref_title and len(ref_title) >= 5:
                            result["title"] = ref_title

    # ── Journal & Title (APA) ──
    if is_apa:
        jm = _APA_JOURNAL_RE.search(reference)
        if jm:
            result["apa_journal"] = jm.group(1).strip()
        if not result["title"]:
            tm = _APA_TITLE_RE.search(reference)
            if tm:
                raw = tm.group(1).strip()
                if len(raw) >= 5:
                    result["title"] = raw

    # ── Priority 4: summary first sentence (last resort) ──
    if not result["title"] and summary:
        result["title"] = _title_from_summary(summary)

    return result


def _title_from_summary(summary: str) -> str | None:
    """Extract the first meaningful sentence from a plain-text summary as a title fallback.

    Returns None if nothing usable is found (too short, too long, or only punctuation).
    """
    # Strip markdown bold/italic markers and leading whitespace
    text = re.sub(r'\*+', '', summary).strip()
    # Take up to first 300 chars then cut at first sentence boundary
    snippet = text[:300]
    for sep in ('\n', '。', '. ', '! ', '? '):
        idx = snippet.find(sep)
        if idx > 0:
            candidate = snippet[:idx].strip()
            break
    else:
        candidate = snippet.strip()
    # Keep only if 10–300 chars (Thai academic titles can be long)
    if 10 <= len(candidate) <= 300:
        return candidate
    return None


def _normalize_term(term: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', term.lower().strip())


def _cache_key(normalized: str, size: int) -> str:
    """SHA-256 of 'v4:normalized_term|size=N'.

    v4 forces cache miss for v3 entries that may have had view URLs with file
    segments incorrectly stripped (pre-P02/T0 fix).  v3 entries expire via TTL.
    """
    return sha256(f"v4:{normalized}|size={size}".encode()).hexdigest()


def _read_cache(key: str) -> list | None:
    """Return cached results list if cache hit, not expired, and non-empty — else None.

    Empty cached lists are treated as a miss so subsequent strict=False retries
    can reach the API (instead of being blocked by a previously cached 0-result entry).
    """
    try:
        from src.db.pool import query_db
        rows = query_db(
            "SELECT results_json FROM thaijo_search_cache "
            "WHERE cache_key = %s AND expires_at > NOW()",
            (key,),
        )
        if rows:
            results = rows[0]["results_json"]
            if results:   # treat empty cached list as cache miss
                return results
            logger.info("ThaiJO: ignoring empty cached result for key=%s (stale 0-result entry)", key[:8])
    except Exception as e:
        logger.warning("ThaiJO cache read error: %s", e)
    return None


def _write_cache(key: str, term: str, normalized: str, results: list, ttl_days: int) -> None:
    """UPSERT results into thaijo_search_cache."""
    try:
        from src.db.pool import execute_db
        execute_db(
            """
            INSERT INTO thaijo_search_cache
                (cache_key, search_term, normalized_term, results_json, result_count,
                 api_called_at, expires_at, hit_count)
            VALUES (%s, %s, %s, %s::jsonb, %s, NOW(),
                    NOW() + (%s || ' days')::interval, 0)
            ON CONFLICT (cache_key) DO UPDATE SET
                results_json   = EXCLUDED.results_json,
                result_count   = EXCLUDED.result_count,
                api_called_at  = NOW(),
                expires_at     = EXCLUDED.expires_at,
                hit_count      = 0
            """,
            (key, term, normalized, json.dumps(results, ensure_ascii=False),
             len(results), str(ttl_days)),
        )
    except Exception as e:
        logger.warning("ThaiJO cache write error: %s", e)


def _increment_hit(key: str) -> None:
    """Increment hit_count and update last_hit_at for a cache entry."""
    try:
        from src.db.pool import execute_db
        execute_db(
            "UPDATE thaijo_search_cache "
            "SET hit_count = hit_count + 1, last_hit_at = NOW() "
            "WHERE cache_key = %s",
            (key,),
        )
    except Exception as e:
        logger.warning("ThaiJO cache hit increment error: %s", e)


def _search_thaijo_impl(
    term: str,
    size: int = 5,
    page: int = 1,
    strict: bool = True,
) -> str:
    """Core search logic — extracted for testability (called by @tool wrapper)."""
    if not settings.THAIJO_ENABLED:
        return json.dumps(
            {"count": 0, "results": [], "note": "ThaiJO search is disabled"},
            ensure_ascii=False,
        )

    size = max(1, min(size, settings.THAIJO_MAX_SIZE))

    # Cache-first: compute key and check cache before hitting API
    normalized = _normalize_term(term)
    cache_key = _cache_key(normalized, size)
    cached = _read_cache(cache_key)
    if cached is not None:
        logger.info("ThaiJO: cache HIT key=%s (%d articles) term=%r", cache_key[:8], len(cached), term)
        _increment_hit(cache_key)
        return json.dumps({"count": len(cached), "results": cached}, ensure_ascii=False)

    payload = {
        "term": term,
        "page": page,
        "size": size,
        "strict": strict,
        "title": True,
        "author": True,
        "abstract": True,
    }

    logger.info("ThaiJO search (cache MISS): term=%r size=%s page=%s strict=%s", term, size, page, strict)

    # Internal helper to call API with specific timeout
    def _do_search(current_timeout: float):
        with httpx.Client(timeout=current_timeout) as client:
            resp = client.post(settings.THAIJO_API_URL, json=payload)
            resp.raise_for_status()
            return resp.json()

    # Two-tier timeout strategy:
    # 1. Try a quick search (20s) for responsiveness.
    # 2. If results < 5 or times out, try a deeper search (THAIJO_TIMEOUT, e.g. 120s).
    # All exceptions are caught and returned as graceful error JSON — never re-raised.
    data = None
    try:
        logger.info("ThaiJO: Attempting quick search (20s)...")
        data = _do_search(20.0)
        results = data.get("results", [])
        if len(results) >= 5:
            logger.info("ThaiJO: Quick search successful with %s results", len(results))
        else:
            logger.info(
                "ThaiJO: Quick search returned only %s results, retrying with full timeout...",
                len(results),
            )
            data = _do_search(float(settings.THAIJO_TIMEOUT))
    except httpx.TimeoutException as e:
        logger.warning(
            "ThaiJO: timed out (%s), retrying with full timeout (%ss)...",
            type(e).__name__,
            settings.THAIJO_TIMEOUT,
        )
        try:
            data = _do_search(float(settings.THAIJO_TIMEOUT))
        except httpx.TimeoutException:
            logger.warning("ThaiJO: final timeout after %ss: term=%r", settings.THAIJO_TIMEOUT, term)
            return json.dumps(
                {"count": 0, "results": [], "error": "ThaiJO search timed out"},
                ensure_ascii=False,
            )
        except Exception as final_exc:
            logger.warning("ThaiJO: final attempt failed (%s): term=%r", type(final_exc).__name__, term)
            return json.dumps(
                {"count": 0, "results": [], "error": f"ThaiJO unavailable: {type(final_exc).__name__}"},
                ensure_ascii=False,
            )
    except httpx.HTTPStatusError as e:
        logger.warning("ThaiJO HTTP %s: %s term=%r", e.response.status_code, repr(e), term)
        return json.dumps(
            {"count": 0, "results": [], "error": f"ThaiJO HTTP error {e.response.status_code}"},
            ensure_ascii=False,
        )
    except httpx.HTTPError as e:
        logger.warning("ThaiJO HTTP error: %s term=%r", repr(e), term)
        return json.dumps(
            {"count": 0, "results": [], "error": "ThaiJO service unavailable"},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.exception("ThaiJO unexpected error: %s", repr(e))
        return json.dumps(
            {"count": 0, "results": [], "error": f"ThaiJO search failed: {type(e).__name__}"},
            ensure_ascii=False,
        )

    # Process successful response
    count = data.get("count", 0)
    results = data.get("results", [])
    logger.info("ThaiJO final results: count=%s for term=%r", count, term)

    enriched = []
    for article in results:
        raw_url = article.get("pdf_url", "")
        # Accept both /download/ (actual PDF) and /view/ (article page) as valid
        if not _is_valid_thaijo_url(raw_url):
            logger.warning("ThaiJO: invalid pdf_url filtered out: %r", raw_url[:80])
            continue
        # article_url = /article/view/ID page (always available from either form)
        article_url = _normalize_to_view_url(raw_url)

        reference = article.get("reference")
        raw_summary = _strip_embedded_urls(article.get("summary", ""))  # F2: strip embedded URLs

        # Pre-extract structured fields before any LLM sees this data (RC-CE-1, RC-CE-2)
        fields = _extract_article_fields(reference, raw_summary)

        if fields["title"]:
            logger.debug("ThaiJO: extracted title=%r", fields["title"][:60])
        else:
            logger.debug("ThaiJO: no title extracted for url=%r", raw_url[:60])

        enriched.append({
            "pdf_url":     raw_url,      # real PDF download URL (from microservice)
            "article_url": article_url,  # /article/view/ID page URL
            "title":       fields["title"],        # pre-extracted — LLM must not fabricate
            "summary":     raw_summary,
            "reference":   reference,
            "source_type": "thaijo_article",
            "trust_level": "medium",
            "apa_type":    "article",
            "apa_authors": fields["apa_authors"],  # pre-extracted from reference
            "apa_year":    fields["apa_year"],
            "apa_journal": fields["apa_journal"],
            "search_term": term,
        })

    # If strict=True returned 0 results, retry immediately with strict=False (same timeout budget)
    if not enriched and strict:
        logger.info("ThaiJO: strict=True returned 0 enriched articles — retrying with strict=False term=%r", term)
        payload["strict"] = False
        try:
            data_retry = _do_search(float(settings.THAIJO_TIMEOUT))
            for article in data_retry.get("results", []):
                raw_url = article.get("pdf_url", "")
                if not _is_valid_thaijo_url(raw_url):
                    continue
                article_url = _normalize_to_view_url(raw_url)
                reference = article.get("reference")
                raw_summary = _strip_embedded_urls(article.get("summary", ""))  # F2
                fields = _extract_article_fields(reference, raw_summary)
                enriched.append({
                    "pdf_url":     raw_url,
                    "article_url": article_url,
                    "title":       fields["title"],
                    "summary":     raw_summary,
                    "reference":   reference,
                    "source_type": "thaijo_article",
                    "trust_level": "medium",
                    "apa_type":    "article",
                    "apa_authors": fields["apa_authors"],
                    "apa_year":    fields["apa_year"],
                    "apa_journal": fields["apa_journal"],
                    "search_term": term,
                })
            if enriched:
                logger.info("ThaiJO: strict=False retry found %d articles for term=%r", len(enriched), term)
        except Exception as retry_exc:
            logger.warning("ThaiJO: strict=False retry failed (%s): term=%r", type(retry_exc).__name__, term)

    # Only cache non-empty results — empty results must not poison the cache
    # (a later strict=False retry must still be able to reach the API)
    if enriched:
        _write_cache(cache_key, term, normalized, enriched, settings.THAIJO_CACHE_TTL_DAYS)
        logger.info("ThaiJO: cache written for key=%s (%d articles)", cache_key[:8], len(enriched))
    else:
        logger.info("ThaiJO: 0 results — skipping cache write for key=%s term=%r", cache_key[:8], term)

    return json.dumps(
        {"count": len(enriched), "results": enriched},
        ensure_ascii=False,
    )


@tool("search_thaijo")
def search_thaijo(
    term: str,
    size: int = 5,
    page: int = 1,
    strict: bool = True,
) -> str:
    """ค้นหาบทความวิชาการจาก ThaiJO (Thai Journals Online / TCI-THAIJO)
    สำหรับอ้างอิงเชิงวิชาการด้านสาธารณสุข

    ใช้เมื่อ:
    - ต้องการข้อมูลวิจัย/บทความวิชาการสนับสนุนการวิเคราะห์
    - ผู้ใช้ถามเกี่ยวกับงานวิจัย ข้อมูลเชิงวิชาการ
    - ต้องการ evidence-based support จากวารสารไทย
    - เปรียบเทียบผลการศึกษากับข้อมูลในพื้นที่
    - คำถามมีคำว่า วิจัย, บทความ, วารสาร, ศึกษา, evidence, research

    ไม่ควรใช้เมื่อ:
    - ถามแค่ข้อมูลสถิติจากฐานข้อมูล (ใช้ tools อื่น)
    - ข้อมูลจาก Document RAG เพียงพอแล้ว

    Args:
        term: คำค้นหา (ภาษาไทยหรืออังกฤษ) ควรเป็นคำสำคัญ 2-5 คำ
              เช่น "อุบัติเหตุทางถนน ปัจจัยเสี่ยง" หรือ "โรคซึมเศร้า ผู้สูงอายุ"
        size: จำนวนบทความที่ต้องการ (1-10, default 5)
        page: หน้าที่ต้องการ (default 1)
        strict: ค้นหาแบบ exact match (default true)

    Returns:
        JSON string: {"count": N, "results": [{pdf_url, summary, reference, source_type, ...}]}
        แต่ละ result มี:
          - pdf_url: ลิงค์ตรงไปยัง PDF บน TCI-THAIJO (ใช้เป็น open_url)
          - summary: สรุปบทความภาษาไทยโดย AI (max 3 หน้า A4)
          - reference: APA citation text จาก TCI-THAIJO (อาจเป็น null)
          - source_type: "thaijo_article"
          - trust_level: "medium"
          - apa_type: "article"
    """
    return _search_thaijo_impl(term, size, page, strict)
