"""Document ingestion endpoint."""
import logging
from fastapi import APIRouter, HTTPException

from src.rag.document_rag import ingest_all_documents

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


@router.post("/api/ingest")
async def ingest_documents(prefix: str = ""):
    """Trigger document ingestion from MinIO into ChromaDB vector store.
    
    Args:
        prefix: Optional prefix to filter MinIO objects
    
    Returns:
        Number of chunks ingested.
    """
    try:
        logger.info(f"Starting document ingestion (prefix='{prefix}')")
        chunk_count = ingest_all_documents(prefix=prefix)
        return {"status": "ok", "chunks_ingested": chunk_count}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
