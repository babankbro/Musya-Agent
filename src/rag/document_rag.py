"""Document RAG pipeline: ingest from MinIO, chunk, embed, search."""
import io
import logging
from hashlib import md5

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.db.minio_client import list_documents, download_document
from src.rag.vector_store import add_documents, search_documents

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


def ingest_all_documents(prefix: str = "") -> int:
    """Ingest all documents from MinIO into the vector store.
    
    Returns the number of chunks added.
    """
    docs = list_documents(prefix=prefix)
    total_chunks = 0

    for doc_info in docs:
        object_name = doc_info["name"]
        logger.info(f"Processing: {object_name}")

        try:
            data = download_document(object_name)
            text = extract_text(object_name, data)
            if not text.strip():
                logger.warning(f"No text extracted from {object_name}")
                continue

            chunks = _splitter.split_text(text)
            if not chunks:
                continue

            ids = []
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_id = md5(f"{object_name}::{i}".encode()).hexdigest()
                ids.append(chunk_id)
                metadatas.append({
                    "source": object_name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                })

            add_documents(ids=ids, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
            logger.info(f"  Added {len(chunks)} chunks from {object_name}")

        except Exception as e:
            logger.error(f"Failed to process {object_name}: {e}")

    logger.info(f"Ingestion complete. Total chunks: {total_chunks}")
    return total_chunks


def search(query: str, topic: str | None = None, n_results: int = 5) -> list[dict]:
    """Search documents with optional topic filter."""
    where = None
    if topic:
        where = {"topic": topic}
    return search_documents(query=query, n_results=n_results, where=where)
