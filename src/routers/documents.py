"""Document management endpoints: list, detail, update, delete, reingest."""
import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from src.db.pool import query_db, execute_db
from src.db.minio_client import download_document, delete_from_minio, browse_minio
from src.rag.document_rag import ingest_single_document, delete_document_chunks, _extract_title_from_name
from src.utils.apa_formatter import format_apa_reference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    apa_authors: str | None = None
    apa_year: str | None = None
    apa_publisher: str | None = None
    apa_doi: str | None = None
    apa_url: str | None = None
    apa_type: str | None = None
    apa_edition: str | None = None
    apa_volume: str | None = None
    apa_pages: str | None = None
    external_url: str | None = None


def _format_doc_response(row: dict) -> dict:
    """Format a document_registry row for API response."""
    apa_text = format_apa_reference(row)
    return {
        "document_id": row.get("document_id"),
        "title": row.get("title", ""),
        "document_type": row.get("document_type", ""),
        "file_path": row.get("file_path", ""),
        "file_size": row.get("file_size", 0),
        "total_pages": row.get("total_pages", 0),
        "topic": row.get("topic", ""),
        "uploaded_at": str(row.get("uploaded_at", "")),
        "uploaded_by": row.get("uploaded_by", ""),
        "upload_method": row.get("upload_method", ""),
        "ingestion_status": row.get("ingestion_status", ""),
        "chunk_count": row.get("chunk_count", 0),
        "error_message": row.get("error_message", ""),
        "source_type": row.get("source_type", "internal"),
        "minio_url": f"/api/documents/open/{row.get('document_id')}",
        "external_url": row.get("external_url", ""),
        "apa_citation": apa_text,
        "apa": {
            "authors": row.get("apa_authors", ""),
            "year": row.get("apa_year", ""),
            "title": row.get("title", ""),
            "publisher": row.get("apa_publisher", ""),
            "doi": row.get("apa_doi", ""),
            "url": row.get("apa_url", ""),
            "accessed": str(row.get("apa_accessed", "")) if row.get("apa_accessed") else None,
            "edition": row.get("apa_edition", ""),
            "volume": row.get("apa_volume", ""),
            "pages": row.get("apa_pages", ""),
            "type": row.get("apa_type", "report"),
            "formatted": apa_text,
        },
    }


