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
) -> Union[Tuple[str, str, str, str], Dict[str, Any]]:
    """
    Resolve source_path or source_url to a DocumentServer-fetchable URL.

    source_url: extension comes from the path (not the query). When
    MCP_PUBLIC_URL is set, MCP GETs the original URL (signature case
    preserved) and DocumentServer pulls a clean proxy URL. Callers do
    not need MCP MinIO.

    Returns:
        (fetch_url, file_ext, path_val, source_path_format) on success
        {"isError": True, "text": str} on failure
    """
    if path_val and url_val:
        return err("Provide source_path OR source_url, not both")
    if not path_val and not url_val:
        return err(f"Provide source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url (HTTP/HTTPS)")

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
