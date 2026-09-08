"""
Storage utilities for office tools.

Supports local paths, GCS (gs://), and MinIO/S3 (s3://).
Object paths are resolved to HTTP presigned/signed URLs for DocumentServer.
Signed URL expiry = 2 * BUILDER_TIMEOUT.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Tuple

from aiecs.clients.documentserver_client import BUILDER_TIMEOUT
from aiecs.tools.office_tool.core.storage.paths import (
    backup_storage_path,
    is_object_storage_path,
    parse_storage_path,
)

logger = logging.getLogger(__name__)

# Signed URL validity: 2x builder timeout (design: avoid expiry during script execution)
SIGNED_URL_EXPIRY_SECONDS = 2 * BUILDER_TIMEOUT  # 1200 seconds


def _parse_gcs_path(path: str) -> Tuple[str, str]:
    """Parse gs://bucket/path into (bucket, blob_path)."""
    parsed = parse_storage_path(path)
    if parsed.scheme != "gs":
        raise ValueError(f"Not a GCS path: {path}")
    return parsed.bucket, parsed.key


def _get_gcs_client():
    """Lazy import of GCS client."""
    from google.cloud import storage

    return storage.Client()


@lru_cache()
def _get_s3_client():
    """Lazy cached boto3 S3 client for MinIO presign/upload."""
    import boto3
    from botocore.client import Config

    from aiecs.config import get_minio_config

    cfg = get_minio_config()
    if not cfg.is_configured():
        raise RuntimeError(
            "MinIO is not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY."
        )
    addressing = "path" if cfg.force_path_style else "auto"
    return boto3.client(
        "s3",
        endpoint_url=cfg.presign_endpoint(),
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
        region_name=cfg.region,
        config=Config(signature_version="s3v4", s3={"addressing_style": addressing}),
    )


async def _get_gcs_signed_url(gcs_path: str, expiry_seconds: int) -> str:
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


async def _get_s3_presigned_url(s3_path: str, expiry_seconds: int) -> str:
    parsed = parse_storage_path(s3_path)
    if parsed.scheme != "s3":
        raise ValueError(f"Not an s3:// path: {s3_path}")

    def _do():
        client = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": parsed.bucket, "Key": parsed.key},
            ExpiresIn=expiry_seconds,
        )

    return await asyncio.to_thread(_do)


async def resolve_fetch_url(
    storage_path: str,
    expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
) -> str:
    """
    Resolve gs:// or s3:// path to an HTTP URL DocumentServer can fetch.

    s3:// uses MCP proxy URL when MCP_PUBLIC_URL is set (default) because
    DocumentServer often fails on MinIO presigned URLs. Override with
    MINIO_FETCH_MODE=presign|proxy.
    """
    parsed = parse_storage_path(storage_path)
    if parsed.scheme == "gs":
        return await _get_gcs_signed_url(storage_path, expiry_seconds)
    if parsed.scheme == "s3":
        from aiecs.tools.office_tool.core.storage.object_fetch import _use_minio_proxy, build_s3_fetch_url

        if _use_minio_proxy():
            return await build_s3_fetch_url(storage_path, expiry_seconds)
        return await _get_s3_presigned_url(storage_path, expiry_seconds)
    raise ValueError(f"Unsupported storage scheme: {parsed.scheme}")


class SourceTooLargeError(Exception):
    """Object exceeds PARSE_MAX_SOURCE_BYTES."""


async def stat_object_size(storage_path: str) -> int:
    """Return object size in bytes for gs:// or s3://."""
    parsed = parse_storage_path(storage_path)
    if parsed.scheme == "gs":

        def _do_gcs():
            client = _get_gcs_client()
            blob = client.bucket(parsed.bucket).blob(parsed.key)
            blob.reload()
            return int(blob.size or 0)

        return await asyncio.to_thread(_do_gcs)
    if parsed.scheme == "s3":

        def _do_s3():
            client = _get_s3_client()
            resp = client.head_object(Bucket=parsed.bucket, Key=parsed.key)
            return int(resp["ContentLength"])

        return await asyncio.to_thread(_do_s3)
    raise ValueError(f"Unsupported storage scheme: {parsed.scheme}")


async def download_object_bytes(storage_path: str, max_bytes: int) -> bytes:
    """Download gs:// or s3:// object. Raises SourceTooLargeError if over max_bytes."""
    size = await stat_object_size(storage_path)
    if size > max_bytes:
        raise SourceTooLargeError(f"source_too_large: {size} > {max_bytes}")
    parsed = parse_storage_path(storage_path)
    if parsed.scheme == "gs":

        def _do_gcs():
            client = _get_gcs_client()
            return client.bucket(parsed.bucket).blob(parsed.key).download_as_bytes()

        data = await asyncio.to_thread(_do_gcs)
    elif parsed.scheme == "s3":

        def _do_s3():
            client = _get_s3_client()
            obj = client.get_object(Bucket=parsed.bucket, Key=parsed.key)
            return obj["Body"].read()

        data = await asyncio.to_thread(_do_s3)
    else:
        raise ValueError(f"Unsupported storage scheme: {parsed.scheme}")
    if len(data) > max_bytes:
        raise SourceTooLargeError(f"source_too_large: {len(data)} > {max_bytes}")
    return data


