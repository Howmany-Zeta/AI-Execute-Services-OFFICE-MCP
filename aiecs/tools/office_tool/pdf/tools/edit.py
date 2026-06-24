"""office_edit_pdf — declarative PDF editing."""

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
from aiecs.tools.office_tool.pdf.builder.edit import build_edit_script
from aiecs.tools.office_tool.pdf.schemas.edit_ops import EDIT_OPERATION_ITEM_SCHEMA, PdfEditArgs
from aiecs.tools.office_tool.pdf.validation import validate_pdf_output_path, validate_pdf_source_ext

logger = logging.getLogger(__name__)

TOOL_NAME = "office_edit_pdf"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[PDF] Edit PDF with declarative operations (add_paragraph, delete_page, rotate_page, etc.). "
        "Form filling is office_fill_pdf_form only (ADR-030). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "output_path": {"type": "string"},
            "operations": {"type": "array", "minItems": 1, "items": EDIT_OPERATION_ITEM_SCHEMA},
            "options": {"type": "object", "properties": {"backup": {"type": "boolean"}}},
        },
        "required": ["output_path", "operations"],
    },
}


async def office_edit_pdf(
    output_path: str,
    operations: list,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PdfEditArgs.model_validate(
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

    out_err = validate_pdf_output_path(args.output_path)
    if out_err:
        return out_err

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
    src_err = validate_pdf_source_ext(file_ext)
    if src_err:
        return src_err
    body = build_edit_script(args.operations, file_ext=file_ext)
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_edit_pdf

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_edit_pdf"]
