"""
Temporary object fetch registry for DocumentServer.

ONLYOFFICE DocumentServer often fails on S3 presigned URLs (HEAD/GET quirks).
When MCP_PUBLIC_URL is set, s3:// paths are exposed as plain HTTP URLs served
by this MCP process, which streams objects from MinIO using SDK credentials.
"""

import logging
import os
import time
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# token -> (storage_path, expires_at_monotonic)
_fetch_store: dict[str, Tuple[str, float]] = {}


def _use_minio_proxy() -> bool:
    mode = os.environ.get("MINIO_FETCH_MODE", "").strip().lower()
    if mode == "presign":
        return False
    if mode == "proxy":
        return True
    return bool(os.environ.get("MCP_PUBLIC_URL", "").strip())


def register_fetch_path(storage_path: str, ttl_seconds: int) -> str:
    """Register s3:// path and return opaque fetch token."""
    token = uuid.uuid4().hex
    _fetch_store[token] = (storage_path, time.monotonic() + ttl_seconds)
    return token


def _resolve_token(token: str) -> Optional[str]:
    entry = _fetch_store.get(token)
    if not entry:
        return None
    storage_path, expires_at = entry
    if time.monotonic() > expires_at:
        _fetch_store.pop(token, None)
        return None
    return storage_path


def _guess_content_type(key: str) -> str:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pdf": "application/pdf",
        "html": "text/html",
        "docbuilder": "text/plain",
    }.get(ext, "application/octet-stream")


async def build_s3_fetch_url(s3_path: str, expiry_seconds: int) -> str:
    """Return MCP proxy URL for an s3:// object."""
    base = os.environ.get("MCP_PUBLIC_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError(
            "MCP_PUBLIC_URL is required for MinIO proxy fetch. "
            "Set MINIO_FETCH_MODE=presign to use presigned URLs instead."
        )
    token = register_fetch_path(s3_path, expiry_seconds)
    return f"{base}/storage-objects/{token}"


async def fetch_object_bytes(token: str) -> Optional[Tuple[bytes, str]]:
    """Load object bytes for a registered fetch token."""
    storage_path = _resolve_token(token)
    if not storage_path:
        return None

    from aiecs.tools.office_tool.storage_paths import parse_storage_path

    parsed = parse_storage_path(storage_path)
    if parsed.scheme == "s3":
        from aiecs.tools.office_tool.storage import _get_s3_client

        def _do():
            client = _get_s3_client()
            obj = client.get_object(Bucket=parsed.bucket, Key=parsed.key)
            body = obj["Body"].read()
            ctype = obj.get("ContentType") or _guess_content_type(parsed.key)
            return body, ctype

        import asyncio

        return await asyncio.to_thread(_do)

    if parsed.scheme == "gs":
        from aiecs.tools.office_tool.storage import _get_gcs_client

        def _do_gcs():
            client = _get_gcs_client()
            bucket = client.bucket(parsed.bucket)
            blob = bucket.blob(parsed.key)
            data = blob.download_as_bytes()
            return data, _guess_content_type(parsed.key)

        import asyncio

        return await asyncio.to_thread(_do_gcs)

    return None
