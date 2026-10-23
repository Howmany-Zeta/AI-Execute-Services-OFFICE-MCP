"""Legacy alias: office_edit_document → office_edit_word_script."""

from typing import Any, Callable

from aiecs.tools.office_tool.core.caller_io import INLINE_SOURCE_PROPERTIES, SOURCE_PATH_INTERNAL
from aiecs.tools.office_tool.core.storage.paths import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.tools.edit_script import office_edit_word_script

OFFICE_EDIT_DOCUMENT_TOOL = {
    "name": "office_edit_document",
    "description": (
        "Edit an existing document. Provide source_url or content_base64. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) is internal compatibility only. "
        "Opens the file via Builder OpenFile, executes the edit_script (edit logic only - do NOT include "
        "builder.OpenFile/SaveFile/CloseFile). "
        "output_path is optional; omit to get content_base64 (does not write a caller bucket). "
        "s3:// / gs:// output_path keeps the old internal upload. "
        "IMPORTANT: Use Search(text) or GetStyleName() for positioning - do NOT use GetElement(index). "
        "For edit locators call office_read_word (fine), not office_read_document."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string", "description": SOURCE_PATH_INTERNAL},
            "source_url": {"type": "string"},
            **INLINE_SOURCE_PROPERTIES,
            "edit_script": {"type": "string"},
            "output_path": {
                "type": "string",
                "description": (
                    "Optional. Omit to return content_base64. "
                    "s3:// or gs:// keeps the old internal upload."
                ),
            },
            "options": {
                "type": "object",
                "properties": {"backup": {"type": "boolean"}},
            },
        },
        "required": ["edit_script"],
    },
}


async def office_edit_document(*args: Any, **kwargs: Any) -> dict:
    return await office_edit_word_script(*args, **kwargs)


LEGACY_ALIASES: list[tuple[str, Callable, dict]] = [
    ("office_edit_document", office_edit_document, OFFICE_EDIT_DOCUMENT_TOOL),
]

__all__ = ["LEGACY_ALIASES", "OFFICE_EDIT_DOCUMENT_TOOL", "office_edit_document"]
