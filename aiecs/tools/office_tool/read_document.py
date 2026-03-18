"""
office_read_document: Read document structure via Conversion API.

Converts document to HTML via Conversion API, parses DOM to extract structure.
No Builder API. Format: structured | text | outline.
"""

import logging
import uuid
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    CONVERT_TIMEOUT,
)
from aiecs.tools.office_tool.storage import get_signed_url, get_file_ext
from aiecs.tools.office_tool.html_parser import (
    parse_html_to_structure,
    extract_plain_text,
    extract_outline,
)

logger = logging.getLogger(__name__)

INDEX_NOTE = (
    "index is logical order only, NOT for Builder GetElement(i). "
    "Use Search(text) or GetStyleName() for positioning in office_edit_document."
)

OFFICE_READ_DOCUMENT_TOOL = {
    "name": "office_read_document",
    "description": (
        "Read document structure and content. Provide source_path (GCS gs://) OR source_url (HTTP/HTTPS). "
        "Uses Conversion API to convert to HTML, then parses structure. "
        "Returns elements, word_count, page_count. "
        "IMPORTANT: The index in elements is for logical order only - do NOT use it with "
        "Builder GetElement(index). Use Search(text) or GetStyleName() for positioning in office_edit_document."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": "GCS path (gs://bucket/path/file.docx). Optional if source_url provided.",
            },
            "source_url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to document. Caller provides fetchable URL. Optional if source_path provided.",
            },
            "format": {
                "type": "string",
                "enum": ["structured", "text", "outline"],
                "default": "structured",
                "description": "structured: full structure; text: plain text; outline: headings only",
            },
        },
        "required": [],
    },
}


def _is_http_url(s: str) -> bool:
    """Check if string is HTTP/HTTPS URL."""
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


async def office_read_document(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "structured",
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Read document structure: Conversion API to HTML, parse DOM.

    Args:
        source_path: GCS path (gs://bucket/path). Optional if source_url provided.
        source_url: HTTP/HTTPS URL to document. Optional if source_path provided.
        format: "structured" | "text" | "outline"
        client: Optional DocumentServerClient

    Returns:
        {"title", "elements", "word_count", "page_count", "_note"} for structured
        {"text": str} for text
        {"outline": [...]} for outline
        or {"isError": True, "text": str}
    """
    path_val = (source_path or "").strip()
    url_val = (source_url or "").strip()

    if path_val and url_val:
        return {"isError": True, "text": "Provide source_path OR source_url, not both"}
    if not path_val and not url_val:
        return {"isError": True, "text": "Provide source_path (gs://) or source_url (HTTP/HTTPS)"}

    if format not in ("structured", "text", "outline"):
        return {"isError": True, "text": f"format must be structured, text, or outline; got {format}"}

    ds_client = client or get_documentserver_client()

    if path_val:
        if not path_val.startswith("gs://"):
            return {"isError": True, "text": "source_path must be a GCS path (gs://bucket/path)"}
        try:
            fetch_url = await get_signed_url(path_val)
        except Exception as e:
            return {"isError": True, "text": f"Failed to get signed URL: {e}"}
        file_ext = get_file_ext(path_val)
    else:
        if not _is_http_url(url_val):
            return {"isError": True, "text": "source_url must be HTTP or HTTPS URL"}
        fetch_url = url_val
        file_ext = get_file_ext(url_val)
    key = str(uuid.uuid4())

    try:
        result = await ds_client.convert({
            "url": fetch_url,
            "filetype": file_ext,
            "outputtype": "html",
            "key": key,
        })
    except httpx.HTTPStatusError as e:
        logger.error(f"Conversion API error: {e}")
        return {"isError": True, "text": f"Conversion API error: {e.response.status_code} {e.response.text[:500]}"}
    except httpx.TimeoutException:
        return {"isError": True, "text": f"Conversion API timeout (>{CONVERT_TIMEOUT}s)"}
    except Exception as e:
        logger.exception("office_read_document Conversion failed")
        return {"isError": True, "text": str(e)}

    if result.get("error"):
        return {"isError": True, "text": f"Conversion API error code: {result.get('error')}"}

    if not result.get("endConvert", False):
        return {"isError": True, "text": "Conversion not complete (async conversion not supported)"}

    file_url = result.get("fileUrl")
    if not file_url:
        return {"isError": True, "text": "Conversion API did not return fileUrl"}

    # Fetch HTML content
    try:
        async with httpx.AsyncClient(timeout=CONVERT_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        logger.exception("Failed to fetch converted HTML")
        return {"isError": True, "text": str(e)}

    if format == "text":
        return {"text": extract_plain_text(html)}

    if format == "outline":
        return {"outline": extract_outline(html), "_note": INDEX_NOTE}

    # structured
    structure = parse_html_to_structure(html)
    return {
        "title": structure["title"],
        "elements": structure["elements"],
        "word_count": structure["word_count"],
        "page_count": structure["page_count"],
        "_note": INDEX_NOTE,
    }
