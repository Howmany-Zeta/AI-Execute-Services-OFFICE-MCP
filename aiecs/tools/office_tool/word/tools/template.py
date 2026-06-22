"""office_apply_template_word — fill Word template with data."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS, SIGNED_URL_EXPIRY_SECONDS
from aiecs.tools.office_tool.word.builder.template import build_apply_template_script
from aiecs.tools.office_tool.word.schemas.section_spec import WordTemplateArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_apply_template_word"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        f"[Word] Fill Word template with {{key}} placeholders. template_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "or template_url."
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


async def office_apply_template_word(
    data: dict,
    output_path: str,
    template_path: Optional[str] = None,
    template_url: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = WordTemplateArgs.model_validate(
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
    script = build_apply_template_script(fetch_url, file_ext, args.data)
    return await run_builder_script(script, output_path=args.output_path, client=client)


handler = office_apply_template_word

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_apply_template_word"]
