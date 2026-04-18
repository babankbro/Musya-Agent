"""Evidence & Document access API routes for Citation & Evidence Agent."""
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
import io

from src.db.pool import query_db
from src.db.minio_client import get_minio_client, download_document
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["evidence"])


# ---------------------------------------------------------------------------
# Document access endpoints
# ---------------------------------------------------------------------------

@router.get("/documents/open/{document_id}")
async def open_document(document_id: int, page: int | None = Query(None)):
    """Open a source document by its document_registry ID.

    Returns the file as an inline stream (PDF/DOCX viewer) from MinIO.
    Optionally accepts ?page=N for PDF page reference (informational).
    """
    try:
        rows = query_db(
            "SELECT document_id, title, file_path, minio_path, document_type FROM document_registry WHERE document_id = %s",
            (document_id,),
        )
    except Exception as e:
        logger.error("open_document DB error id=%s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not rows:
        raise HTTPException(status_code=404, detail="เอกสารไม่พบในระบบ")

    doc = rows[0]
    file_path = doc.get("file_path") or doc.get("minio_path") or ""
    logger.info("open_document id=%s file_path=%r", document_id, file_path)

    if not file_path:
        raise HTTPException(status_code=404, detail="ไม่มี file_path สำหรับเอกสารนี้")

    try:
        data = download_document(file_path)
    except Exception as e:
        logger.error("open_document MinIO error id=%s path=%r: %s", document_id, file_path, e)
        raise HTTPException(status_code=502, detail=f"ไม่สามารถดาวน์โหลดไฟล์จาก MinIO: {e}")

    if not isinstance(data, (bytes, bytearray)):
        logger.error("open_document: download_document returned %r for path=%r", type(data), file_path)
        raise HTTPException(status_code=502, detail="MinIO returned non-bytes data")

    ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
    _CONTENT_TYPES = {
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "md": "text/plain; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

    filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    logger.info("open_document serving %d bytes as %s", len(data), content_type)

    # RFC 5987: encode non-ASCII filename so HTTP headers don't crash
    from urllib.parse import quote as _quote
    try:
        filename.encode("ascii")
        cd = f'inline; filename="{filename}"'
    except UnicodeEncodeError:
        cd = f"inline; filename*=UTF-8''{_quote(filename)}"

    return StreamingResponse(
        io.BytesIO(data),
        media_type=content_type,
        headers={"Content-Disposition": cd},
    )


@router.get("/documents/open/{document_id}/info")
async def document_info(document_id: int):
    """Get metadata about a document (title, file_path, total_pages, etc.)."""
    try:
        rows = query_db(
            "SELECT document_id, title, file_path, minio_path, document_type, total_pages, original_url "
            "FROM document_registry WHERE document_id = %s",
            (document_id,),
        )
    except Exception:
        rows = []

    if not rows:
        raise HTTPException(status_code=404, detail="เอกสารไม่พบในระบบ")

    doc = dict(rows[0])
    doc["open_url"] = f"/api/documents/open/{document_id}"
    return doc


# ---------------------------------------------------------------------------
# Evidence access endpoints
# ---------------------------------------------------------------------------

@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str):
    """Get a single evidence item by ID."""
    try:
        rows = query_db(
            "SELECT * FROM evidence_registry WHERE evidence_id = %s",
            (evidence_id,),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not rows:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} ไม่พบ")

    return rows[0]


@router.get("/evidence/{evidence_id}/query")
async def get_evidence_query(evidence_id: str):
    """For database-type evidence, show the SQL query and re-run to get results."""
    try:
        rows = query_db(
            "SELECT evidence_id, evidence_type, source_ref, query_signature, query_params, text_snippet "
            "FROM evidence_registry WHERE evidence_id = %s",
            (evidence_id,),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not rows:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} ไม่พบ")

    ev = rows[0]
    if ev.get("evidence_type") != "database":
        return {
            "evidence_id": evidence_id,
            "evidence_type": ev.get("evidence_type"),
            "message": "Evidence นี้ไม่ใช่ประเภท database — ไม่มี SQL query",
            "text_snippet": ev.get("text_snippet", ""),
        }

    return {
        "evidence_id": evidence_id,
        "evidence_type": "database",
        "source_ref": ev.get("source_ref", ""),
        "query_signature": ev.get("query_signature", ""),
        "query_params": ev.get("query_params", {}),
        "text_snippet": ev.get("text_snippet", ""),
    }


@router.get("/evidence/session/{session_id}")
async def get_session_evidence(session_id: str):
    """List all evidence items for a given chat session."""
    try:
        rows = query_db(
            "SELECT * FROM evidence_registry WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {"session_id": session_id, "evidence_count": len(rows), "evidence": rows}


@router.get("/evidence/session/{session_id}/coverage")
async def get_session_coverage(session_id: str):
    """Get coverage report for a session — how many claims have evidence."""
    try:
        claims = query_db(
            "SELECT claim_id, claim_text, claim_type, support_level, evidence_strength, citation_code "
            "FROM claim_evidence_link WHERE session_id = %s",
            (session_id,),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    total = len(claims)
    supported = sum(1 for c in claims if c.get("support_level") == "supported")
    partial = sum(1 for c in claims if c.get("support_level") == "partially_supported")
    insufficient = sum(1 for c in claims if c.get("support_level") == "insufficient")

    return {
        "session_id": session_id,
        "total_claims": total,
        "supported": supported,
        "partially_supported": partial,
        "insufficient": insufficient,
        "coverage_score": supported / total if total > 0 else 0.0,
        "claims": claims,
    }
