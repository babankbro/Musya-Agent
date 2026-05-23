"""Obsidian Knowledge Vault search tools for Data Retrieval Agent."""
import json
import logging
import re

from crewai.tools import tool

from src.config import get_settings

logger = logging.getLogger("musya.tools.obsidian")
settings = get_settings()


def _build_like_conditions(query: str) -> tuple[list[str], list[str]]:
    """Split query into terms and build LIKE patterns.

    Returns (conditions_sql_fragments, params) for use in WHERE clause.
    Each term becomes: (content_stripped LIKE %s OR title LIKE %s)
    """
    terms = [t.strip() for t in query.split() if t.strip()]
    if not terms:
        terms = [query.strip()]

    conditions = []
    params = []
    for term in terms[:5]:  # cap at 5 terms to avoid overly restrictive queries
        pattern = f"%{term}%"
        conditions.append("(content_stripped LIKE %s OR title LIKE %s)")
        params.extend([pattern, pattern])
    return conditions, params


def _search_obsidian_impl(
    query: str,
    province: str | None = None,
    district: str | None = None,
    tag: str | None = None,
    note_type: str | None = None,
    vault_id: str = "health_region_10",
    top_k: int = 5,
) -> str:
    """Core search logic (extracted for testability)."""
    if not settings.OBSIDIAN_ENABLED:
        return json.dumps({"count": 0, "results": [], "note": "Obsidian search disabled"}, ensure_ascii=False)

    if not query.strip():
        return json.dumps({"count": 0, "results": [], "error": "Empty query"}, ensure_ascii=False)

    top_k = max(1, min(top_k, 20))

    try:
        from src.db.pool import query_db

        where_parts = ["vault_id = %s", "content_stripped IS NOT NULL"]
        params: list = [vault_id]

        # Multi-term LIKE conditions
        term_conditions, term_params = _build_like_conditions(query)
        if term_conditions:
            where_parts.append(f"({' OR '.join(term_conditions)})")
            params.extend(term_params)

        if province:
            where_parts.append("province = %s")
            params.append(province)
        if district:
            where_parts.append("district = %s")
            params.append(district)
        if tag:
            where_parts.append("%s = ANY(tags)")
            params.append(tag)
        if note_type:
            where_parts.append("note_type = %s")
            params.append(note_type)

        where_sql = " AND ".join(where_parts)

        # Prioritize: title match > report type > district (rich notes over stubs)
        first_term_pattern = f"%{query.split()[0] if query.split() else query}%"
        params.extend([first_term_pattern, first_term_pattern, top_k])

        sql = f"""
            SELECT
                note_id, vault_id, title, province, district,
                note_type, tags, source_file, year,
                SUBSTRING(content_stripped, 1, 600) AS snippet
            FROM obsidian_notes
            WHERE {where_sql}
            ORDER BY
                CASE WHEN title LIKE %s THEN 0
                     WHEN note_type IN ('report', 'policy', 'research') THEN 1
                     ELSE 2
                END,
                CASE WHEN title LIKE %s THEN LENGTH(content_stripped) ELSE 0 END DESC,
                indexed_at DESC
            LIMIT %s
        """

        rows = query_db(sql, params)

        results = []
        for row in rows:
            results.append({
                "note_id": row["note_id"],
                "vault_id": row["vault_id"],
                "title": row.get("title") or "",
                "province": row.get("province") or "",
                "district": row.get("district") or "",
                "note_type": row.get("note_type") or "",
                "tags": row.get("tags") or [],
                "source_file": row.get("source_file") or "",
                "year": row.get("year"),
                "snippet": (row.get("snippet") or "")[:600],
                "score": 1.0,
            })

        logger.info("Obsidian search: query=%r vault=%s found=%d", query[:50], vault_id, len(results))
        return json.dumps({"count": len(results), "results": results}, ensure_ascii=False)

    except Exception as e:
        logger.exception("Obsidian search error: %s", e)
        return json.dumps({"count": 0, "results": [], "error": str(e)[:120]}, ensure_ascii=False)


