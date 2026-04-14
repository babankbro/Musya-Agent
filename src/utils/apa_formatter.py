"""APA 7th Edition citation formatter.

Supports document types:
  - report    : รายงาน/เอกสารราชการ
  - book      : หนังสือ
  - article   : บทความวิชาการ
  - website   : เว็บไซต์
  - dataset   : ชุดข้อมูล
  - law       : กฎหมาย/ประกาศราชกิจจาฯ
"""


def format_apa_reference(doc: dict) -> str:
    """Format a document_registry row into APA 7th reference string.

    APA 7 patterns:
      report:  Author. (Year). Title. Publisher.
      book:    Author. (Year). Title (Edition). Publisher.
      article: Author. (Year). Title. Journal, Volume(Issue), Pages. DOI
      website: Author. (Year, Month Day). Title. Site Name. URL
      dataset: Author. (Year). Title [Data set]. Source.
      law:     ชื่อกฎหมาย, พ.ศ. ปี. ราชกิจจานุเบกษา เล่ม x ตอนที่ y.
    """
    apa_type = doc.get("apa_type", "report")
    authors = doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")
    year = doc.get("apa_year", "") or "n.d."
    title = doc.get("title", "ไม่ระบุชื่อ")
    publisher = doc.get("apa_publisher", "")
    doi = doc.get("apa_doi", "")
    url = doc.get("apa_url", "") or doc.get("external_url", "")
    edition = doc.get("apa_edition", "")
    volume = doc.get("apa_volume", "")
    pages = doc.get("apa_pages", "")

    if apa_type == "report":
        ref = f"{authors}. ({year}). {_italicize(title)}."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "book":
        ed = f" ({edition})" if edition else ""
        ref = f"{authors}. ({year}). {_italicize(title)}{ed}."
        if publisher:
            ref += f" {publisher}."

    elif apa_type == "article":
        ref = f"{authors}. ({year}). {title}."
        if publisher:  # journal name
            ref += f" {_italicize(publisher)}"
        if volume:
            ref += f", {volume}"
        if pages:
            ref += f", {pages}"
        ref += "."
        if doi:
            ref += f" https://doi.org/{doi}"
        elif url:
            ref += f" {url}"

    elif apa_type == "website":
        ref = f"{authors}. ({year}). {_italicize(title)}."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "dataset":
        ref = f"{authors}. ({year}). {_italicize(title)} [Data set]."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "law":
        ref = f"{title}, {authors} ({year})."
        if volume:
            ref += f" ราชกิจจานุเบกษา เล่ม {volume}."

    else:
        ref = f"{authors}. ({year}). {_italicize(title)}."

    return ref.strip()


def format_apa_inline(doc: dict, page_ref: str = "") -> str:
    """Format inline citation: (Author, Year, p. X)"""
    authors = doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")
    author_short = _shorten_author(authors)
    year = doc.get("apa_year", "") or "n.d."

    cite = f"({author_short}, {year}"
    if page_ref:
        cite += f", หน้า {page_ref}"
    cite += ")"
    return cite


def format_database_reference(table_name: str, year: str = "") -> str:
    """Format database source as APA dataset reference."""
    yr = year or "2025"
    table_labels = {
        "mart_province_year": "ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี",
        "mart_accident_summary": "ฐานข้อมูลสรุปอุบัติเหตุรายเดือน",
        "mart_accident_hotspot": "ฐานข้อมูลจุดเสี่ยงอุบัติเหตุ",
        "mart_province_road": "ฐานข้อมูลถนนเสี่ยงรายจังหวัด",
        "fact_accident_event": "ฐานข้อมูลเหตุการณ์อุบัติเหตุ",
    }
    label = table_labels.get(table_name, table_name)
    return f"Musya Agent. ({yr}). {label} [Data set]. {table_name}."


def resolve_source_link(evidence: dict) -> dict:
    """Resolve the best available link for an evidence item."""
    ev_type = evidence.get("evidence_type", "")
    source_type = evidence.get("source_type", "internal")

    if ev_type == "document":
        doc_id = evidence.get("document_id")
        page_ref = evidence.get("page_ref", "")
        external_url = evidence.get("external_url", "")

        if source_type == "external" and external_url:
            return {
                "type": "external",
                "primary_url": external_url,
                "fallback_url": f"/api/documents/open/{doc_id}" + (f"?page={page_ref}" if page_ref else ""),
                "label": "เปิดเว็บไซต์ต้นทาง",
                "icon": "external-link",
            }
        else:
            return {
                "type": "internal",
                "primary_url": f"/api/documents/open/{doc_id}" + (f"?page={page_ref}" if page_ref else ""),
                "fallback_url": None,
                "label": f"เปิดเอกสาร" + (f" หน้า {page_ref}" if page_ref else ""),
                "icon": "file-text",
            }

    elif ev_type == "database":
        ev_id = evidence.get("evidence_id", "")
        return {
            "type": "database",
            "primary_url": f"/api/evidence/{ev_id}/query",
            "fallback_url": None,
            "label": "ดู SQL Query และผลลัพธ์",
            "icon": "database",
        }

    return {
        "type": "unknown",
        "primary_url": "",
        "fallback_url": None,
        "label": "ไม่ทราบแหล่งที่มา",
        "icon": "help-circle",
    }


def _italicize(text: str) -> str:
    """Wrap in italic markers (Markdown)."""
    return f"*{text}*"


def _shorten_author(authors: str) -> str:
    """Shorten multi-author string to first + et al."""
    if "," in authors and "&" in authors:
        first = authors.split(",")[0].strip()
        return f"{first} et al."
    return authors
