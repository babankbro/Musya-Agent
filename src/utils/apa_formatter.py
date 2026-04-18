"""APA 7th Edition citation formatter for Thai public health inspection reports.

Supports document types:
  - report    : รายงานตรวจราชการ/เอกสารราชการ
  - book      : หนังสือ
  - article   : บทความวิชาการ
  - website   : เว็บไซต์ (HDC, กระทรวง)
  - dataset   : ชุดข้อมูล (Musya Agent Database)
  - law       : กฎหมาย/ประกาศราชกิจจาฯ

APA 7th Edition patterns (Thai adaptation):
  report:  หน่วยงาน. (ปี พ.ศ.). *ชื่อรายงาน*. สำนักพิมพ์.
  book:    ผู้แต่ง. (ปี). *ชื่อหนังสือ* (พิมพ์ครั้งที่). สำนักพิมพ์.
  article: ผู้แต่ง. (ปี). ชื่อบทความ. *ชื่อวารสาร*, ปีที่(ฉบับที่), หน้า. DOI
  website: ผู้เขียน. (ปี). *ชื่อหน้า*. ชื่อเว็บไซต์. URL
  dataset: หน่วยงาน. (ปี). *ชื่อชุดข้อมูล* [Data set]. แหล่งข้อมูล.
  law:     ชื่อกฎหมาย, พ.ศ. ปี. ราชกิจจานุเบกษา เล่ม x ตอนที่ y.
"""


