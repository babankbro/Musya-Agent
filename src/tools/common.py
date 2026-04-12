"""Common tools shared across all domains."""
from crewai.tools import tool
from src.rag.document_rag import search as doc_search
from src.db.pool import query_db


@tool("search_documents")
def search_documents(topic: str, keywords: str, n_results: int = 5) -> str:
    """Search policy documents, research papers, and guidelines from the document store.
    
    Args:
        topic: Domain topic (accident, mental_health, nutrition)
        keywords: Search keywords or natural language query
        n_results: Number of results to return (default 5)
    
    Returns:
        Relevant document chunks with source metadata.
    """
    results = doc_search(query=keywords, topic=topic if topic != "all" else None, n_results=n_results)
    if not results:
        return "ไม่พบเอกสารที่เกี่ยวข้อง"

    output_parts = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        source = meta.get("source", "unknown")
        chunk_idx = meta.get("chunk_index", "?")
        distance = r.get("distance", "?")
        output_parts.append(
            f"--- ผลลัพธ์ {i} (source: {source}, chunk: {chunk_idx}, relevance: {distance}) ---\n"
            f"{r['text'][:800]}"
        )
    return "\n\n".join(output_parts)


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
