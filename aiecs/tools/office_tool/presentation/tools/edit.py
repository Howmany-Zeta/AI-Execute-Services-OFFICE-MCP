"""office_edit_presentation — declarative presentation editing."""

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
from aiecs.tools.office_tool.presentation.builder.edit import build_edit_script
from aiecs.tools.office_tool.presentation.schemas.edit_ops import (
    PRESENTATION_EDIT_INPUT_SCHEMA,
    PresentationEditArgs,
)
from aiecs.tools.office_tool.presentation.schemas.slide_spec import validate_add_slide_layouts

logger = logging.getLogger(__name__)

TOOL_NAME = "office_edit_presentation"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Presentation] Edit presentation with declarative operations (set_title, set_bullets, "
        "add_slide, delete_slide, etc.). Use office_read_presentation fine read first for slide_index. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url."
    ),
    "inputSchema": PRESENTATION_EDIT_INPUT_SCHEMA,
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

    layout_err = validate_add_slide_layouts(args.operations, args.options.allowed_layouts)
    if layout_err:
        return err(layout_err)

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
    try:
        body = build_edit_script(args.operations, file_ext=file_ext)
    except ValueError as e:
        return err(str(e))
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_edit_presentation

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_edit_presentation"]
