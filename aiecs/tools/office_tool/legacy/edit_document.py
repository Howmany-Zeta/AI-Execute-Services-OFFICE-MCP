"""Legacy alias: office_edit_document → office_edit_word_script."""

from typing import Any, Callable

from aiecs.tools.office_tool.core.storage.paths import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.tools.edit_script import office_edit_word_script

OFFICE_EDIT_DOCUMENT_TOOL = {
    "name": "office_edit_document",
    "description": (
        f"Edit an existing document. Provide source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "OR source_url (HTTP/HTTPS). "
        "Opens the file via Builder OpenFile, executes the edit_script (edit logic only - do NOT include "
        "builder.OpenFile/SaveFile/CloseFile), saves to output_path. "
        "IMPORTANT: Use Search(text) or GetStyleName() for positioning - do NOT use GetElement(index). "
        "Recommended: call office_read_document first, then use Search() or GetStyleName() for targeting."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "edit_script": {"type": "string"},
            "output_path": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {"backup": {"type": "boolean"}},
            },
        },
        "required": ["edit_script", "output_path"],
    },
}


async def office_edit_document(*args: Any, **kwargs: Any) -> dict:
    return await office_edit_word_script(*args, **kwargs)


LEGACY_ALIASES: list[tuple[str, Callable, dict]] = [
    ("office_edit_document", office_edit_document, OFFICE_EDIT_DOCUMENT_TOOL),
]

__all__ = ["LEGACY_ALIASES", "OFFICE_EDIT_DOCUMENT_TOOL", "office_edit_document"]
