"""Sync raw PDF/DOCX files from obsidian_raw_pdf/ to MinIO.

Uploads all files under Agent/obsidian_raw_pdf/{province}/... to MinIO under
the path obsidian-pdfs/{province}/{relative_path}. Records each upload in the
obsidian_pdf_assets table (idempotent — skips already-uploaded paths).

After upload, sets a public-read bucket policy on the obsidian-pdfs/ prefix so
PDFs are directly accessible via their MinIO URL without authentication.

Usage:
    python scripts/sync_obsidian_pdfs.py [--force]

Options:
    --force   Re-upload even files already recorded in the DB
"""
import json
import logging
import mimetypes
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_obsidian_pdfs")

# ── Skip patterns ──────────────────────────────────────────────────────────────
SKIP_NAMES = {".DS_Store", "Thumbs.db", ".folder", "desktop.ini"}
SKIP_EXTS  = {".tmp", ".bak", ".log"}


def _build_public_policy(bucket: str, prefix: str) -> str:
    """Return JSON bucket policy allowing anonymous GET on the given prefix."""
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/{prefix}/*"],
            }
        ],
    })


def _ensure_public_policy(client, bucket: str, prefix: str) -> None:
    """Set/merge public-read policy for the given prefix in the bucket."""
    try:
        policy_json = _build_public_policy(bucket, prefix)
        client.set_bucket_policy(bucket, policy_json)
        logger.info("Bucket policy set: anonymous GET on %s/%s/*", bucket, prefix)
    except Exception as e:
        logger.warning("Could not set bucket policy (non-fatal): %s", e)


def _minio_url(endpoint: str, port: int, bucket: str, minio_path: str) -> str:
    """Build a direct MinIO URL with proper URL-encoding for Thai filenames."""
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in minio_path.split("/"))
    return f"http://{endpoint}:{port}/{bucket}/{encoded}"


def sync_pdfs(force: bool = False) -> dict:
    """Walk obsidian_raw_pdf/, upload new files to MinIO, record in DB.

    Returns:
        dict with keys: uploaded, skipped, errors, total_files, elapsed_seconds
    """
    from src.config import get_settings
    from src.db.minio_client import get_minio_client, upload_to_minio
    from src.db.pool import query_db, execute_db

    settings = get_settings()
    start = time.time()

    agent_root = Path(__file__).parent.parent
    pdf_root   = agent_root / settings.OBSIDIAN_RAW_PDF_PATH
    prefix     = settings.OBSIDIAN_PDF_MINIO_PREFIX  # "obsidian-pdfs"
    bucket     = settings.MINIO_BUCKET               # "uploads"

    if not pdf_root.exists():
        raise FileNotFoundError(f"Raw PDF directory not found: {pdf_root}")

    # ── Set public-read policy once ────────────────────────────────────────────
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created bucket: %s", bucket)
    _ensure_public_policy(client, bucket, prefix)

    # ── Build set of already-uploaded minio_paths (for skip check) ────────────
    existing_paths: set[str] = set()
    if not force:
        rows = query_db("SELECT minio_path FROM obsidian_pdf_assets", ())
        existing_paths = {r["minio_path"] for r in rows}
        logger.info("Already uploaded: %d files", len(existing_paths))

    # ── Walk raw PDF directory ─────────────────────────────────────────────────
    uploaded = skipped = errors = total_files = 0
    now = datetime.now(timezone.utc)

    all_files = sorted(pdf_root.rglob("*"))
    for path in all_files:
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES:
            continue
        if path.suffix.lower() in SKIP_EXTS:
            continue

        total_files += 1
        rel = path.relative_to(pdf_root)          # e.g. มุกดาหาร/1.ดอนตาล.pdf
        parts = rel.parts

        if len(parts) < 1:
            skipped += 1
            continue

        province   = parts[0]                      # "มุกดาหาร"
        minio_path = f"{prefix}/{rel.as_posix()}"  # "obsidian-pdfs/มุกดาหาร/1.ดอนตาล.pdf"

        if minio_path in existing_paths:
            skipped += 1
            continue

        # ── Determine content type ─────────────────────────────────────────────
        content_type, _ = mimetypes.guess_type(path.name)
        content_type = content_type or "application/octet-stream"

        try:
            data = path.read_bytes()
            upload_to_minio(minio_path, data, content_type)

            minio_url = _minio_url(
                settings.MINIO_ENDPOINT, settings.MINIO_PORT, bucket, minio_path
            )

            execute_db(
                """
                INSERT INTO obsidian_pdf_assets
                    (province, filename, minio_path, minio_url, file_size, content_type, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (minio_path) DO UPDATE SET
                    minio_url    = EXCLUDED.minio_url,
                    file_size    = EXCLUDED.file_size,
                    content_type = EXCLUDED.content_type,
                    synced_at    = EXCLUDED.synced_at
                """,
                (province, path.name, minio_path, minio_url,
                 len(data), content_type, now),
            )

            uploaded += 1
            if uploaded % 20 == 0:
                logger.info("Progress: %d uploaded so far...", uploaded)

        except Exception as e:
            logger.error("Error uploading %s: %s", minio_path, e)
            errors += 1

    elapsed = round(time.time() - start, 2)

    # ── Province summary ───────────────────────────────────────────────────────
    rows = query_db(
        "SELECT province, COUNT(*) AS cnt FROM obsidian_pdf_assets GROUP BY province ORDER BY province",
        (),
    )
    logger.info("── Province totals in DB ──────────────────")
    for r in rows:
        logger.info("  %s: %d files", r["province"], r["cnt"])

    summary = {
        "uploaded": uploaded,
        "skipped": skipped,
        "errors": errors,
        "total_files": total_files,
        "elapsed_seconds": elapsed,
    }
    logger.info(
        "Sync complete in %.1fs: uploaded=%d skipped=%d errors=%d",
        elapsed, uploaded, skipped, errors,
    )
    return summary


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        logger.info("--force: re-uploading all files regardless of DB state")
    try:
        result = sync_pdfs(force=force)
        print("\n✅ Done:")
        for k, v in result.items():
            print(f"   {k}: {v}")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)
