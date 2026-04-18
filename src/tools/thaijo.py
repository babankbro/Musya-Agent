"""ThaiJO academic article search tool for Data Retrieval Agent."""
import json
import logging
from typing import Optional

import httpx
from crewai.tools import tool

from src.config import get_settings

logger = logging.getLogger("musya.tools.thaijo")

settings = get_settings()


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
    if not settings.THAIJO_ENABLED:
        return json.dumps(
            {"count": 0, "results": [], "note": "ThaiJO search is disabled"},
            ensure_ascii=False,
        )

    size = max(1, min(size, settings.THAIJO_MAX_SIZE))

    payload = {
        "term": term,
        "page": page,
        "size": size,
        "strict": strict,
        "title": True,
        "author": True,
        "abstract": True,
    }

    logger.info("ThaiJO search: term=%r size=%s page=%s strict=%s", term, size, page, strict)

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
        enriched.append({
            "pdf_url": article.get("pdf_url", ""),
            "summary": article.get("summary", ""),
            "reference": article.get("reference"),
            "source_type": "thaijo_article",
            "trust_level": "medium",
            "apa_type": "article",
            "search_term": term,
        })

    return json.dumps(
        {"count": len(enriched), "results": enriched},
        ensure_ascii=False,
    )
