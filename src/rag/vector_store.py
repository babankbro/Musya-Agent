import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config import get_settings

_chroma_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        s = get_settings()
        _chroma_client = chromadb.PersistentClient(
            path=s.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_collection(name: str | None = None) -> chromadb.Collection:
    """Get or create the document collection."""
    s = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name or s.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
    collection_name: str | None = None,
) -> None:
    """Add document chunks to the vector store."""
    collection = get_collection(collection_name)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def search_documents(
    query: str,
    n_results: int = 5,
    where: dict | None = None,
    collection_name: str | None = None,
) -> list[dict]:
    """Semantic search over document chunks."""
    collection = get_collection(collection_name)
    kwargs: dict = {"query_texts": [query], "n_results": n_results}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    docs = []
    if results and results["documents"]:
        for i, doc_text in enumerate(results["documents"][0]):
            entry = {
                "text": doc_text,
                "distance": results["distances"][0][i] if results.get("distances") else None,
            }
            if results.get("metadatas") and results["metadatas"][0]:
                entry["metadata"] = results["metadatas"][0][i]
            if results.get("ids") and results["ids"][0]:
                entry["id"] = results["ids"][0][i]
            docs.append(entry)
    return docs