async def list_objects_under_prefix(prefix: str) -> list[str]:
    """List gs:// or s3:// object URIs under a prefix (inclusive of prefix as directory)."""
    parsed = parse_storage_path(prefix)
    key_prefix = parsed.key
    if key_prefix and not key_prefix.endswith("/"):
        key_prefix += "/"
    if parsed.scheme == "gs":

        def _do_gcs():
            client = _get_gcs_client()
            return [f"gs://{parsed.bucket}/{blob.name}" for blob in client.list_blobs(parsed.bucket, prefix=key_prefix)]

        return await asyncio.to_thread(_do_gcs)
    if parsed.scheme == "s3":

        def _do_s3():
            client = _get_s3_client()
            uris: list[str] = []
            token = None
            while True:
                kwargs: dict = {"Bucket": parsed.bucket, "Prefix": key_prefix}
                if token:
                    kwargs["ContinuationToken"] = token
                resp = client.list_objects_v2(**kwargs)
                for obj in resp.get("Contents") or []:
                    uris.append(f"s3://{parsed.bucket}/{obj['Key']}")
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
            return uris

        return await asyncio.to_thread(_do_s3)
    raise ValueError(f"Unsupported storage scheme: {parsed.scheme}")


async def delete_prefix(prefix: str) -> None:
    """Best-effort delete of every object under a gs:// or s3:// prefix."""
    for uri in await list_objects_under_prefix(prefix):
        await delete_object(uri)


async def delete_object(storage_path: str) -> None:
    """Best-effort delete of gs:// or s3:// object."""
    parsed = parse_storage_path(storage_path)
    try:
        if parsed.scheme == "gs":

            def _do_gcs():
                client = _get_gcs_client()
                client.bucket(parsed.bucket).blob(parsed.key).delete()

            await asyncio.to_thread(_do_gcs)
        elif parsed.scheme == "s3":

            def _do_s3():
                _get_s3_client().delete_object(Bucket=parsed.bucket, Key=parsed.key)

            await asyncio.to_thread(_do_s3)
    except Exception:
        logger.warning("Failed to delete staging object %s", storage_path, exc_info=True)


async def get_signed_url(gcs_path: str, expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS) -> str:
    """Backward-compatible alias: resolve gs:// or s3:// to fetch URL."""
    return await resolve_fetch_url(gcs_path, expiry_seconds=expiry_seconds)


async def upload_to_storage(content: bytes, output_path: str) -> None:
    """
    Upload content to output_path.

    Supports:
    - Local paths: writes to filesystem
    - gs:// paths: uploads to GCS
    - s3:// paths: uploads to MinIO/S3
    """
    if output_path.startswith("gs://"):
        bucket_name, blob_path = _parse_gcs_path(output_path)

        def _do_gcs():
            client = _get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.upload_from_string(content, content_type="application/octet-stream")

        await asyncio.to_thread(_do_gcs)
        logger.debug(f"Uploaded {len(content)} bytes to {output_path}")
    elif output_path.startswith("s3://"):
        parsed = parse_storage_path(output_path)

        def _do_s3():
            client = _get_s3_client()
            client.put_object(Bucket=parsed.bucket, Key=parsed.key, Body=content)

        await asyncio.to_thread(_do_s3)
        logger.debug(f"Uploaded {len(content)} bytes to {output_path}")
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        logger.debug(f"Wrote {len(content)} bytes to {output_path}")


async def copy_storage_file(source_path: str, dest_path: str) -> None:
    """Copy an object within the same backend (gs:// or s3://)."""
    src = parse_storage_path(source_path)
    dest = parse_storage_path(dest_path)
    if src.scheme != dest.scheme:
        raise ValueError(f"Cannot copy across storage backends: {source_path} -> {dest_path}")

    if src.scheme == "gs":

        def _do_gcs():
            client = _get_gcs_client()
            src_bucket = client.bucket(src.bucket)
            src_blob = src_bucket.blob(src.key)
            dest_bucket = client.bucket(dest.bucket)
            src_bucket.copy_blob(src_blob, dest_bucket, dest.key)

        await asyncio.to_thread(_do_gcs)
    else:

        def _do_s3():
            client = _get_s3_client()
            client.copy_object(
                CopySource={"Bucket": src.bucket, "Key": src.key},
                Bucket=dest.bucket,
                Key=dest.key,
            )

        await asyncio.to_thread(_do_s3)

    logger.debug(f"Copied {source_path} to {dest_path}")


async def copy_source_to_backup(source_path: str) -> tuple[str | None, str | None]:
    """
    Copy source object to a timestamped backup path.

    Returns:
        (backup_path, None) on success, or (None, error_message) on failure.
    """
    if not is_object_storage_path(source_path):
        return None, "options.backup requires source_path (gs:// or s3://)"
    dest_path = backup_storage_path(source_path)
    try:
        await copy_storage_file(source_path, dest_path)
        return dest_path, None
    except Exception as e:
        logger.exception("Backup failed")
        return None, f"Backup failed: {e}"


async def copy_gcs_file(source_path: str, dest_path: str) -> None:
    """Backward-compatible alias for copy_storage_file (gs:// or s3://)."""
    await copy_storage_file(source_path, dest_path)


def get_file_ext(path: str) -> str:
    """Extract file extension from path (e.g. docx, xlsx)."""
    p = path.rstrip("/")
    if "." in p:
        return p.split(".")[-1].lower()
    return "docx"
