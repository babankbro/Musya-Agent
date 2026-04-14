"""Citation API endpoints: APA-formatted citations for chat sessions."""
import logging

from fastapi import APIRouter, HTTPException

from src.db.pool import query_db
from src.utils.apa_formatter import format_apa_reference, format_apa_inline, format_database_reference, resolve_source_link

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/citations", tags=["citations"])


@router.get("/session/{session_id}")
async def get_session_citations(session_id: str):
    """Get all citations for a chat session in APA format."""
    # Fetch evidence items for this session
    try:
        evidence_rows = query_db(
            "SELECT * FROM evidence_registry WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

    if not evidence_rows:
        return {
            "session_id": session_id,
            "citation_style": "APA7",
            "citations": [],
            "reference_list_html": "",
        }

    citations = []
    references_html_parts = []

    for ev in evidence_rows:
        ev_type = ev.get("evidence_type", "")
        citation_code = ev.get("citation_code", "")
        trust_level = ev.get("trust_level", "medium")
        page_ref = ev.get("page_ref", "")

        if ev_type == "document":
            # Look up document_registry for APA metadata
            source_ref = ev.get("source_ref", "")
            doc_rows = query_db(
                "SELECT * FROM document_registry WHERE file_path = %s OR title = %s LIMIT 1",
                (source_ref, source_ref),
            )

            if doc_rows:
                doc = doc_rows[0]
                inline_text = format_apa_inline(doc, page_ref=page_ref)
                reference_text = format_apa_reference(doc)
                if page_ref:
                    # Insert page ref into reference
                    reference_text = reference_text.rstrip(".")
                    reference_text += f" (หน้า {page_ref})."
            else:
                # Fallback: construct from evidence fields
                inline_text = f"({source_ref}, {page_ref})" if page_ref else f"({source_ref})"
                reference_text = f"{source_ref}."

            source_link = resolve_source_link({
                "evidence_type": "document",
                "document_id": doc_rows[0].get("document_id") if doc_rows else None,
                "page_ref": page_ref,
                "source_type": doc_rows[0].get("source_type", "internal") if doc_rows else "internal",
                "external_url": doc_rows[0].get("external_url", "") if doc_rows else "",
            })

        elif ev_type == "database":
            source_ref = ev.get("source_ref", "")
            year = ev.get("time_range_ref", "2025").split("-")[0] if ev.get("time_range_ref") else "2025"
            inline_text = f"(Musya Agent Database, {year})"
            reference_text = format_database_reference(source_ref, year)
            source_link = resolve_source_link({
                "evidence_type": "database",
                "evidence_id": ev.get("evidence_id", ""),
            })

        else:
            inline_text = f"({ev.get('source_ref', 'Unknown')})"
            reference_text = f"{ev.get('source_ref', 'Unknown')}."
            source_link = resolve_source_link(ev)

        citation_entry = {
            "citation_code": citation_code,
            "evidence_id": ev.get("evidence_id", ""),
            "inline_text": inline_text,
            "reference_text": reference_text,
            "evidence_type": ev_type,
            "trust_level": trust_level,
            "source_link": {
                "type": source_link.get("type", "unknown"),
                "url": source_link.get("primary_url", ""),
                "label": source_link.get("label", ""),
            },
        }
        citations.append(citation_entry)

        # Build HTML reference entry
        trust_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(trust_level, "⚪")
        references_html_parts.append(
            f'<div class="apa-ref-entry">'
            f'<span class="citation-code">[{citation_code}]</span> '
            f'<span class="trust-badge">{trust_color} {trust_level.title()}</span><br>'
            f'<span class="ref-text">{reference_text}</span>'
            f'</div>'
        )

    reference_list_html = '<div class="apa-references">' + "\n".join(references_html_parts) + '</div>'

    return {
        "session_id": session_id,
        "citation_style": "APA7",
        "citations": citations,
        "reference_list_html": reference_list_html,
    }


@router.get("/document/{document_id}")
async def get_document_citation(document_id: int):
    """Get APA citation for a specific document."""
    rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    if not rows:
        raise HTTPException(404, "เอกสารไม่พบในระบบ")

    doc = rows[0]
    return {
        "document_id": document_id,
        "apa_reference": format_apa_reference(doc),
        "apa_inline": format_apa_inline(doc),
        "apa_type": doc.get("apa_type", "report"),
    }
