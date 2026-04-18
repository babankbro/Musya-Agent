"""Common tools shared across all domains."""
import json
from crewai.tools import tool
from src.rag.document_rag import search as doc_search
from src.db.pool import query_db
from src.utils.apa_formatter import format_apa_reference


@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    """Search policy documents, research papers, and guidelines from the document store.
    
    Returns a JSON array of evidence objects with full metadata for citation.
    Each object has: evidence_type, source_ref, title, page_ref, section_label,
    chunk_id, chunk_index, text_snippet, trust_level, original_url, distance,
    document_id, open_url, apa_type, apa_authors, apa_year, apa_publisher,
    bibliography_text.
    
    Results are **deduplicated by source file**: multiple chunks from the same
    document are merged into one evidence item (best snippet kept, page_refs
    accumulated).
    
    Args:
        topic: Domain topic (accident, mental_health, nutrition)
        keywords: Search keywords or natural language query
        n_results: Number of results to return (default 5)
    
    Returns:
        JSON array of structured evidence items with source metadata.
    """
    results = doc_search(query=keywords, topic=topic if topic != "all" else None, n_results=n_results)
    if not results:
        return json.dumps([], ensure_ascii=False)

    # Collect unique source paths for a single DB lookup
    source_set: set[str] = set()
    for r in results:
        source_set.add(r.get("metadata", {}).get("source", "unknown"))

    # Batch lookup document_registry for APA metadata
    registry_map: dict[str, dict] = {}
    if source_set:
        try:
            paths = list(source_set)
            ph = ",".join(["%s"] * len(paths))
            rows = query_db(
                f"SELECT * FROM document_registry WHERE minio_path IN ({ph}) OR file_path IN ({ph})",
                paths + paths,
            )
            for row in rows:
                for key in (row.get("minio_path", ""), row.get("file_path", "")):
                    if key:
                        registry_map[key] = row
        except Exception:
            pass  # graceful fallback — no APA enrichment

        # Second pass: for any sources still unmatched, try title-stem lookup
        unmatched = [s for s in source_set if s not in registry_map]
        if unmatched:
            try:
                for source in unmatched:
                    # Extract bare filename stem (e.g. "accident/report.pdf" → "report")
                    stem = source.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    if len(stem) < 4:
                        continue  # too short to be meaningful
                    rows2 = query_db(
                        "SELECT * FROM document_registry WHERE title ILIKE %s LIMIT 1",
                        (f"%{stem}%",),
                    )
                    if rows2:
                        registry_map[source] = rows2[0]
            except Exception:
                pass

    # Deduplicate by source: merge chunks from same file
    seen: dict[str, dict] = {}  # source -> merged evidence item
    for r in results:
        meta = r.get("metadata", {})
        source = meta.get("source", "unknown")

        if source in seen:
            # Accumulate page_refs and keep best (shortest distance) snippet
            existing = seen[source]
            page = str(meta.get("page_ref", ""))
            if page and page not in existing.get("_page_set", set()):
                existing["_page_set"].add(page)
                existing["page_ref"] = ", ".join(sorted(existing["_page_set"]))
            if r.get("distance", 999) < existing.get("_best_dist", 999):
                existing["text_snippet"] = r["text"][:500]
                existing["_best_dist"] = r.get("distance", 999)
            existing["_chunk_count"] += 1
            continue

        reg = registry_map.get(source, {})
        doc_id = reg.get("document_id")
        bib_text = format_apa_reference(reg) if reg else ""
        raw_title = meta.get("title", "")
        if not raw_title:
            raw_title = reg.get("title", "") or (
                source.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if "/" in source or "." in source else source
            )
        page = str(meta.get("page_ref", ""))

        item = {
            "evidence_type": "document",
            "source_ref": source,
            "title": raw_title,
            "page_ref": page,
            "section_label": meta.get("section_label", ""),
            "chunk_id": r.get("id", ""),
            "chunk_index": meta.get("chunk_index", -1),
            "total_chunks": meta.get("total_chunks", 0),
            "text_snippet": r["text"][:500],
            "trust_level": "high",
            "original_url": f"minio://uploads/{source}",
            "distance": r.get("distance"),
            # --- NEW: document_registry enrichment ---
            "document_id": doc_id,
            "open_url": f"/api/documents/open/{doc_id}" if doc_id else "",
            "apa_type": reg.get("apa_type", "report"),
            "apa_authors": reg.get("apa_authors", ""),
            "apa_year": reg.get("apa_year", ""),
            "apa_publisher": reg.get("apa_publisher", ""),
            "bibliography_text": bib_text,
            # --- internal tracking for dedup ---
            "_page_set": {page} if page else set(),
            "_best_dist": r.get("distance", 999),
            "_chunk_count": 1,
        }
        seen[source] = item

    # Strip internal keys and return
    evidence_items = []
    for item in seen.values():
        item.pop("_page_set", None)
        item.pop("_best_dist", None)
        item.pop("_chunk_count", None)
        evidence_items.append(item)

    return json.dumps(evidence_items, ensure_ascii=False)


@tool("get_indicator_catalog")
def get_indicator_catalog(topic: str) -> str:
    """Get the list of health indicators for a given topic.
    
    Args:
        topic: Domain topic (accident, mental_health, nutrition)
    
    Returns:
        List of indicators with codes, names, definitions, and preferred chart types.
    """
    try:
        rows = query_db(
            "SELECT indicator_code, indicator_name, definition, unit_name, preferred_chart "
            "FROM indicator_catalog WHERE topic = %s ORDER BY indicator_code",
            (topic,),
        )
    except Exception:
        return f"ยังไม่มีตาราง indicator_catalog หรือไม่พบตัวชี้วัดสำหรับ {topic}"

    if not rows:
        return f"ไม่พบตัวชี้วัดสำหรับหัวข้อ {topic}"

    lines = []
    for r in rows:
        lines.append(
            f"- {r['indicator_code']}: {r['indicator_name']} ({r['unit_name']}) "
            f"[chart: {r.get('preferred_chart', 'N/A')}]"
        )
    return "\n".join(lines)


@tool("get_geography_profile")
def get_geography_profile(province_name: str) -> str:
    """Get geographic profile for a province or district.
    
    Args:
        province_name: Name of the province or district in Thai
    
    Returns:
        Geographic details including code, districts, and coordinates.
    """
    try:
        rows = query_db(
            "SELECT * FROM dim_geography WHERE province_name ILIKE %s OR district_name ILIKE %s LIMIT 20",
            (f"%{province_name}%", f"%{province_name}%"),
        )
    except Exception:
        return f"ยังไม่มีตาราง dim_geography หรือไม่พบข้อมูลพื้นที่ {province_name}"

    if not rows:
        return f"ไม่พบข้อมูลพื้นที่สำหรับ {province_name}"

    lines = []
    for r in rows:
        lines.append(
            f"- {r.get('province_name', '')} > {r.get('district_name', '')} > {r.get('subdistrict_name', '')} "
            f"(lat: {r.get('latitude', 'N/A')}, lon: {r.get('longitude', 'N/A')})"
        )
    return "\n".join(lines)
