"""office_fill_pdf_form — fill PDF AcroForm fields (ADR-019)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS, SIGNED_URL_EXPIRY_SECONDS
from aiecs.tools.office_tool.pdf.builder.fill_form import build_fill_form_script
from aiecs.tools.office_tool.pdf.schemas.fill_form import PdfFillFormArgs
from aiecs.tools.office_tool.pdf.validation import validate_pdf_output_path, validate_pdf_source_ext

logger = logging.getLogger(__name__)

TOOL_NAME = "office_fill_pdf_form"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        f"[PDF] Fill PDF AcroForm fields by name (SetValue per field, ADR-019). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url. "
        "No office_apply_template_pdf — use field names from office_read_pdf form_fields."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "data": {"type": "object"},
            "output_path": {"type": "string"},
        },
        "required": ["data", "output_path"],
    },
}


async def office_fill_pdf_form(
    data: dict,
    output_path: str,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PdfFillFormArgs.model_validate(
            {
                "data": data,
                "output_path": output_path,
                "source_path": source_path,
                "source_url": source_url,
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

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    src_err = validate_pdf_source_ext(file_ext)
    if src_err:
        return src_err
    body = build_fill_form_script(args.data, file_ext=file_ext)
    return await run_builder_on_source(fetch_url, file_ext, body, args.output_path, client=client)


handler = office_fill_pdf_form

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_fill_pdf_form"]
