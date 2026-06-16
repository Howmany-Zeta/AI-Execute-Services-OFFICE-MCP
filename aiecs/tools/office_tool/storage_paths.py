"""
Object storage path parsing and validation for office tools.

Accepted source_path / output_path schemes (DocumentServer receives HTTP URL;
MCP resolves object paths to presigned/signed URLs):

  gs://bucket/path/to/file.ext   — Google Cloud Storage
  s3://bucket/path/to/file.ext   — MinIO / S3-compatible (MINIO_* env required)
"""

from typing import NamedTuple, Optional, Tuple

# Documented formats returned in tool responses and schema descriptions
ACCEPTED_SOURCE_PATH_FORMATS = (
    "gs://bucket/path/to/file.ext (GCS) | s3://bucket/path/to/file.ext (MinIO/S3)"
)

SOURCE_PATH_FORMAT_GCS = "gs://bucket/path/to/file.ext"
SOURCE_PATH_FORMAT_S3 = "s3://bucket/path/to/file.ext"


class StoragePath(NamedTuple):
    scheme: str  # "gs" or "s3"
    bucket: str
    key: str


def is_object_storage_path(path: str) -> bool:
    """True when path uses gs:// or s3://."""
    p = (path or "").strip()
    return p.startswith("gs://") or p.startswith("s3://")


def parse_storage_path(path: str) -> StoragePath:
    """
    Parse gs:// or s3:// URI into (scheme, bucket, key).

    Raises:
        ValueError: if path is not a valid object-storage URI.
    """
    p = (path or "").strip()
    if p.startswith("gs://"):
        scheme = "gs"
        rest = p[5:]
    elif p.startswith("s3://"):
        scheme = "s3"
        rest = p[5:]
    else:
        raise ValueError(
            f"Not an object storage path: {path!r}. "
            f"Accepted: {ACCEPTED_SOURCE_PATH_FORMATS}"
        )
    if "/" not in rest:
        raise ValueError(f"Invalid object storage path (missing object key): {path}")
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid object storage path: {path}")
    return StoragePath(scheme=scheme, bucket=bucket, key=key)


def validate_source_path(path: str) -> Optional[str]:
    """
    Validate source_path format.

    Returns:
        None if valid, else human-readable error string.
    """
    p = (path or "").strip()
    if not p:
        return "source_path is empty"
    if p.startswith("http://") or p.startswith("https://"):
        return "Use source_url for HTTP/HTTPS; source_path accepts gs:// or s3:// only"
    if not is_object_storage_path(p):
        return f"source_path must be gs:// or s3:// URI. Accepted: {ACCEPTED_SOURCE_PATH_FORMATS}"
    try:
        parse_storage_path(p)
    except ValueError as e:
        return str(e)
    return None


def source_path_format_label(path: str) -> str:
    """Return the format label for a resolved source_path."""
    p = (path or "").strip()
    if p.startswith("s3://"):
        return SOURCE_PATH_FORMAT_S3
    if p.startswith("gs://"):
        return SOURCE_PATH_FORMAT_GCS
    return ACCEPTED_SOURCE_PATH_FORMATS
