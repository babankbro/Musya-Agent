"""Document upload endpoints: file upload + URL import with auto-ingestion."""
import logging
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, Form

from src.config import get_settings
from src.db.minio_client import upload_to_minio
from src.db.pool import query_db, execute_db
from src.rag.document_rag import ingest_single_document, _extract_title_from_name
from src.utils.apa_formatter import format_apa_reference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _sanitize_filename(name: str) -> str:
    """Remove path separators and dangerous characters from filename."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"|?*]', "_", name)
    return name.strip()


def _insert_document_registry(
    title: str,
    file_path: str,
    document_type: str,
    file_size: int,
    content_type: str,
    upload_method: str,
    topic: str,
    apa_authors: str,
    apa_year: str,
    apa_publisher: str,
    apa_doi: str,
    apa_url: str,
    apa_type: str,
    external_url: str,
    source_type: str,
    minio_path: str,
    ingestion_status: str,
) -> int:
    """Insert a new row into document_registry and return the document_id."""
    rows = query_db(
        """
        INSERT INTO document_registry
            (title, file_path, document_type, file_size, content_type,
             upload_method, topic, ingestion_status,
             apa_authors, apa_year, apa_publisher, apa_doi, apa_url, apa_type,
             external_url, source_type, minio_path, uploaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING document_id
        """,
        (
            title, file_path, document_type, file_size, content_type,
            upload_method, topic, ingestion_status,
            apa_authors, apa_year, apa_publisher, apa_doi, apa_url, apa_type,
            external_url, source_type, minio_path,
        ),
    )
    return rows[0]["document_id"]


def _update_ingestion_status(doc_id: int, status: str, chunk_count: int = 0, error_message: str = "", total_pages: int = 0):
    """Update ingestion status for a document."""
    execute_db(
        """
        UPDATE document_registry
        SET ingestion_status = %s, chunk_count = %s, error_message = %s, total_pages = %s
        WHERE document_id = %s
        """,
        (status, chunk_count, error_message, total_pages, doc_id),
    )


def _get_doc_row(doc_id: int) -> dict:
    """Fetch a document_registry row as dict."""
    rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (doc_id,))
    return rows[0] if rows else {}


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    title: str = Form(""),
    topic: str = Form("general"),
    apa_authors: str = Form(""),
    apa_year: str = Form(""),
    apa_publisher: str = Form(""),
    apa_doi: str = Form(""),
    apa_url: str = Form(""),
    apa_type: str = Form("report"),
    external_url: str = Form(""),
):
    """Upload a file → MinIO → register → auto-ingest → pgvector."""
    s = get_settings()

    # 1. Validate file type
    safe_name = _sanitize_filename(file.filename or "unknown")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # 2. Read file content
    content = await file.read()
    file_size = len(content)
    max_bytes = s.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(400, f"File too large: {file_size} bytes. Max: {s.MAX_UPLOAD_SIZE_MB} MB")

    # 3. Upload to MinIO with structured path: <topic>/<filename>
    safe_topic = re.sub(r'[^a-z0-9_]', '_', (topic or 'general').lower())
    minio_path = f"{safe_topic}/{safe_name}"
    try:
        upload_to_minio(minio_path, content, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(500, f"Failed to upload to MinIO: {e}")

    # 4. Register in document_registry
    doc_title = title or _extract_title_from_name(safe_name)
    doc_id = _insert_document_registry(
        title=doc_title,
        file_path=minio_path,
        document_type=ext.lstrip("."),
        file_size=file_size,
        content_type=file.content_type or "",
        upload_method="upload",
        topic=topic,
        apa_authors=apa_authors,
        apa_year=apa_year,
        apa_publisher=apa_publisher,
        apa_doi=apa_doi,
        apa_url=apa_url,
        apa_type=apa_type,
        external_url=external_url,
        source_type="external" if external_url else "internal",
        minio_path=minio_path,
        ingestion_status="processing",
    )

    # 5. Auto-ingest: extract text → chunk → embed → pgvector
    chunk_count = 0
    try:
        chunk_count = ingest_single_document(minio_path, content, doc_id, topic)
        _update_ingestion_status(doc_id, "completed", chunk_count)
    except Exception as e:
        _update_ingestion_status(doc_id, "failed", 0, str(e))
        raise HTTPException(500, f"Ingestion failed: {e}")

    # 6. Generate APA citation preview
    doc_row = _get_doc_row(doc_id)
    apa_text = format_apa_reference(doc_row)

    return {
        "status": "ok",
        "document_id": doc_id,
        "file_path": minio_path,
        "title": doc_title,
        "chunks_ingested": chunk_count,
        "ingestion_status": "completed",
        "apa_citation": apa_text,
        "source_link": {
            "type": "external" if external_url else "internal",
            "minio_url": f"/api/documents/open/{doc_id}",
            "external_url": external_url,
        },
    }


@router.post("/upload-url")
async def upload_from_url(
    url: str = Form(...),
    title: str = Form(""),
    topic: str = Form("general"),
    apa_authors: str = Form(""),
    apa_year: str = Form(""),
    apa_publisher: str = Form(""),
    apa_doi: str = Form(""),
    apa_url: str = Form(""),
    apa_type: str = Form("report"),
):
    """Download a document from an external URL, store in MinIO, and auto-ingest."""
    s = get_settings()

    if not s.ALLOW_EXTERNAL_URL_IMPORT:
        raise HTTPException(403, "External URL import is disabled")

    # Validate URL scheme
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    # Download file
    try:
        async with httpx.AsyncClient(timeout=s.EXTERNAL_URL_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Failed to download from URL: {e}")

    content = resp.content
    file_size = len(content)
    content_type = resp.headers.get("content-type", "application/octet-stream")

    # Determine filename from URL
    url_path = url.rsplit("?", 1)[0]
    safe_name = _sanitize_filename(url_path.rsplit("/", 1)[-1] or "downloaded_document")
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Downloaded file type not supported: {ext}")

    # Upload to MinIO with structured path: <topic>/<filename>
    safe_topic = re.sub(r'[^a-z0-9_]', '_', (topic or 'general').lower())
    minio_path = f"{safe_topic}/{safe_name}"
    upload_to_minio(minio_path, content, content_type)

    # Register
    doc_title = title or _extract_title_from_name(safe_name)
    doc_id = _insert_document_registry(
        title=doc_title,
        file_path=minio_path,
        document_type=ext.lstrip("."),
        file_size=file_size,
        content_type=content_type,
        upload_method="url",
        topic=topic,
        apa_authors=apa_authors,
        apa_year=apa_year,
        apa_publisher=apa_publisher,
        apa_doi=apa_doi,
        apa_url=apa_url or url,
        apa_type=apa_type,
        external_url=url,
        source_type="external",
        minio_path=minio_path,
        ingestion_status="processing",
    )

    # Auto-ingest
    chunk_count = 0
    try:
        chunk_count = ingest_single_document(minio_path, content, doc_id, topic)
        _update_ingestion_status(doc_id, "completed", chunk_count)
    except Exception as e:
        _update_ingestion_status(doc_id, "failed", 0, str(e))
        raise HTTPException(500, f"Ingestion failed: {e}")

    doc_row = _get_doc_row(doc_id)
    apa_text = format_apa_reference(doc_row)

    return {
        "status": "ok",
        "document_id": doc_id,
        "file_path": minio_path,
        "title": doc_title,
        "chunks_ingested": chunk_count,
        "ingestion_status": "completed",
        "apa_citation": apa_text,
        "source_link": {
            "type": "external",
            "minio_url": f"/api/documents/open/{doc_id}",
            "external_url": url,
        },
    }
