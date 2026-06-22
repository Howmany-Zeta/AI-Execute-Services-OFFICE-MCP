"""office_edit_presentation — declarative presentation editing."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import SIGNED_URL_EXPIRY_SECONDS, copy_storage_file, is_object_storage_path
from aiecs.tools.office_tool.core.storage.paths import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.presentation.builder.edit import build_edit_script
from aiecs.tools.office_tool.presentation.schemas.edit_ops import PresentationEditArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_edit_presentation"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Presentation] Edit presentation with declarative operations (set_title, set_bullets, "
        "add_slide, delete_slide, etc.). Use office_read_presentation fine read first for slide_index. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "output_path": {"type": "string"},
            "operations": {"type": "array", "items": {"type": "object"}},
            "options": {"type": "object", "properties": {"backup": {"type": "boolean"}}},
        },
        "required": ["output_path", "operations"],
    },
}


async def office_edit_presentation(
    output_path: str,
    operations: list,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PresentationEditArgs.model_validate(
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
        if not is_object_storage_path(path_val):
            return err("options.backup requires source_path (gs:// or s3://)")
        try:
            await copy_storage_file(path_val, path_val + ".backup")
        except Exception as e:
            logger.exception("Backup failed")
            return err(f"Backup failed: {e}")

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    body = build_edit_script(args.operations, file_ext=file_ext)
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_edit_presentation

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_edit_presentation"]
