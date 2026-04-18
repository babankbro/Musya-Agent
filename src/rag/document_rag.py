"""Document RAG pipeline: ingest from MinIO, chunk, embed, search."""
import io
import logging
import re
from hashlib import md5

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.db.minio_client import list_documents, download_document
from src.rag.vector_store import add_documents, search_documents
from src.db.pool import query_db, execute_db

logger = logging.getLogger(__name__)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", "。", ".", " ", ""],
)


def extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    text_parts = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def extract_pages_from_pdf(data: bytes) -> list[dict]:
    """Extract text per page from PDF, returning list of {page, text}."""
    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pages.append({"page": i + 1, "text": page.get_text()})
    return pages


def _detect_heading(text: str) -> str:
    """Try to detect section heading from the first line of a chunk."""
    first_line = text.strip().split("\n")[0].strip() if text.strip() else ""
    if not first_line:
        return ""
    # Heuristic: headings are short lines that look like titles
    if len(first_line) < 120 and (first_line[0].isupper() or re.match(r'^[\d\.]+\s', first_line) or re.match(r'^[ก-๙]', first_line)):
        return first_line[:200]
    return ""


def _extract_title_from_name(object_name: str) -> str:
    """Extract a human-readable title from the file name."""
    name = object_name.rsplit("/", 1)[-1] if "/" in object_name else object_name
    name = name.rsplit(".", 1)[0] if "." in name else name
    return name.replace("_", " ").replace("-", " ").strip()


