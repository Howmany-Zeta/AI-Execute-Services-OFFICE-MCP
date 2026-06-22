"""office_create_pdf — declarative PDF creation (ADR-017)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.categories import assert_category_path, builder_file_ext
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.pdf.builder.create import build_create_script
from aiecs.tools.office_tool.pdf.schemas.page_spec import PdfCreateArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_create_pdf"

VIA_DOCX_HINT = " Try create_mode=via_docx explicitly."

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[PDF] Create a PDF from declarative pages/blocks. "
        f"Output path ({ACCEPTED_SOURCE_PATH_FORMATS} or local). "
        "create_mode: native (default) or via_docx — no automatic fallback (ADR-017)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "pages": {"type": "array", "items": {"type": "object"}},
            "output_path": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {
                    "page_size": {"type": "string", "enum": ["A4", "Letter"]},
                    "create_mode": {"type": "string", "enum": ["native", "via_docx"]},
                },
            },
        },
        "required": ["pages", "output_path"],
    },
}


async def office_create_pdf(
    pages: list,
    output_path: str,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PdfCreateArgs.model_validate(
            {"pages": pages, "output_path": output_path, "options": options or {}, **kwargs}
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_err = assert_category_path("pdf", args.output_path)
    if path_err:
        return err(path_err)

    output_ext = builder_file_ext(args.output_path)
    script = build_create_script(args.pages, output_ext=output_ext, options=args.options)
    result = await run_builder_script(script, output_path=args.output_path, client=client)

    if result.get("isError") and args.options.create_mode == "native":
        text = result.get("text", "")
        if VIA_DOCX_HINT.strip() not in text:
            result = dict(result)
            result["text"] = text + VIA_DOCX_HINT
    return result


handler = office_create_pdf

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_create_pdf"]
