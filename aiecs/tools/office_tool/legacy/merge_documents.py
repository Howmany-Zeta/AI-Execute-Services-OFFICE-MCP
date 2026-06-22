"""Legacy alias: office_merge_documents → office_merge_word."""

from typing import Any, Callable

from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.tools.merge import office_merge_word

OFFICE_MERGE_DOCUMENTS_TOOL = {
    "name": "office_merge_documents",
    "description": (
        f"Merge multiple documents into one output file. Provide source_paths ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "OR source_urls (HTTP/HTTPS). "
        "Documents are merged in order. Options: add_page_break, add_toc."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_paths": {"type": "array", "items": {"type": "string"}},
            "source_urls": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {
                    "add_page_break": {"type": "boolean"},
                    "add_toc": {"type": "boolean"},
                },
            },
        },
        "required": ["output_path"],
    },
}


async def office_merge_documents(*args: Any, **kwargs: Any) -> dict:
    return await office_merge_word(*args, **kwargs)


LEGACY_ALIASES: list[tuple[str, Callable, dict]] = [
    ("office_merge_documents", office_merge_documents, OFFICE_MERGE_DOCUMENTS_TOOL),
]

__all__ = ["LEGACY_ALIASES", "OFFICE_MERGE_DOCUMENTS_TOOL", "office_merge_documents"]
