import io

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


def browse_minio(prefix: str = "") -> dict:
    """Browse MinIO bucket non-recursively — like the MinIO console UI.
    
    Returns folders and files at the given prefix level.
    prefix should end with '/' if non-empty (e.g. 'accident/').
    """
    s = get_settings()
    client = get_minio_client()

    # Normalize prefix: ensure trailing slash if non-empty
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"

    objects = client.list_objects(s.MINIO_BUCKET, prefix=prefix, recursive=False)

    folders = []
    files = []
    for obj in objects:
        name = obj.object_name or ""
        if obj.is_dir or name.endswith("/"):
            # Strip the leading prefix and trailing slash to get folder name
            rel = name[len(prefix):].rstrip("/")
            if rel:
                folders.append({
                    "name": rel,
                    "full_path": name,
                    "type": "folder",
                    "size": None,
                    "last_modified": None,
                })
        else:
            # Skip .folder marker files
            rel = name[len(prefix):]
            if not rel or rel == ".folder":
                continue
            lm = obj.last_modified
            files.append({
                "name": rel,
                "full_path": name,
                "type": "file",
                "size": obj.size or 0,
                "last_modified": lm.isoformat() if lm else None,
                "content_type": obj.content_type or "",
                "ext": rel.rsplit(".", 1)[-1].lower() if "." in rel else "",
            })

    return {
        "bucket": s.MINIO_BUCKET,
        "prefix": prefix,
        "folders": folders,
        "files": files,
    }


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


def upload_to_minio(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload bytes to MinIO bucket."""
    s = get_settings()
    client = get_minio_client()
    # Ensure bucket exists
    if not client.bucket_exists(s.MINIO_BUCKET):
        client.make_bucket(s.MINIO_BUCKET)
    client.put_object(
        s.MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def delete_from_minio(object_name: str) -> bool:
    """Delete an object from MinIO. Returns True if successful."""
    s = get_settings()
    client = get_minio_client()
    try:
        client.remove_object(s.MINIO_BUCKET, object_name)
        return True
    except Exception:
        return False