def extract_text_from_docx(data: bytes) -> str:
    """Extract text from DOCX bytes."""
    doc = DocxDocument(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(object_name: str, data: bytes) -> str:
    """Extract text based on file extension."""
    name_lower = object_name.lower()
    if name_lower.endswith(".pdf"):
        return extract_text_from_pdf(data)
    elif name_lower.endswith(".docx"):
        return extract_text_from_docx(data)
    elif name_lower.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    else:
        logger.warning(f"Unsupported file type: {object_name}")
        return ""


def _upsert_registry(object_name: str, file_size: int, status: str, chunk_count: int = 0, error_msg: str = "") -> int:
    """Upsert a row in document_registry for the given MinIO object. Returns document_id."""
    doc_title = _extract_title_from_name(object_name)
    ext = object_name.rsplit(".", 1)[-1].lower() if "." in object_name else "txt"
    doc_type = {"pdf": "pdf", "docx": "docx", "txt": "txt", "md": "md"}.get(ext, "txt")

    # Check if row already exists (by minio_path or file_path)
    rows = query_db(
        "SELECT document_id FROM document_registry WHERE minio_path = %s OR file_path = %s",
        (object_name, object_name),
    )
    if rows:
        doc_id = rows[0]["document_id"]
        execute_db(
            """UPDATE document_registry
               SET ingestion_status = %s, chunk_count = %s, error_message = %s,
                   file_size = %s, minio_path = %s, file_path = %s
               WHERE document_id = %s""",
            (status, chunk_count, error_msg, file_size, object_name, object_name, doc_id),
        )
        return doc_id
    else:
        # Insert new row
        rows2 = query_db(
            """INSERT INTO document_registry
               (title, document_type, topic, minio_path, file_path, file_size,
                ingestion_status, chunk_count, error_message, upload_method, source_type)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING document_id""",
            (doc_title, doc_type, "general", object_name, object_name, file_size,
             status, chunk_count, error_msg, "minio", "internal"),
        )
        return rows2[0]["document_id"] if rows2 else -1


def ingest_all_documents(prefix: str = "") -> int:
    """Ingest all documents from MinIO into the vector store.
    
    Upserts each file into document_registry with real status.
    Returns the number of chunks added.
    """
    docs = list_documents(prefix=prefix)
    total_chunks = 0
    ingested_count = 0

    for doc_info in docs:
        object_name = doc_info["name"]
        file_size = doc_info.get("size") or 0
        logger.info(f"Processing: {object_name}")

        # Mark as processing
        try:
            _upsert_registry(object_name, file_size, "processing")
        except Exception as e:
            logger.warning(f"Registry upsert (processing) failed for {object_name}: {e}")

        try:
            data = download_document(object_name)
            text = extract_text(object_name, data)
            if not text.strip():
                logger.warning(f"No text extracted from {object_name}")
                try:
                    _upsert_registry(object_name, file_size, "failed", 0, "No text extracted")
                except Exception:
                    pass
                continue

            chunks = _splitter.split_text(text)
            if not chunks:
                try:
                    _upsert_registry(object_name, file_size, "failed", 0, "No chunks produced")
                except Exception:
                    pass
                continue

            # Build page map for PDFs so we can assign page_ref per chunk
            page_map = None
            total_pages = 0
            if object_name.lower().endswith(".pdf"):
                try:
                    pdf_pages = extract_pages_from_pdf(data)
                    total_pages = len(pdf_pages)
                    page_map = []
                    offset = 0
                    for p in pdf_pages:
                        page_map.append((offset, offset + len(p["text"]), p["page"]))
                        offset += len(p["text"]) + 1
                except Exception:
                    page_map = None

            doc_title = _extract_title_from_name(object_name)

            ids = []
            metadatas = []
            char_offset = 0
            for i, chunk in enumerate(chunks):
                chunk_id = md5(f"{object_name}::{i}".encode()).hexdigest()
                ids.append(chunk_id)

                page_ref = ""
                if page_map:
                    for (start, end, pg) in page_map:
                        if start <= char_offset < end:
                            page_ref = str(pg)
                            break

                heading = _detect_heading(chunk)

                metadatas.append({
                    "source": object_name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "title": doc_title,
                    "page_ref": page_ref,
                    "section_label": heading,
                    "total_pages": total_pages,
                })
                char_offset += len(chunk)

            add_documents(ids=ids, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
            ingested_count += 1
            logger.info(f"  Added {len(chunks)} chunks from {object_name}")

            # Mark completed in registry
            try:
                _upsert_registry(object_name, file_size, "completed", len(chunks))
            except Exception as e:
                logger.warning(f"Registry upsert (completed) failed for {object_name}: {e}")

        except Exception as e:
            logger.error(f"Failed to process {object_name}: {e}")
            try:
                _upsert_registry(object_name, file_size, "failed", 0, str(e)[:500])
            except Exception:
                pass

    logger.info(f"Ingestion complete. Total chunks: {total_chunks}, files: {ingested_count}")
    return total_chunks


def ingest_single_document(
    object_name: str,
    data: bytes,
    doc_id: int | None = None,
    topic: str = "general",
) -> int:
    """Ingest a single document from bytes into pgvector.

    Returns the number of chunks added.
    """
    text = extract_text(object_name, data)
    if not text.strip():
        logger.warning(f"No text extracted from {object_name}")
        return 0

    chunks = _splitter.split_text(text)
    if not chunks:
        return 0

    # Build page map for PDFs
    page_map = None
    total_pages = 0
    if object_name.lower().endswith(".pdf"):
        try:
            pdf_pages = extract_pages_from_pdf(data)
            total_pages = len(pdf_pages)
            page_map = []
            offset = 0
            for p in pdf_pages:
                page_map.append((offset, offset + len(p["text"]), p["page"]))
                offset += len(p["text"]) + 1
        except Exception:
            page_map = None

    doc_title = _extract_title_from_name(object_name)

    ids = []
    metadatas = []
    char_offset = 0
    for i, chunk in enumerate(chunks):
        chunk_id = md5(f"{object_name}::{i}".encode()).hexdigest()
        ids.append(chunk_id)

        page_ref = ""
        if page_map:
            for (start, end, pg) in page_map:
                if start <= char_offset < end:
                    page_ref = str(pg)
                    break

        heading = _detect_heading(chunk)

        metadatas.append({
            "source": object_name,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "title": doc_title,
            "page_ref": page_ref,
            "section_label": heading,
            "total_pages": total_pages,
            "topic": topic,
        })
        char_offset += len(chunk)

    add_documents(ids=ids, documents=chunks, metadatas=metadatas)
    logger.info(f"Ingested {len(chunks)} chunks from {object_name}")
    return len(chunks)


def delete_document_chunks(source_path: str) -> int:
    """Delete all embedding chunks for a given source path. Returns count removed."""
    from src.rag.vector_store import _get_conn
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_embeddings WHERE source = %s", (source_path,))
            count = cur.rowcount
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise


_TOPIC_ALIASES: dict[str, str] = {
    "rti": "accident",
    "mental": "mental_health",
    "ncd": "nutrition",
    "all": "",
    "general": "",
}


def search(query: str, topic: str | None = None, n_results: int = 5) -> list[dict]:
    """Search documents with optional topic filter.

    Normalises agent topic codes (rti, mental, ncd) to ingest-time values
    (accident, mental_health, nutrition). If the filtered search returns no
    results it retries with no topic filter so documents tagged 'general' or
    any other topic are still found.
    """
    # Normalise topic alias (rti → accident, mental → mental_health, etc.)
    if topic:
        topic = _TOPIC_ALIASES.get(topic.lower(), topic)

    where = {"topic": topic} if topic else None
    results = search_documents(query=query, n_results=n_results, where=where)

    # Fallback: retry without topic filter if filtered search returns nothing
    if not results and where is not None:
        logger.debug("search(): no results for topic=%s, retrying without filter", topic)
        results = search_documents(query=query, n_results=n_results, where=None)

    return results
