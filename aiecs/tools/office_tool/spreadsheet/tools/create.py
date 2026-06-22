"""office_create_spreadsheet — declarative spreadsheet creation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.categories import assert_category_path, builder_file_ext
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.spreadsheet.builder.create import build_create_script
from aiecs.tools.office_tool.spreadsheet.schemas.workbook_spec import SpreadsheetCreateArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_create_spreadsheet"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Spreadsheet] Create a spreadsheet from declarative sheets. "
        f"Output path ({ACCEPTED_SOURCE_PATH_FORMATS} or local). "
        "Each sheet: name + rows[][] data."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "sheets": {"type": "array", "items": {"type": "object"}},
            "output_path": {"type": "string"},
            "options": {"type": "object", "properties": {"default_col_width": {"type": "number"}}},
        },
        "required": ["sheets", "output_path"],
    },
}


async def office_create_spreadsheet(
    sheets: list,
    output_path: str,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = SpreadsheetCreateArgs.model_validate(
            {"sheets": sheets, "output_path": output_path, "options": options or {}, **kwargs}
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_err = assert_category_path("spreadsheet", args.output_path)
    if path_err:
        return err(path_err)

    output_ext = builder_file_ext(args.output_path)
    script = build_create_script(args.sheets, output_ext=output_ext, options=args.options)
    return await run_builder_script(script, output_path=args.output_path, client=client)


handler = office_create_spreadsheet

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_create_spreadsheet"]
