"""
office_read_document: model reading line. Projects documents to Markdown.

Does not call office_read_{category} fine (ADR-049 / §11.2 isolation).
"""

from typing import Any, Callable, Dict, Optional

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.caller_io import INLINE_SOURCE_PROPERTIES, SOURCE_PATH_INTERNAL
from aiecs.tools.office_tool.core.document_read import read_document_markdown
from aiecs.tools.office_tool.core.read_markdown import READ_NOTE
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS

OFFICE_READ_DOCUMENT_TOOL = {
    "name": "office_read_document",
    "description": (
        "Read a document as clean Markdown for model reading only. "
        f"Provide source_url or content_base64. source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "is internal compatibility only. No caller bucket required. "
        f"{READ_NOTE}"
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
                "enum": ["markdown", "plain", "outline"],
                "default": "markdown",
                "description": "markdown: full Markdown; plain: unmarked text; outline: headings only",
            },
            "options": {
                "type": "object",
                "properties": {
                    "accept": {
                        "type": "string",
                        "enum": [
                            "application/json",
                            "text/markdown",
                            "text/plain",
                            "application/zip",
                        ],
                        "default": "application/json",
                    },
                    "page_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "1-based inclusive [start, end] matching [Page N] markers",
                    },
                    "media_delivery": {
                        "type": "string",
                        "enum": ["fetch_token", "caller_bucket"],
                        "default": "fetch_token",
                    },
                    "media_output_path": {
                        "type": "string",
                        "description": "s3:// or gs:// directory when media_delivery=caller_bucket",
                    },
                },
            },
        },
        "required": [],
    },
}


async def office_read_document(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "markdown",
    client: Optional[DocumentServerClient] = None,
    content_base64: Optional[str] = None,
    source_bytes: Optional[str] = None,
    filename: Optional[str] = None,
    options: Optional[dict] = None,
) -> Dict[str, Any] | str:
    """Read a document as Markdown for model reading. Not an edit locator."""
    return await read_document_markdown(
        source_path=source_path,
        source_url=source_url,
        format=format,
        client=client,
        content_base64=content_base64,
        source_bytes=source_bytes,
        filename=filename,
        options=options,
    )


LEGACY_ALIASES: list[tuple[str, Callable[..., Any], dict]] = [
    ("office_read_document", office_read_document, OFFICE_READ_DOCUMENT_TOOL),
]

__all__ = [
    "LEGACY_ALIASES",
    "OFFICE_READ_DOCUMENT_TOOL",
    "office_read_document",
]
