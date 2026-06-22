"""office_apply_template_presentation — fill presentation template with data."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS, SIGNED_URL_EXPIRY_SECONDS
from aiecs.tools.office_tool.presentation.builder.template import build_template_script
from aiecs.tools.office_tool.presentation.schemas.edit_ops import PresentationTemplateArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_apply_template_presentation"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        f"[Presentation] Fill presentation template with {{key}} placeholders. "
        f"template_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or template_url. "
        "Supports global {{company_name}} and per-slide slide_1_title keys."
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


async def office_apply_template_presentation(
    data: dict,
    output_path: str,
    template_path: Optional[str] = None,
    template_url: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PresentationTemplateArgs.model_validate(
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


handler = office_apply_template_presentation

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_apply_template_presentation"]
