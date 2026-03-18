"""
Storage utilities for office tools.

Supports local paths and GCS (gs://). Signed URL expiry = 2 * BUILDER_TIMEOUT.
"""

import asyncio
import logging
from pathlib import Path
from typing import Tuple

from aiecs.clients.documentserver_client import BUILDER_TIMEOUT

logger = logging.getLogger(__name__)

# Signed URL validity: 2x builder timeout (design: avoid expiry during script execution)
SIGNED_URL_EXPIRY_SECONDS = 2 * BUILDER_TIMEOUT  # 240 seconds


def _parse_gcs_path(path: str) -> Tuple[str, str]:
    """Parse gs://bucket/path into (bucket, blob_path)."""
    if not path.startswith("gs://"):
        raise ValueError(f"Not a GCS path: {path}")
    rest = path[5:]  # strip gs://
    if "/" not in rest:
        raise ValueError(f"Invalid GCS path: {path}")
    bucket, _, blob_path = rest.partition("/")
    return bucket, blob_path


def _get_gcs_client():
    """Lazy import of GCS client."""
    from google.cloud import storage

    return storage.Client()


async def get_signed_url(gcs_path: str, expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS) -> str:
    """
    Generate a signed URL for reading a GCS object.

    Args:
        gcs_path: gs://bucket/path/to/file
        expiry_seconds: URL validity (default: 2 * BUILDER_TIMEOUT)

    Returns:
        Signed URL string
    """
    bucket_name, blob_path = _parse_gcs_path(gcs_path)

    def _do():
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=expiry_seconds,
            method="GET",
        )

    return await asyncio.to_thread(_do)


async def upload_to_storage(content: bytes, output_path: str) -> None:
    """
    Upload content to output_path.

    Supports:
    - Local paths: writes to filesystem
    - gs:// paths: uploads to GCS

    Args:
        content: File content bytes
        output_path: Destination path (local or gs://bucket/path)
    """
    if output_path.startswith("gs://"):
        bucket_name, blob_path = _parse_gcs_path(output_path)

        def _do():
            client = _get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.upload_from_string(content, content_type="application/octet-stream")

        await asyncio.to_thread(_do)
        logger.debug(f"Uploaded {len(content)} bytes to {output_path}")
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        logger.debug(f"Wrote {len(content)} bytes to {output_path}")


async def copy_gcs_file(source_path: str, dest_path: str) -> None:
    """
    Copy a file within GCS (or from GCS to GCS).

    Args:
        source_path: gs://bucket/source/path
        dest_path: gs://bucket/dest/path
    """
    src_bucket_name, src_blob_path = _parse_gcs_path(source_path)
    dest_bucket_name, dest_blob_path = _parse_gcs_path(dest_path)

    def _do():
        client = _get_gcs_client()
        src_bucket = client.bucket(src_bucket_name)
        src_blob = src_bucket.blob(src_blob_path)
        dest_bucket = client.bucket(dest_bucket_name)
        src_bucket.copy_blob(src_blob, dest_bucket, dest_blob_path)

    await asyncio.to_thread(_do)
    logger.debug(f"Copied {source_path} to {dest_path}")


def get_file_ext(path: str) -> str:
    """Extract file extension from path (e.g. docx, xlsx)."""
    p = path.rstrip("/")
    if "." in p:
        return p.split(".")[-1].lower()
    return "docx"
