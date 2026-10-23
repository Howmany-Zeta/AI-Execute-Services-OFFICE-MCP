"""office_edit_word — declarative Word document editing."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import SIGNED_URL_EXPIRY_SECONDS, copy_source_to_backup
from aiecs.tools.office_tool.core.storage.paths import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.builder.edit import build_edit_script
from aiecs.tools.office_tool.word.schemas.edit_ops import EDIT_OPERATION_ITEM_SCHEMA, WordEditArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_edit_word"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Word] Edit Word document with declarative operations. "
        "Existing: search_replace, set_block_text, set_heading, insert_paragraph, insert_bullets "
        "(prefix only, not a Word list), insert_table, delete_block (not tables), apply_style, "
        "add_page_break, insert_section_break, insert_toc. "
        "Also: set_run_format (bold/italic/underline/font_name/font_size_pt), set_paragraph_format, "
        "set_list, set_cell_text, table row/column insert and delete, delete_table, "
        "set_header/set_footer (variant=default|first|even, optional page_number), insert_image/replace_image, "
        "set_hyperlink/remove_hyperlink, move_block, set_section, insert_footnote/set_footnote_text/delete_footnote, "
        "insert_comment/set_comment/delete_comment, insert_caption, insert_chart/set_chart_data, "
        "insert_textbox/set_textbox_geometry. "
        "set_block_text clears runs; format goes through set_run_format (including strike/highlight/font_color). "
        "search_replace is body paragraphs only. "
        "Use office_read_word fine read for locators. "
        "Do not pass office_read_document [Page N] or media URLs. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "output_path": {"type": "string"},
            "operations": {
                "type": "array",
                "items": EDIT_OPERATION_ITEM_SCHEMA,
                "minItems": 1,
            },
            "options": {"type": "object", "properties": {"backup": {"type": "boolean"}}},
        },
        "required": ["output_path", "operations"],
    },
}


async def office_edit_word(
    output_path: str,
    operations: list,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = WordEditArgs.model_validate(
            {
                "source_path": source_path,
                "source_url": source_url,
                "output_path": output_path,
                "operations": operations,
                "options": options or {},
                **kwargs,
            }
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()

    if path_val and args.options.backup:
        _, backup_err = await copy_source_to_backup(path_val)
        if backup_err:
            return err(backup_err)

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    body = build_edit_script(args.operations, file_ext=file_ext)
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_edit_word

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_edit_word"]
