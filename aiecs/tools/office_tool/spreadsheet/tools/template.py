"""office_apply_template_spreadsheet — fill spreadsheet template with data."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS, SIGNED_URL_EXPIRY_SECONDS
from aiecs.tools.office_tool.spreadsheet.builder.template import build_template_script
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import SpreadsheetTemplateArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_apply_template_spreadsheet"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        f"[Spreadsheet] Fill spreadsheet template. template_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "or template_url. Use explicit Sheet!A1 keys or {{key}} in used ranges (ADR-014)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "template_path": {"type": "string"},
            "template_url": {"type": "string"},
            "data": {"type": "object"},
            "output_path": {"type": "string"},
        },
        "required": ["data", "output_path"],
    },
}


async def office_apply_template_spreadsheet(
    data: dict,
    output_path: str,
    template_path: Optional[str] = None,
    template_url: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = SpreadsheetTemplateArgs.model_validate(
            {
                "data": data,
                "output_path": output_path,
                "template_path": template_path,
                "template_url": template_url,
                **kwargs,
            }
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.template_path or "").strip()
    url_val = (args.template_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    body = build_template_script(args.data, file_ext=file_ext)
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_apply_template_spreadsheet

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_apply_template_spreadsheet"]
