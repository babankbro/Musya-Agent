"""Vector store backed by PostgreSQL + pgvector (replaces ChromaDB).

Embeddings are generated via Google Gemini gemini-embedding-001 API (3072-dim).
No local model download required — uses the existing GEMINI_API_KEY.
"""
import logging
from typing import Any

import psycopg2
import psycopg2.extras
from google import genai
from google.genai import types as genai_types

from src.config import get_settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_conn: Any | None = None

_EMBEDDING_DIM = 3072  # gemini-embedding-001 output dimension (matches vector(3072) in DB)


def _get_client() -> genai.Client:
    """Get (and cache) the Google Gemini client."""
    global _client
    if _client is None:
        s = get_settings()
        _client = genai.Client(api_key=s.GEMINI_API_KEY)
        logger.info("Google Gemini embedding client created: %s", s.EMBEDDING_MODEL)
    return _client


def _get_conn():
    """Get (and cache) a psycopg2 connection with pgvector support."""
    global _conn
    if _conn is None or _conn.closed:
        s = get_settings()
        _conn = psycopg2.connect(
            host=s.DB_HOST,
            port=s.DB_PORT,
            dbname=s.DB_NAME,
            user=s.DB_USER,
            password=s.DB_PASSWORD,
        )
        _conn.autocommit = False
        psycopg2.extras.register_uuid(_conn)
        with _conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            _conn.commit()
    return _conn


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using Google Gemini gemini-embedding-001."""
    s = get_settings()
    client = _get_client()
    vectors = []
    for text in texts:
        response = client.models.embed_content(
            model=s.EMBEDDING_MODEL,
            contents=text,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        vectors.append(response.embeddings[0].values)
    return vectors


def _embed_query(text: str) -> list[float]:
    """Embed a single query string (task_type=RETRIEVAL_QUERY)."""
    s = get_settings()
    client = _get_client()
    response = client.models.embed_content(
        model=s.EMBEDDING_MODEL,
        contents=text,
        config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return response.embeddings[0].values


def health_check() -> bool:
    """Check pgvector connectivity — used by health endpoint."""
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning("pgvector health check failed: %s", e)
        return False


def add_documents(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
    collection_name: str | None = None,
) -> None:
    """Embed and upsert document chunks into document_embeddings."""
    s = get_settings()
    collection = collection_name or s.PGVECTOR_COLLECTION
    metadatas = metadatas or [{} for _ in ids]

    vectors = _embed(documents)
    conn = _get_conn()

    try:
        with conn.cursor() as cur:
            for doc_id, text, vec, meta in zip(ids, documents, vectors, metadatas):
                cur.execute(
                    """
                    INSERT INTO document_embeddings
                        (id, collection, document, embedding,
                         source, title, topic, chunk_index, total_chunks,
                         page_ref, section_label, total_pages)
                    VALUES (%s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        document       = EXCLUDED.document,
                        embedding      = EXCLUDED.embedding,
                        source         = EXCLUDED.source,
                        title          = EXCLUDED.title,
                        topic          = EXCLUDED.topic,
                        chunk_index    = EXCLUDED.chunk_index,
                        total_chunks   = EXCLUDED.total_chunks,
                        page_ref       = EXCLUDED.page_ref,
                        section_label  = EXCLUDED.section_label,
                        total_pages    = EXCLUDED.total_pages
                    """,
                    (
                        doc_id,
                        collection,
                        text,
                        vec,
                        meta.get("source", ""),
                        meta.get("title", ""),
                        meta.get("topic", ""),
                        meta.get("chunk_index", -1),
                        meta.get("total_chunks", 0),
                        meta.get("page_ref", ""),
                        meta.get("section_label", ""),
                        meta.get("total_pages", 0),
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def search_documents(
    query: str,
    n_results: int = 5,
    where: dict | None = None,
    collection_name: str | None = None,
) -> list[dict]:
    """Semantic search using cosine similarity via pgvector."""
    global _conn
    s = get_settings()
    collection = collection_name or s.PGVECTOR_COLLECTION

    query_vec = _embed_query(query)

    # Build optional WHERE filter (supports topic filter used by document_rag.search)
    extra_where = ""
    if where:
        conditions = []
        for key in where:
            conditions.append(f"{key} = %s")
        extra_where = "AND " + " AND ".join(conditions)

    sql = f"""
        SELECT id, document, source, title, topic,
               chunk_index, total_chunks, page_ref, section_label, total_pages,
               1 - (embedding <=> %s::vector) AS similarity
        FROM   document_embeddings
        WHERE  collection = %s
               {extra_where}
        ORDER  BY embedding <=> %s::vector
        LIMIT  %s
    """
    # cosine distance query needs the vector twice (once for similarity calc, once for ORDER BY)
    params = [query_vec, collection] + (list(where.values()) if where else []) + [query_vec, n_results]

    conn = _get_conn()
    docs = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            for row in rows:
                docs.append({
                    "id": row["id"],
                    "text": row["document"],
                    "distance": float(1 - row["similarity"]),  # cosine distance (lower = closer)
                    "metadata": {
                        "source": row["source"],
                        "title": row["title"],
                        "topic": row["topic"],
                        "chunk_index": row["chunk_index"],
                        "total_chunks": row["total_chunks"],
                        "page_ref": row["page_ref"],
                        "section_label": row["section_label"],
                        "total_pages": row["total_pages"],
                    },
                })
    except Exception:
        # Reset stale connection so the next call can re-connect
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        raise
    return docs
