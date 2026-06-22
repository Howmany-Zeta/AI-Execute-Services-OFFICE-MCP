"""
Legacy Conversion API coarse read helpers.

Used by legacy/read_document.py and future office_read_{category} coarse mode.
"""

import logging
import uuid
from typing import Any, Dict, Optional, Tuple

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    CONVERT_TIMEOUT,
    get_documentserver_client,
)
from aiecs.tools.office_tool.core.categories import llm_coarse_output_type
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.core.coarse_parsers import (
    extract_outline,
    extract_outline_from_csv,
    extract_outline_from_txt,
    extract_plain_text,
    parse_csv_to_structure,
    parse_html_to_structure,
    parse_txt_to_structure,
)

logger = logging.getLogger(__name__)

INDEX_NOTE = (
    "index is logical order only, NOT for Builder GetElement(i). "
    "Use Search(text) or GetStyleName() for positioning in office_edit_document."
)


def _parse_converted_content(
    content: str,
    output_type: str,
    format: str,
) -> Dict[str, Any]:
    """Parse converted file body based on output type and requested format."""
    if format == "text":
        if output_type == "html":
            return {"text": extract_plain_text(content)}
        return {"text": content}

    if format == "outline":
        if output_type == "html":
            return {"outline": extract_outline(content), "_note": INDEX_NOTE}
        if output_type == "csv":
            return {"outline": extract_outline_from_csv(content), "_note": INDEX_NOTE}
        return {"outline": extract_outline_from_txt(content), "_note": INDEX_NOTE}

    if output_type == "html":
        structure = parse_html_to_structure(content)
    elif output_type == "csv":
        structure = parse_csv_to_structure(content)
    else:
        structure = parse_txt_to_structure(content)

    return {
        "title": structure["title"],
        "elements": structure["elements"],
        "word_count": structure["word_count"],
        "page_count": structure["page_count"],
        "_note": INDEX_NOTE,
    }


async def convert_and_fetch(
    fetch_url: str,
    file_ext: str,
    output_type: str,
    client: DocumentServerClient | None = None,
) -> tuple[str | None, str | None]:
    """Run Conversion API async poll and download converted body text."""
    ds_client = client or get_documentserver_client()
    key = str(uuid.uuid4())
    convert_params = {
        "url": fetch_url,
        "filetype": file_ext,
        "outputtype": output_type,
        "key": key,
    }

    try:
        result = await ds_client.convert_until_complete(convert_params)
    except httpx.HTTPStatusError as e:
        logger.error(f"Conversion API error: {e}")
        return None, f"Conversion API error: {e.response.status_code} {e.response.text[:500]}"
    except httpx.TimeoutException:
        return None, f"Conversion API timeout (>{CONVERT_TIMEOUT}s)"
    except Exception as e:
        logger.exception("convert_and_fetch failed")
        return None, str(e)

    if result.get("error"):
        code = result.get("error")
        hint = ""
        if code == -7:
            hint = f" (unsupported conversion: {file_ext} -> {output_type})"
        elif code == -2:
            hint = " (conversion timed out during async polling)"
        return None, f"Conversion API error code: {code}{hint}"

    if not result.get("endConvert", False):
        return None, "Conversion not complete after async polling"

    file_url = result.get("fileUrl")
    if not file_url:
        return None, "Conversion API did not return fileUrl"

    try:
        async with httpx.AsyncClient(timeout=CONVERT_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            return response.text, None
    except Exception as e:
        logger.exception("Failed to fetch converted file")
        return None, str(e)


async def coarse_read_legacy(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "structured",
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Legacy office_read_document behavior via Conversion API coarse read.

    Returns elements/text/outline per §11.2 frozen behavior.
    """
    path_val = (source_path or "").strip()
    url_val = (source_url or "").strip()

    if format not in ("structured", "text", "outline"):
        return err(f"format must be structured, text, or outline; got {format}")

    resolved = await resolve_document_source(path_val, url_val)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, storage_path, source_path_format = resolved
    output_type = llm_coarse_output_type(file_ext)
    logger.info(
        "coarse_read_legacy: filetype=%s outputtype=%s format=%s",
        file_ext,
        output_type,
        format,
    )

    content, fetch_error = await convert_and_fetch(fetch_url, file_ext, output_type, client=client)
    if fetch_error:
        return err(fetch_error)

    meta = {
        "source_path_format": source_path_format,
        "accepted_source_path_formats": ACCEPTED_SOURCE_PATH_FORMATS,
        "conversion_output_type": output_type,
    }
    if storage_path:
        meta["source_path"] = storage_path

    parsed = _parse_converted_content(content, output_type, format)
    return {**parsed, **meta}
