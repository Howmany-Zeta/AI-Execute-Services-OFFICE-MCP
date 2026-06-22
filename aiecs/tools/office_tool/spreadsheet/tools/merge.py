"""office_merge_spreadsheets — merge spreadsheet files."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import is_http_url
from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SIGNED_URL_EXPIRY_SECONDS,
    get_file_ext,
    resolve_fetch_url,
    validate_source_path,
)
from aiecs.tools.office_tool.spreadsheet.builder.merge import build_merge_script
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import SpreadsheetMergeArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_merge_spreadsheets"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        f"[Spreadsheet] Merge spreadsheets into one workbook. source_paths ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "or source_urls. Options: rename_conflicts (default true)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_paths": {"type": "array", "items": {"type": "string"}},
            "source_urls": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {"rename_conflicts": {"type": "boolean"}},
            },
        },
        "required": ["output_path"],
    },
}


async def office_merge_spreadsheets(
    output_path: str,
    source_paths: Optional[List[str]] = None,
    source_urls: Optional[List[str]] = None,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = SpreadsheetMergeArgs.model_validate(
            {
                "output_path": output_path,
                "source_paths": source_paths,
                "source_urls": source_urls,
                "options": options or {},
                **kwargs,
            }
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    paths = args.source_paths or []
    urls = args.source_urls or []
    sources = paths if paths else (urls or [])
    use_storage = bool(paths)

    for p in sources:
        if not p or not str(p).strip():
            return err("Each source must be non-empty")
        if use_storage:
            verr = validate_source_path(str(p))
            if verr:
                return err(f"Invalid source_path {p!r}: {verr}")
        elif not is_http_url(str(p)):
            return err(f"source_urls must be HTTP/HTTPS URLs: {p}")

    try:
        fetch_urls: List[str] = []
        file_exts: List[str] = []
        for item in sources:
            if use_storage:
                url = await resolve_fetch_url(item, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
                fetch_urls.append(url)
                file_exts.append(get_file_ext(item))
            else:
                fetch_urls.append(item)
                file_exts.append(get_file_ext(item))
    except Exception as e:
        return err(f"Failed to resolve sources: {e}")

    script = build_merge_script(
        fetch_urls,
        file_exts,
        output_path=args.output_path,
        rename_conflicts=args.options.rename_conflicts,
    )
    return await run_builder_script(script, output_path=args.output_path, client=client)


handler = office_merge_spreadsheets

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_merge_spreadsheets"]
