from minio import Minio
from src.config import get_settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    """Get or create the MinIO client (reuses ChatV1 config)."""
    global _client
    if _client is None:
        s = get_settings()
        _client = Minio(
            endpoint=s.minio_endpoint_url,
            access_key=s.MINIO_ACCESS_KEY,
            secret_key=s.MINIO_SECRET_KEY,
            secure=s.MINIO_USE_SSL,
        )
    return _client


def list_documents(prefix: str = "") -> list[dict]:
    """List all document objects in the uploads bucket."""
    s = get_settings()
    client = get_minio_client()
    objects = client.list_objects(s.MINIO_BUCKET, prefix=prefix, recursive=True)
    results = []
    for obj in objects:
        if obj.object_name and not obj.is_dir:
            results.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified,
                "content_type": obj.content_type,
            })
    return results


def download_document(object_name: str) -> bytes:
    """Download a document from MinIO and return its bytes."""
    s = get_settings()
    client = get_minio_client()
    response = client.get_object(s.MINIO_BUCKET, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
