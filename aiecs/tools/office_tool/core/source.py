"""
Shared source resolution for office tools.

DocumentServer only accepts HTTP/HTTPS URLs. MCP resolves object storage paths
(gs://, s3://) to presigned/signed URLs before calling DocumentServer APIs.
"""

from typing import Any, Dict, Optional, Tuple, Union

from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SIGNED_URL_EXPIRY_SECONDS,
    get_file_ext,
    resolve_fetch_url,
    source_path_format_label,
    validate_source_path,
)


def is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


async def resolve_document_source(
    path_val: str,
    url_val: str,
    *,
    expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
) -> Union[Tuple[str, str, str, str], Dict[str, Any]]:
    """
    Resolve source_path or source_url to a DocumentServer-fetchable URL.

    Returns:
        (fetch_url, file_ext, path_val, source_path_format) on success
        {"isError": True, "text": str} on failure
    """
    if path_val and url_val:
        return {"isError": True, "text": "Provide source_path OR source_url, not both"}
    if not path_val and not url_val:
        return {
            "isError": True,
            "text": f"Provide source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url (HTTP/HTTPS)",
        }

    if path_val:
        err = validate_source_path(path_val)
        if err:
            return {"isError": True, "text": err}
        try:
            fetch_url = await resolve_fetch_url(path_val, expiry_seconds=expiry_seconds)
        except Exception as e:
            return {"isError": True, "text": f"Failed to resolve object storage URL: {e}"}
        return (
            fetch_url,
            get_file_ext(path_val),
            path_val,
            source_path_format_label(path_val),
        )

    if not is_http_url(url_val):
        return {"isError": True, "text": "source_url must be HTTP or HTTPS URL"}
    return (url_val, get_file_ext(url_val), "", "source_url (HTTP/HTTPS)")
