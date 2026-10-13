"""
Legacy office_read_document: Read document structure via Conversion API.

Behavior frozen (§11.2): Word->html, Presentation->txt, Spreadsheet->csv, PDF->txt.
"""

from typing import Any, Callable, Dict, Optional

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.caller_io import INLINE_SOURCE_PROPERTIES, SOURCE_PATH_INTERNAL
from aiecs.tools.office_tool.core.coarse_read import coarse_read_legacy
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS

OFFICE_READ_DOCUMENT_TOOL = {
    "name": "office_read_document",
    "description": (
        "Read document structure and content. Provide source_url or content_base64. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) is internal compatibility only. "
        "No caller bucket required. MCP does not read caller MINIO_*. "
        "Uses Conversion API with LLM-friendly output (Word->html, Presentation->txt, Spreadsheet->csv), "
        "with async polling for large files. Returns elements, word_count, page_count. "
        "IMPORTANT: The index in elements is for logical order only - do NOT use it with "
        "Builder GetElement(index). Use Search(text) or GetStyleName() for positioning in office_edit_document."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": SOURCE_PATH_INTERNAL,
            },
            "source_url": {
                "type": "string",
                "description": "Anonymous HTTP/HTTPS URL. Alternative to content_base64.",
            },
            **INLINE_SOURCE_PROPERTIES,
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


async def office_read_document(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "structured",
    client: Optional[DocumentServerClient] = None,
    content_base64: Optional[str] = None,
    source_bytes: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Read document structure via Conversion API (legacy coarse read)."""
    return await coarse_read_legacy(
        source_path=source_path,
        source_url=source_url,
        format=format,
        client=client,
        content_base64=content_base64,
        source_bytes=source_bytes,
        filename=filename,
    )


LEGACY_ALIASES: list[tuple[str, Callable[..., Any], dict]] = [
    ("office_read_document", office_read_document, OFFICE_READ_DOCUMENT_TOOL),
]

__all__ = [
    "LEGACY_ALIASES",
    "OFFICE_READ_DOCUMENT_TOOL",
    "office_read_document",
]