@router.get("")
async def list_documents(
    status: str = Query("", description="Filter by ingestion_status"),
    topic: str = Query("", description="Filter by topic"),
    source_type: str = Query("", description="Filter: internal | external"),
    search: str = Query("", description="Title/filename search"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("uploaded_at", description="Sort field"),
    order: str = Query("desc", description="asc | desc"),
):
    """List all registered documents with filters and pagination."""
    conditions = []
    params: list = []

    if status:
        conditions.append("ingestion_status = %s")
        params.append(status)
    if topic:
        conditions.append("topic = %s")
        params.append(topic)
    if source_type:
        conditions.append("source_type = %s")
        params.append(source_type)
    if search:
        conditions.append("(title ILIKE %s OR file_path ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Whitelist sort columns
    allowed_sorts = {"uploaded_at", "title", "file_size", "chunk_count", "document_id"}
    sort_col = sort if sort in allowed_sorts else "uploaded_at"
    sort_dir = "ASC" if order.lower() == "asc" else "DESC"

    # Count
    count_rows = query_db(f"SELECT COUNT(*) as cnt FROM document_registry {where_clause}", params)
    total = count_rows[0]["cnt"] if count_rows else 0

    # Fetch page
    offset = (page - 1) * per_page
    rows = query_db(
        f"SELECT * FROM document_registry {where_clause} ORDER BY {sort_col} {sort_dir} LIMIT %s OFFSET %s",
        params + [per_page, offset],
    )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "documents": [_format_doc_response(r) for r in rows],
    }


@router.get("/{document_id}")
async def get_document(document_id: int):
    """Get single document detail with full APA metadata."""
    rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    if not rows:
        raise HTTPException(404, "เอกสารไม่พบในระบบ")

    doc = _format_doc_response(rows[0])

    # Attach chunks preview
    try:
        chunk_rows = query_db(
            """
            SELECT chunk_index, section_label, page_ref,
                   LEFT(document, 200) as text_preview
            FROM document_embeddings
            WHERE source = %s
            ORDER BY chunk_index
            LIMIT 10
            """,
            (rows[0].get("file_path", ""),),
        )
        doc["chunks_preview"] = [
            {
                "chunk_index": c.get("chunk_index"),
                "section_label": c.get("section_label", ""),
                "page_ref": c.get("page_ref", ""),
                "text_preview": c.get("text_preview", ""),
            }
            for c in chunk_rows
        ]
    except Exception:
        doc["chunks_preview"] = []

    return doc


@router.patch("/{document_id}")
async def update_document(document_id: int, body: DocumentUpdate):
    """Update document metadata (title, APA fields, topic)."""
    rows = query_db("SELECT document_id FROM document_registry WHERE document_id = %s", (document_id,))
    if not rows:
        raise HTTPException(404, "เอกสารไม่พบในระบบ")

    updates = []
    params: list = []
    for field, value in body.model_dump(exclude_none=True).items():
        col = f"apa_{field}" if field.startswith(("authors", "year", "publisher", "doi", "url", "type", "edition", "volume", "pages")) and not field.startswith("apa_") else field
        # Map model fields to DB columns
        col_map = {
            "apa_authors": "apa_authors", "apa_year": "apa_year",
            "apa_publisher": "apa_publisher", "apa_doi": "apa_doi",
            "apa_url": "apa_url", "apa_type": "apa_type",
            "apa_edition": "apa_edition", "apa_volume": "apa_volume",
            "apa_pages": "apa_pages",
            "title": "title", "topic": "topic", "external_url": "external_url",
        }
        db_col = col_map.get(field)
        if db_col:
            updates.append(f"{db_col} = %s")
            params.append(value)

    if not updates:
        raise HTTPException(400, "No valid fields to update")

    params.append(document_id)
    execute_db(
        f"UPDATE document_registry SET {', '.join(updates)} WHERE document_id = %s",
        params,
    )

    updated_rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    return _format_doc_response(updated_rows[0])


@router.delete("/{document_id}")
async def delete_document(document_id: int):
    """Delete document from registry, MinIO, and pgvector."""
    rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    if not rows:
        raise HTTPException(404, "เอกสารไม่พบในระบบ")

    doc = rows[0]
    file_path = doc.get("file_path", "") or doc.get("minio_path", "")

    # Delete embeddings
    chunks_removed = 0
    if file_path:
        try:
            chunks_removed = delete_document_chunks(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete chunks for doc {document_id}: {e}")

    # Delete from MinIO
    minio_removed = False
    if file_path:
        minio_removed = delete_from_minio(file_path)

    # Delete from registry
    execute_db("DELETE FROM document_registry WHERE document_id = %s", (document_id,))

    return {
        "status": "deleted",
        "document_id": document_id,
        "chunks_removed": chunks_removed,
        "minio_removed": minio_removed,
    }


@router.post("/{document_id}/reingest")
async def reingest_document(document_id: int):
    """Re-ingest a document (e.g., after embedding model change)."""
    rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    if not rows:
        raise HTTPException(404, "เอกสารไม่พบในระบบ")

    doc = rows[0]
    file_path = doc.get("file_path", "") or doc.get("minio_path", "")
    if not file_path:
        raise HTTPException(400, "เอกสารไม่มี file_path — ไม่สามารถ reingest ได้")

    # Delete old chunks
    try:
        delete_document_chunks(file_path)
    except Exception as e:
        logger.warning(f"Failed to delete old chunks: {e}")

    # Download from MinIO
    try:
        data = download_document(file_path)
    except Exception as e:
        execute_db(
            "UPDATE document_registry SET ingestion_status = 'failed', error_message = %s WHERE document_id = %s",
            (str(e), document_id),
        )
        raise HTTPException(502, f"ไม่สามารถดาวน์โหลดไฟล์จาก MinIO: {e}")

    # Re-ingest
    topic = doc.get("topic", "general") or "general"
    try:
        chunk_count = ingest_single_document(file_path, data, document_id, topic)
        execute_db(
            "UPDATE document_registry SET ingestion_status = 'completed', chunk_count = %s, error_message = '' WHERE document_id = %s",
            (chunk_count, document_id),
        )
    except Exception as e:
        execute_db(
            "UPDATE document_registry SET ingestion_status = 'failed', error_message = %s WHERE document_id = %s",
            (str(e), document_id),
        )
        raise HTTPException(500, f"Re-ingestion failed: {e}")

    updated_rows = query_db("SELECT * FROM document_registry WHERE document_id = %s", (document_id,))
    doc_row = updated_rows[0]
    apa_text = format_apa_reference(doc_row)

    return {
        "status": "ok",
        "document_id": document_id,
        "file_path": file_path,
        "title": doc_row.get("title", ""),
        "chunks_ingested": chunk_count,
        "ingestion_status": "completed",
        "apa_citation": apa_text,
    }


@router.get("/minio/tree")
async def minio_tree() -> dict:
    """Return the full recursive tree of MinIO bucket with registry enrichment.
    
    Returns a nested structure: { name, type, path, children[] } for folders,
    plus file metadata (status, chunks, apa) for files.
    """
    from src.db.minio_client import list_documents as _list_all
    s = __import__('src.config', fromlist=['get_settings']).get_settings()

    try:
        all_files = _list_all(prefix="")
    except Exception as e:
        raise HTTPException(500, f"MinIO list error: {e}")

    if not all_files:
        return {"tree": [], "total_files": 0}

    # Enrich all files with registry + embeddings data in one query
    file_paths = [f["name"] for f in all_files]
    registry_map: dict[str, dict] = {}
    embed_chunk_map: dict[str, int] = {}

    if file_paths:
        try:
            ph = ",".join(["%s"] * len(file_paths))
            rows = query_db(
                f"SELECT * FROM document_registry WHERE minio_path IN ({ph}) OR file_path IN ({ph})",
                file_paths + file_paths,
            )
            for row in rows:
                for key in (row.get("minio_path", ""), row.get("file_path", "")):
                    if key:
                        registry_map[key] = row
        except Exception as e:
            logger.warning(f"Tree registry lookup failed: {e}")

        try:
            ph = ",".join(["%s"] * len(file_paths))
            rows2 = query_db(
                f"SELECT source, COUNT(*) AS cnt FROM document_embeddings WHERE source IN ({ph}) GROUP BY source",
                file_paths,
            )
            for row in rows2:
                embed_chunk_map[row["source"]] = int(row["cnt"])
        except Exception as e:
            logger.warning(f"Tree embeddings lookup failed: {e}")

    # Build nested tree structure
    root: dict = {}  # path -> node
    tree_roots: list = []

    def get_or_create_folder(path: str) -> dict:
        if path in root:
            return root[path]
        name = path.rstrip("/").rsplit("/", 1)[-1]
        node = {"name": name, "type": "folder", "path": path, "children": []}
        root[path] = node
        # Attach to parent
        parent_path = path.rstrip("/").rsplit("/", 1)[0] + "/" if "/" in path.rstrip("/") else ""
        if parent_path and parent_path != path:
            parent = get_or_create_folder(parent_path)
            if node not in parent["children"]:
                parent["children"].append(node)
        else:
            if node not in tree_roots:
                tree_roots.append(node)
        return node

    for f in all_files:
        obj_name = f["name"]
        lm = f.get("last_modified")
        lm_iso = lm.isoformat() if hasattr(lm, "isoformat") else str(lm) if lm else None
        ext = obj_name.rsplit(".", 1)[-1].lower() if "." in obj_name else ""
        rel_name = obj_name.rsplit("/", 1)[-1] if "/" in obj_name else obj_name

        reg = registry_map.get(obj_name)
        if reg:
            status = reg.get("ingestion_status", "not_registered")
            chunks = reg.get("chunk_count", 0) or embed_chunk_map.get(obj_name, 0)
        elif obj_name in embed_chunk_map:
            status = "completed"
            chunks = embed_chunk_map[obj_name]
        else:
            status = "not_registered"
            chunks = 0

        apa = format_apa_reference(reg) if reg else ""

        file_node = {
            "name": rel_name,
            "type": "file",
            "path": obj_name,
            "ext": ext,
            "size": f.get("size") or 0,
            "last_modified": lm_iso,
            "document_id": reg.get("document_id") if reg else None,
            "ingestion_status": status,
            "chunk_count": chunks,
            "apa_citation": apa,
            "title": reg.get("title", rel_name) if reg else rel_name,
        }

        # Attach to parent folder
        if "/" in obj_name:
            folder_path = obj_name.rsplit("/", 1)[0] + "/"
            parent = get_or_create_folder(folder_path)
            parent["children"].append(file_node)
        else:
            tree_roots.append(file_node)

    return {"tree": tree_roots, "total_files": len(all_files)}


@router.get("/minio/read")
async def minio_read_file(path: str = Query(..., description="Full MinIO object path, e.g. 'accident/file.txt'")) -> dict:
    """Read text content of a file from MinIO for inline preview."""
    try:
        data = download_document(path)
    except Exception as e:
        raise HTTPException(404, f"Cannot read file from MinIO: {e}")

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    try:
        if ext == "pdf":
            from src.rag.document_rag import extract_text_from_pdf
            text = extract_text_from_pdf(data)
        elif ext == "docx":
            from src.rag.document_rag import extract_text_from_docx
            text = extract_text_from_docx(data)
        else:
            text = data.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Cannot extract text: {e}")

    # Return first 8000 chars as preview
    preview = text[:8000]
    truncated = len(text) > 8000
    return {
        "path": path,
        "ext": ext,
        "size": len(data),
        "total_chars": len(text),
        "truncated": truncated,
        "preview": preview,
    }


class ApaDraftRequest(BaseModel):
    path: str  # MinIO object path


class ApaApproveRequest(BaseModel):
    path: str
    title: str
    topic: str = "general"
    apa_type: str = "report"
    apa_authors: str = ""
    apa_year: str = ""
    apa_publisher: str = ""
    apa_doi: str = ""
    apa_url: str = ""
    apa_edition: str = ""
    apa_volume: str = ""
    apa_pages: str = ""


@router.post("/minio/apa-draft")
async def minio_apa_draft(body: ApaDraftRequest) -> dict:
    """Use Gemini to auto-generate APA metadata from a MinIO file's content.

    Returns a draft dict with title, apa_authors, apa_year, apa_publisher, apa_type, etc.
    Does NOT write to the database — the draft must be approved via /minio/approve.
    """
    try:
        data = download_document(body.path)
    except Exception as e:
        raise HTTPException(404, f"Cannot read file: {e}")

    ext = body.path.rsplit(".", 1)[-1].lower() if "." in body.path else ""
    try:
        if ext == "pdf":
            from src.rag.document_rag import extract_text_from_pdf
            text = extract_text_from_pdf(data)
        elif ext == "docx":
            from src.rag.document_rag import extract_text_from_docx
            text = extract_text_from_docx(data)
        else:
            text = data.decode("utf-8", errors="replace")
    except Exception:
        text = ""

    # Use first 3000 chars for analysis
    snippet = text[:3000] if text else "(no text)"
    filename = body.path.rsplit("/", 1)[-1]
    folder = body.path.rsplit("/", 1)[0] if "/" in body.path else ""

    # Map folder name → likely topic
    folder_topic_map = {
        "accident": "accident", "mental_health": "mental_health",
        "nutrition": "nutrition", "general": "general",
    }
    guessed_topic = folder_topic_map.get(folder.split("/")[0], "general")

    try:
        from src.config import get_settings
        from google import genai as _genai
        settings = get_settings()
        client = _genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""You are an academic librarian. Analyze this document and return a JSON object with APA metadata.

File path: {body.path}
First 3000 chars of content:
\"\"\"
{snippet}
\"\"\"

Return ONLY a valid JSON object with these keys (use empty string if unknown):
{{
  "title": "...",
  "apa_authors": "...",
  "apa_year": "...",
  "apa_publisher": "...",
  "apa_type": "report|book|article|website|dataset|law",
  "apa_doi": "...",
  "apa_url": "...",
  "apa_edition": "",
  "apa_volume": "",
  "apa_pages": "",
  "topic": "accident|mental_health|nutrition|general",
  "confidence": "high|medium|low",
  "reason": "brief explanation"
}}"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json as _json
        draft = _json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"Gemini APA draft failed for {body.path}: {e}")
        # Fallback: use filename-based title
        title_guess = _extract_title_from_name(body.path)
        draft = {
            "title": title_guess,
            "apa_authors": "",
            "apa_year": "",
            "apa_publisher": "",
            "apa_type": "report",
            "apa_doi": "",
            "apa_url": "",
            "apa_edition": "",
            "apa_volume": "",
            "apa_pages": "",
            "topic": guessed_topic,
            "confidence": "low",
            "reason": f"Auto-draft fallback (AI error: {str(e)[:100]})",
        }

    draft["path"] = body.path
    draft["filename"] = filename
    draft["status"] = "draft"
    return draft


@router.post("/minio/approve")
async def minio_approve(body: ApaApproveRequest) -> dict:
    """Approve an APA draft for a MinIO file.

    Creates a document_registry row with apa_approval_status='approved'
    and triggers ingestion into pgvector.
    """
    # Check if already registered
    existing = query_db(
        "SELECT document_id, ingestion_status FROM document_registry WHERE minio_path = %s OR file_path = %s",
        (body.path, body.path),
    )
    if existing:
        doc_id = existing[0]["document_id"]
        # Update metadata
        execute_db(
            """UPDATE document_registry
               SET title=%s, topic=%s, apa_type=%s, apa_authors=%s, apa_year=%s,
                   apa_publisher=%s, apa_doi=%s, apa_url=%s, apa_edition=%s,
                   apa_volume=%s, apa_pages=%s, apa_approval_status='approved',
                   ingestion_status='pending', error_message=''
               WHERE document_id=%s""",
            (body.title, body.topic, body.apa_type, body.apa_authors, body.apa_year,
             body.apa_publisher, body.apa_doi, body.apa_url, body.apa_edition,
             body.apa_volume, body.apa_pages, doc_id),
        )
    else:
        ext = body.path.rsplit(".", 1)[-1].lower() if "." in body.path else "txt"
        doc_type = {"pdf": "pdf", "docx": "docx", "txt": "txt", "md": "md"}.get(ext, "txt")
        rows = query_db(
            """INSERT INTO document_registry
               (title, document_type, topic, minio_path, file_path,
                apa_type, apa_authors, apa_year, apa_publisher, apa_doi,
                apa_url, apa_edition, apa_volume, apa_pages,
                ingestion_status, apa_approval_status, upload_method, source_type)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending','approved','minio','internal')
               RETURNING document_id""",
            (body.title, doc_type, body.topic, body.path, body.path,
             body.apa_type, body.apa_authors, body.apa_year, body.apa_publisher,
             body.apa_doi, body.apa_url, body.apa_edition, body.apa_volume, body.apa_pages),
        )
        doc_id = rows[0]["document_id"] if rows else None

    if not doc_id:
        raise HTTPException(500, "Failed to create registry entry")

    # Trigger ingest
    chunk_count = 0
    try:
        file_data = download_document(body.path)
        from src.rag.document_rag import ingest_single_document
        chunk_count = ingest_single_document(body.path, file_data, doc_id=doc_id, topic=body.topic)
        execute_db(
            "UPDATE document_registry SET ingestion_status='completed', chunk_count=%s WHERE document_id=%s",
            (chunk_count, doc_id),
        )
    except Exception as e:
        execute_db(
            "UPDATE document_registry SET ingestion_status='failed', error_message=%s WHERE document_id=%s",
            (str(e)[:500], doc_id),
        )
        raise HTTPException(500, f"Approved but ingest failed: {e}")

    return {
        "status": "approved",
        "document_id": doc_id,
        "path": body.path,
        "title": body.title,
        "chunks_ingested": chunk_count,
        "ingestion_status": "completed",
    }


@router.post("/analyze-upload")
async def analyze_upload(file: UploadFile = File(...)) -> dict:
    """Analyze an uploaded file with Gemini AI and return APA metadata draft.

    Reads the first 3000 chars of text from the file, sends to Gemini,
    returns JSON with all APA fields pre-filled. Does NOT persist anything.
    """
    from src.rag.document_rag import extract_text, _extract_title_from_name
    import json as _json

    filename = file.filename or "unknown"
    data = await file.read()

    # Extract text for analysis
    try:
        text = extract_text(filename, data)
    except Exception:
        text = ""

    snippet = text[:3000] if text else "(no text extracted)"
    folder = filename.rsplit("/", 1)[0] if "/" in filename else ""
    folder_topic_map = {
        "accident": "accident", "mental_health": "mental_health",
        "nutrition": "nutrition", "general": "general",
    }
    guessed_topic = folder_topic_map.get(folder.split("/")[0], "general")
    title_guess = _extract_title_from_name(filename)

    try:
        from src.config import get_settings
        from google import genai as _genai
        settings = get_settings()
        client = _genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = ("You are an academic librarian. Analyze this document and return a JSON object with APA metadata.\n\n"
                  f"Filename: {filename}\n"
                  f"First 3000 chars of content:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
                  "Return ONLY a valid JSON object with these keys (use empty string if unknown):\n"
                  "{\n"
                  '  "title": "...",\n'
                  '  "apa_authors": "...",\n'
                  '  "apa_year": "...",\n'
                  '  "apa_publisher": "...",\n'
                  '  "apa_type": "report|book|article|website|dataset|law",\n'
                  '  "apa_doi": "",\n'
                  '  "apa_edition": "",\n'
                  '  "apa_volume": "",\n'
                  '  "apa_pages": "",\n'
                  '  "topic": "accident|mental_health|nutrition|general",\n'
                  '  "confidence": "high|medium|low",\n'
                  '  "reason": "brief explanation"\n'
                  "}")

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        draft = _json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"Gemini APA analysis failed for {filename}: {e}")
        draft = {
            "title": title_guess,
            "apa_authors": "",
            "apa_year": "",
            "apa_publisher": "",
            "apa_type": "report",
            "apa_doi": "",
            "apa_edition": "",
            "apa_volume": "",
            "apa_pages": "",
            "topic": guessed_topic,
            "confidence": "low",
            "reason": f"Fallback (AI error: {str(e)[:100]})",
        }

    draft["filename"] = filename
    draft["status"] = "draft"
    return draft


