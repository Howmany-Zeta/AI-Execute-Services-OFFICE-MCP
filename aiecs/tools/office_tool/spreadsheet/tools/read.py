"""office_read_spreadsheet — fine/coarse spreadsheet read."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_json_sidecar import read_sidecar_json
from aiecs.tools.office_tool.core.categories import assert_category_path, classify_file_ext, llm_coarse_output_type
from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.read_response import build_read_response
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.spreadsheet.parser.csv import csv_to_coarse_sheets
from aiecs.tools.office_tool.spreadsheet.parser.workbook import (
    WORKBOOK_SIDECAR_EXTRACT_BODY,
    apply_max_rows,
    filter_sheet_names,
    parse_workbook_json,
    sheets_to_outline,
    sheets_to_text,
)
from aiecs.tools.office_tool.spreadsheet.schemas.read import SpreadsheetReadArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_read_spreadsheet"

LOCATOR_NOTE = (
    "Edit with office_edit_spreadsheet using sheet_name or sheet_index + cell (A1) or range. "
    "Do not use office_read_document row index."
)

COARSE_NOTE = (
    "Coarse csv read may expose only the first sheet — re-read with read_mode=fine before multi-sheet edit."
)

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Spreadsheet] Read spreadsheet structure (xlsx, xls, ods). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url. "
        "Fine read uses Builder GetSheetsCount sidecar; coarse uses Conversion csv. "
        + LOCATOR_NOTE
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "format": {
                "type": "string",
                "enum": ["structured", "outline", "text"],
                "default": "structured",
            },
            "options": {
                "type": "object",
                "properties": {
                    "read_mode": {"type": "string", "enum": ["fine", "coarse"]},
                    "sheet_names": {"type": "array", "items": {"type": "string"}},
                    "max_rows": {"type": "integer", "minimum": 1},
                    "include_formulas": {"type": "boolean"},
                    "range": {"type": "string"},
                },
            },
        },
        "required": [],
    },
}


async def office_read_spreadsheet(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "structured",
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    raw = {
        "source_path": source_path,
        "source_url": source_url,
        "format": format,
        "options": options or {},
        **kwargs,
    }
    try:
        args = SpreadsheetReadArgs.model_validate(raw)
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, storage_path, source_path_format = resolved
    if classify_file_ext(file_ext) != "spreadsheet":
        cat_err = assert_category_path("spreadsheet", f"file.{file_ext}")
        return err(cat_err or f"Not a spreadsheet file: .{file_ext}")

    read_mode = args.options.read_mode

    if read_mode == "fine" and args.format in ("structured", "outline", "text"):
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None,
            url_val or None,
            file_ext,
            WORKBOOK_SIDECAR_EXTRACT_BODY,
            client=client,
        )
        if sidecar_err:
            return err(sidecar_err)

        sheets = parse_workbook_json(parsed or {})
        sheets = filter_sheet_names(sheets, args.options.sheet_names)
        sheets, truncated = apply_max_rows(sheets, args.options.max_rows)
        title = sheets[0].get("name", "") if sheets else ""

        if args.format == "text":
            return ok(text=sheets_to_text(sheets), source_path=storage_path or None, read_mode="fine")

        units = sheets_to_outline(sheets) if args.format == "outline" else sheets
        extra: dict[str, Any] = {"conversion_output_type": "builder_json"}
        if truncated:
            extra["_truncated"] = True

        return build_read_response(
            category="spreadsheet",
            title=title,
            units=units,
            read_mode="fine",
            locator_note=LOCATOR_NOTE,
            source_path=storage_path or None,
            source_path_format=source_path_format,
            extra=extra,
        )

    output_type = llm_coarse_output_type(file_ext)
    content, fetch_error = await convert_and_fetch(fetch_url, file_ext, output_type, client=client)
    if fetch_error:
        return err(fetch_error)

    if args.format == "text":
        return ok(text=content, source_path=storage_path or None, read_mode="coarse")

    sheets = csv_to_coarse_sheets(content)
    sheets = filter_sheet_names(sheets, args.options.sheet_names)
    sheets, truncated = apply_max_rows(sheets, args.options.max_rows)
    title = sheets[0].get("name", "") if sheets else ""

    if args.format == "outline":
        units = sheets_to_outline(sheets)
    else:
        units = sheets

    extra = {"conversion_output_type": output_type, "_note": COARSE_NOTE}
    if truncated:
        extra["_truncated"] = True

    return build_read_response(
        category="spreadsheet",
        title=title,
        units=units,
        read_mode="coarse",
        locator_note=LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        extra=extra,
    )


handler = office_read_spreadsheet

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_read_spreadsheet"]