def _read_note_impl(note_id: str) -> str:
    """Read full content of a note by note_id."""
    try:
        from src.db.pool import query_db
        rows = query_db(
            "SELECT note_id, title, province, district, note_type, tags, "
            "source_file, year, content_stripped FROM obsidian_notes WHERE note_id = %s",
            (note_id,),
        )
        if not rows:
            return json.dumps({"error": f"Note not found: {note_id}"}, ensure_ascii=False)
        row = rows[0]
        return json.dumps({
            "note_id": row["note_id"],
            "title": row.get("title") or "",
            "province": row.get("province") or "",
            "district": row.get("district") or "",
            "note_type": row.get("note_type") or "",
            "tags": row.get("tags") or [],
            "source_file": row.get("source_file") or "",
            "year": row.get("year"),
            "content": row.get("content_stripped") or "",
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("Obsidian read note error: %s", e)
        return json.dumps({"error": str(e)[:120]}, ensure_ascii=False)


def _list_notes_impl(
    province: str | None = None,
    district: str | None = None,
    tag: str | None = None,
    note_type: str | None = None,
    vault_id: str = "health_region_10",
) -> str:
    """List notes with optional filters."""
    try:
        from src.db.pool import query_db

        where_parts = ["vault_id = %s"]
        params: list = [vault_id]

        if province:
            where_parts.append("province = %s")
            params.append(province)
        if district:
            where_parts.append("district = %s")
            params.append(district)
        if tag:
            where_parts.append("%s = ANY(tags)")
            params.append(tag)
        if note_type:
            where_parts.append("note_type = %s")
            params.append(note_type)

        where_sql = " AND ".join(where_parts)
        rows = query_db(
            f"SELECT note_id, title, province, district, note_type, tags, year, source_file "
            f"FROM obsidian_notes WHERE {where_sql} ORDER BY province, district, title LIMIT 100",
            params,
        )

        results = [{
            "note_id": r["note_id"],
            "title": r.get("title") or "",
            "province": r.get("province") or "",
            "district": r.get("district") or "",
            "note_type": r.get("note_type") or "",
            "tags": r.get("tags") or [],
            "year": r.get("year"),
            "source_file": r.get("source_file") or "",
        } for r in rows]

        return json.dumps({"count": len(results), "notes": results}, ensure_ascii=False)

    except Exception as e:
        logger.exception("Obsidian list notes error: %s", e)
        return json.dumps({"count": 0, "notes": [], "error": str(e)[:120]}, ensure_ascii=False)


# ── CrewAI Tools ──────────────────────────────────────────────────────────────

@tool("search_obsidian")
def search_obsidian(
    query: str,
    province: str = "",
    district: str = "",
    tag: str = "",
    vault_id: str = "health_region_10",
    top_k: int = 5,
) -> str:
    """ค้นหาความรู้จาก Obsidian Knowledge Vault (ข้อมูลสุขภาพเขตสุขภาพที่ 10)

    ใช้เมื่อต้องการ:
    - ข้อมูล KPI รายอำเภอ เช่น อัตราฆ่าตัวตาย, ผลงาน NCD, วัณโรค
    - เปรียบเทียบผลงานระหว่างจังหวัดหรืออำเภอ
    - นโยบาย แผนปฏิบัติการ ผลการตรวจราชการ สสจ.
    - ข้อมูลเฉพาะพื้นที่เขตสุขภาพที่ 10

    Args:
        query: คำค้นหาภาษาไทย เช่น "อัตราฆ่าตัวตาย มุกดาหาร" หรือ "NCD remission ยโสธร"
        province: กรองตามจังหวัด เช่น "อุบลราชธานี" (ว่าง = ทุกจังหวัด)
        district: กรองตามอำเภอ เช่น "อ.เมืองมุกดาหาร" (ว่าง = ทุกอำเภอ)
        tag: กรองตาม tag เช่น "ตรวจราชการ" หรือ "คปสอ"
        vault_id: Vault ที่ต้องการค้นหา (default: health_region_10)
        top_k: จำนวนผลลัพธ์ (1-20, default 5)

    Returns:
        JSON: {count, results: [{note_id, title, province, district, note_type, snippet}]}
    """
    return _search_obsidian_impl(
        query=query,
        province=province or None,
        district=district or None,
        tag=tag or None,
        vault_id=vault_id,
        top_k=top_k,
    )


@tool("read_obsidian_note")
def read_obsidian_note(note_id: str) -> str:
    """อ่านเนื้อหาเต็มของ note ใน Obsidian Knowledge Vault

    ใช้เมื่อ snippet จาก search_obsidian ไม่พอ หรือต้องการรายละเอียดครบถ้วน
    เช่น ตัวเลข KPI ครบทุกตัวชี้วัด หรือแผนงานฉบับเต็ม

    Args:
        note_id: ID ของ note เช่น "health_region_10::มุกดาหาร/อ.เมืองมุกดาหาร/สรุปผล...md"
                 ได้จาก search_obsidian results

    Returns:
        JSON: {note_id, title, province, district, note_type, content (full markdown)}
    """
    return _read_note_impl(note_id)


@tool("list_obsidian_notes")
def list_obsidian_notes(
    province: str = "",
    district: str = "",
    tag: str = "",
    vault_id: str = "health_region_10",
) -> str:
    """แสดงรายการ notes ที่มีใน Obsidian Vault พร้อม metadata

    ใช้เมื่อต้องการรู้ว่ามีข้อมูลจังหวัด/อำเภอไหนบ้าง
    หรือค้นหา note ตามชื่อ/แท็กก่อน search เชิงเนื้อหา

    Args:
        province: กรองตามจังหวัด (ว่าง = ทุกจังหวัด)
        district: กรองตามอำเภอ (ว่าง = ทุกอำเภอ)
        tag: กรองตาม tag เช่น "คปสอ", "ตรวจราชการ", "PDF"
        vault_id: Vault ID (default: health_region_10)

    Returns:
        JSON: {count, notes: [{note_id, title, province, district, note_type, tags, year}]}
    """
    return _list_notes_impl(
        province=province or None,
        district=district or None,
        tag=tag or None,
        vault_id=vault_id,
    )