@router.get("/minio/browse")
async def minio_browse(prefix: str = Query("", description="Folder prefix to list, e.g. 'accident/' or ''")) -> dict:
    """Browse MinIO bucket like the MinIO console — folders + files at given prefix.
    
    Each file is enriched with registry info: document_id, ingestion_status, chunk_count, apa_citation.
    """
    try:
        result = browse_minio(prefix)
    except Exception as e:
        raise HTTPException(500, f"MinIO browse error: {e}")

    # Enrich files with registry data
    file_paths = [f["full_path"] for f in result["files"]]
    registry_map: dict[str, dict] = {}
    embed_chunk_map: dict[str, int] = {}   # source → chunk count from document_embeddings

    if file_paths:
        # 1. Try document_registry (minio_path or file_path)
        try:
            placeholders = ",".join(["%s"] * len(file_paths))
            rows = query_db(
                f"""SELECT * FROM document_registry
                    WHERE minio_path IN ({placeholders})
                       OR file_path  IN ({placeholders})""",
                file_paths + file_paths,
            )
            for row in rows:
                # Index by both keys so lookup always hits
                for key in (row.get("minio_path", ""), row.get("file_path", "")):
                    if key:
                        registry_map[key] = row
        except Exception as e:
            logger.warning(f"Registry lookup failed during browse: {e}")

        # 2. Fallback: count chunks from document_embeddings by source
        try:
            placeholders = ",".join(["%s"] * len(file_paths))
            rows2 = query_db(
                f"SELECT source, COUNT(*) AS cnt FROM document_embeddings WHERE source IN ({placeholders}) GROUP BY source",
                file_paths,
            )
            for row in rows2:
                embed_chunk_map[row["source"]] = int(row["cnt"])
        except Exception as e:
            logger.warning(f"Embeddings chunk lookup failed during browse: {e}")

    enriched_files = []
    for f in result["files"]:
        fp = f["full_path"]
        reg = registry_map.get(fp)
        apa = format_apa_reference(reg) if reg else ""

        # Determine embedding status: registry takes priority, fallback to embeddings table
        if reg:
            status = reg.get("ingestion_status", "not_registered")
            chunks = reg.get("chunk_count", 0) or embed_chunk_map.get(fp, 0)
        elif fp in embed_chunk_map:
            status = "completed"
            chunks = embed_chunk_map[fp]
        else:
            status = "not_registered"
            chunks = 0

        enriched_files.append({
            **f,
            "document_id": reg.get("document_id") if reg else None,
            "ingestion_status": status,
            "chunk_count": chunks,
            "apa_citation": apa,
            "title": reg.get("title", f["name"]) if reg else f["name"],
            "has_apa": bool(apa),
        })

    return {
        "bucket": result["bucket"],
        "prefix": result["prefix"],
        "folders": result["folders"],
        "files": enriched_files,
    }
