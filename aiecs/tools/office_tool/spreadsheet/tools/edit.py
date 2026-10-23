"""office_edit_spreadsheet — declarative spreadsheet editing."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.categories import assert_category_path
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import SIGNED_URL_EXPIRY_SECONDS, copy_source_to_backup
from aiecs.tools.office_tool.core.storage.paths import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.spreadsheet.builder.edit import build_edit_script
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import (
    EDIT_OPERATION_ITEM_SCHEMA,
    SpreadsheetEditArgs,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "office_edit_spreadsheet"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Spreadsheet] Edit spreadsheet with declarative operations. "
        "set_cell, set_range, clear_range, clear_format, set_cell_style, set_column_width, "
        "set_row_height, insert_rows, delete_rows, set_formula: sheet_index or sheet_name "
        "(omit = active sheet). sheet_name wins if both are set. "
        "delete_sheet requires sheet_index or sheet_name. "
        "rename_sheet requires sheet_name + new_name. "
        "add_sheet accepts name only. copy_sheet uses source sheet_index or sheet_name and optional new_name. "
        "add_sheet and copy_sheet do not return a new sheet_index. "
        "clear_range clears values and formulas only. clear_format resets the 16 cell style fields. "
        "set_cell_style writes those fields (omit keeps, null clears). "
        "rows[r][c] origin is the top-left of this sheet's used_range, not sheet A1. "
        "Use A1/range (ADR-015). "
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


async def office_edit_spreadsheet(
    output_path: str,
    operations: list,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = SpreadsheetEditArgs.model_validate(
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

    path_err = assert_category_path("spreadsheet", args.output_path)
    if path_err:
        return err(path_err)

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


handler = office_edit_spreadsheet

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_edit_spreadsheet"]
