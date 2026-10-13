"""
Shared source resolution for office tools.

DocumentServer only accepts HTTP/HTTPS URLs. MCP resolves object storage paths
(gs://, s3://) to fetch URLs, and HTTP source_url to a DocumentServer-reachable
origin. Caller MinIO credentials stay on the caller side.
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple, Union

import httpx

from aiecs.tools.office_tool.core.caller_io import decode_inline_file, sniff_office_ext
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SIGNED_URL_EXPIRY_SECONDS,
    SourceTooLargeError,
    get_file_ext,
    resolve_fetch_url,
    source_path_format_label,
    validate_source_path,
)
from aiecs.tools.office_tool.core.storage.object_fetch import (
    build_bytes_fetch_url,
    is_mcp_proxy_url,
    mcp_public_base,
)

logger = logging.getLogger(__name__)

HTTP_SOURCE_TIMEOUT = 60.0
# exact source_url -> (proxy_url, ext, expires_at_monotonic)
_http_proxy_cache: dict[str, Tuple[str, str, float]] = {}


def is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


def _source_max_bytes() -> int:
    from aiecs.config import get_parse_job_config

    return int(get_parse_job_config().max_source_bytes)


async def _download_http_source(url: str, max_bytes: int) -> bytes:
    """GET the caller URL as-is (case and query preserved). No HEAD."""
    async with httpx.AsyncClient(timeout=HTTP_SOURCE_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.content
    if len(data) > max_bytes:
        raise SourceTooLargeError(f"source_too_large: {len(data)} > {max_bytes}")
    return data


async def _proxy_http_source_url(url: str, ext: str, expiry_seconds: int) -> str:
    """Download the presigned URL and expose it at MCP_PUBLIC_URL for DocumentServer."""
    now = time.monotonic()
    cached = _http_proxy_cache.get(url)
    if cached and now < cached[2]:
        return cached[0]
    data = await _download_http_source(url, _source_max_bytes())
    fetch_url = build_bytes_fetch_url(data, ext, expiry_seconds)
    _http_proxy_cache[url] = (fetch_url, ext, now + expiry_seconds)
    return fetch_url


async def resolve_document_source(
    path_val: str,
    url_val: str,
    *,
    expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
    content_base64: str | bytes | None = None,
    source_bytes: str | bytes | None = None,
    filename: str | None = None,
) -> Union[Tuple[str, str, str, str], Dict[str, Any]]:
    """
    Resolve source_url, content_base64, or source_path to a DocumentServer URL.

    source_url: extension comes from the path (not the query). When
    MCP_PUBLIC_URL is set, MCP GETs the original URL (signature case
    preserved) and DocumentServer pulls a clean proxy URL.

    content_base64 / source_bytes: staged on MCP_PUBLIC_URL. No caller bucket.

    source_path (gs:// / s3://): internal compatibility only. MCP does not
    read caller MINIO_*.

    Returns:
        (fetch_url, file_ext, path_val, source_path_format) on success
        {"isError": True, "text": str} on failure
    """
    data, decode_err = decode_inline_file(content_base64, source_bytes)
    if decode_err:
        return err(decode_err)
    n = sum([bool((path_val or "").strip()), bool((url_val or "").strip()), data is not None])
    if n > 1:
        return err("Provide only one of source_path, source_url, or content_base64")
    if n == 0:
        return err(
            "Provide source_url, content_base64, or source_path "
            f"({ACCEPTED_SOURCE_PATH_FORMATS}, internal compatibility)"
        )

    if data is not None:
        if not mcp_public_base():
            return err(
                "content_base64 requires MCP_PUBLIC_URL so DocumentServer can fetch the file"
            )
        ext = sniff_office_ext(data, filename)
        try:
            fetch_url = build_bytes_fetch_url(data, ext, expiry_seconds)
        except Exception as e:
            return err(f"Failed to stage content_base64: {e}")
        return (fetch_url, ext, "", "content_base64")

    if path_val:
        path_err = validate_source_path(path_val)
        if path_err:
            return err(path_err)
        try:
            fetch_url = await resolve_fetch_url(path_val, expiry_seconds=expiry_seconds)
        except Exception as e:
            return err(f"Failed to resolve object storage URL: {e}")
        return (
            fetch_url,
            get_file_ext(path_val),
            path_val,
            source_path_format_label(path_val),
        )

    if not is_http_url(url_val):
        return err("source_url must be HTTP or HTTPS URL")

    file_ext = get_file_ext(url_val)
    if is_mcp_proxy_url(url_val) or not mcp_public_base():
        return (url_val, file_ext, "", "source_url (HTTP/HTTPS)")

    try:
        fetch_url = await _proxy_http_source_url(url_val, file_ext, expiry_seconds)
    except SourceTooLargeError as e:
        return err(str(e))
    except Exception as e:
        logger.exception("Failed to fetch source_url for DocumentServer proxy")
        return err(f"Failed to fetch source_url: {e}")
    return (fetch_url, file_ext, "", "source_url (HTTP/HTTPS)")