def format_apa_reference(doc: dict) -> str:
    """Format a document into APA 7th edition reference string.

    Accepts document_registry rows or evidence items with apa_* fields.
    """
    apa_type = doc.get("apa_type", "report")
    authors = (doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")).rstrip(".")
    year = doc.get("apa_year", "") or "n.d."
    title = doc.get("title", "ไม่ระบุชื่อ")
    publisher = doc.get("apa_publisher", "")
    doi = doc.get("apa_doi", "")
    url = doc.get("apa_url", "") or doc.get("external_url", "")
    edition = doc.get("apa_edition", "")
    volume = doc.get("apa_volume", "")
    issue = doc.get("apa_issue", "")
    pages = doc.get("apa_pages", "")

    if apa_type == "report":
        ref = f"{authors}. ({year}). {_italicize(title)}."
        if publisher:
            ref += f" {publisher}."
        if url:
            ref += f" {url}"

    elif apa_type == "book":
        ed = f" (พิมพ์ครั้งที่ {edition})" if edition else ""
        ref = f"{authors}. ({year}). {_italicize(title)}{ed}."
        if publisher:
            ref += f" {publisher}."

    elif apa_type == "article":
        ref = f"{authors}. ({year}). {title}."
        if publisher:  # journal name
            ref += f" {_italicize(publisher)}"
        if volume:
            ref += f", {volume}"
            if issue:
                ref += f"({issue})"
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
        ref = f"{title}, พ.ศ. {year}."
        if volume:
            ref += f" ราชกิจจานุเบกษา เล่ม {volume}"
            if issue:
                ref += f" ตอนที่ {issue}"
            ref += "."

    else:
        ref = f"{authors}. ({year}). {_italicize(title)}."

    return ref.strip()


def format_apa_inline(doc: dict, page_ref: str = "") -> str:
    """Format inline citation: (Author, Year, หน้า X).

    For Thai inspection reports: (สสจ.{จังหวัด}, {ปี}, หน้า {หน้า})
    """
    authors = doc.get("apa_authors", "") or doc.get("title", "ไม่ระบุ")
    author_short = _shorten_author(authors)
    year = doc.get("apa_year", "") or "n.d."

    cite = f"({author_short}, {year}"
    if page_ref:
        cite += f", หน้า {page_ref}"
    cite += ")"
    return cite


def format_notebooklm_reference(
    province: str,
    year: int,
    round_no: int = 0,
    notebook_id: str = "",
) -> dict:
    """Format a NotebookLM inspection report source as APA reference.

    Returns a dict with apa_* fields ready for format_apa_reference().

    Example output:
        สำนักงานสาธารณสุขจังหวัดอุบลราชธานี. (2567).
        *รายงานตรวจราชการกระทรวงสาธารณสุข รอบที่ 2 ปีงบประมาณ 2567*.
        กระทรวงสาธารณสุข.
    """
    authors = f"สำนักงานสาธารณสุขจังหวัด{province}"
    round_str = f" รอบที่ {round_no}" if round_no else ""
    title = f"รายงานตรวจราชการกระทรวงสาธารณสุข{round_str} ปีงบประมาณ {year}"

    return {
        "apa_type": "report",
        "apa_authors": authors,
        "apa_year": str(year),
        "title": title,
        "apa_publisher": "กระทรวงสาธารณสุข",
        "source_ref": f"notebooklm:{notebook_id}:{title}" if notebook_id else title,
    }


def format_notebooklm_inline(province: str, year: int, page_ref: str = "") -> str:
    """Format NotebookLM source as APA inline citation.

    Example: (สสจ.อุบลราชธานี, 2567, หน้า 45)
    """
    short_author = f"สสจ.{province}"
    cite = f"({short_author}, {year}"
    if page_ref:
        cite += f", หน้า {page_ref}"
    cite += ")"
    return cite


def format_database_reference(table_name: str, year: str = "") -> str:
    """Format database source as APA dataset reference.

    Example: Musya Agent. (2568). *ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี* [Data set]. Musya Agent Database.
    """
    yr = year or "2568"
    table_labels = {
        "mart_province_year": "ฐานข้อมูลสรุปอุบัติเหตุรายจังหวัดรายปี",
        "mart_accident_summary": "ฐานข้อมูลสรุปอุบัติเหตุรายเดือน",
        "mart_accident_hotspot": "ฐานข้อมูลจุดเสี่ยงอุบัติเหตุ",
        "mart_province_road": "ฐานข้อมูลถนนเสี่ยงรายจังหวัด",
        "fact_accident_event": "ฐานข้อมูลเหตุการณ์อุบัติเหตุ",
    }
    label = table_labels.get(table_name, table_name)
    return f"Musya Agent. ({yr}). {_italicize(label)} [Data set]. Musya Agent Database."


def format_database_inline(table_name: str, year: str = "") -> str:
    """Format database source as APA inline citation.

    Example: (Musya Agent Database, 2568)
    """
    yr = year or "2568"
    return f"(Musya Agent Database, {yr})"


def build_reference_list(citations: list[dict]) -> str:
    """Build a complete APA reference list from citation entries.

    Args:
        citations: List of citation dicts with bibliography_text and citation_code.

    Returns:
        Formatted reference list as Markdown string.
    """
    if not citations:
        return ""

    lines = ["## อ้างอิง (References)", ""]
    for cit in sorted(citations, key=lambda c: c.get("citation_code", "")):
        code = cit.get("citation_code", "")
        bib = cit.get("bibliography_text", "")
        if code and bib:
            lines.append(f"[{code}] {bib}")

    return "\n".join(lines)


def build_reference_list_html(citations: list[dict]) -> str:
    """Build an HTML reference list with trust-level badges.

    Args:
        citations: List of citation dicts with bibliography_text, citation_code, trust_level.

    Returns:
        HTML string for rendering in frontend.
    """
    if not citations:
        return ""

    parts = []
    for cit in sorted(citations, key=lambda c: c.get("citation_code", "")):
        code = cit.get("citation_code", "")
        bib = cit.get("bibliography_text", "")
        trust = cit.get("trust_level", "medium")
        trust_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(trust, "⚪")

        if code and bib:
            parts.append(
                f'<div class="apa-ref-entry">'
                f'<span class="citation-code">[{code}]</span> '
                f'<span class="trust-badge">{trust_icon} {trust.title()}</span><br>'
                f'<span class="ref-text">{bib}</span>'
                f'</div>'
            )

    return '<div class="apa-references">' + "\n".join(parts) + "</div>"


def resolve_source_link(evidence: dict) -> dict:
    """Resolve the best available link for an evidence item."""
    ev_type = evidence.get("evidence_type", "")
    source_type = evidence.get("source_type", "internal")

    if ev_type in ("document", "notebooklm_pdf"):
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _italicize(text: str) -> str:
    """Wrap in italic markers (Markdown)."""
    return f"*{text}*"


def _shorten_author(authors: str) -> str:
    """Shorten multi-author or long org name for inline citation.

    สำนักงานสาธารณสุขจังหวัดอุบลราชธานี → สสจ.อุบลราชธานี
    """
    # Shorten Thai provincial health office names
    if "สำนักงานสาธารณสุขจังหวัด" in authors:
        province = authors.replace("สำนักงานสาธารณสุขจังหวัด", "").strip()
        return f"สสจ.{province}"

    # Shorten multi-author with et al.
    if "," in authors and "&" in authors:
        first = authors.split(",")[0].strip()
        return f"{first} et al."

    return authors
