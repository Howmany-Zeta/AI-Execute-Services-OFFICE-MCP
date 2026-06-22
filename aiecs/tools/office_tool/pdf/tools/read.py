"""office_read_pdf — fine/coarse PDF read."""

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
from aiecs.tools.office_tool.pdf.parser.document import (
    PDF_PAGE_EXTRACT_BODY,
    apply_page_range,
    parse_document_json,
    word_count_from_pages,
)
from aiecs.tools.office_tool.pdf.parser.pages_txt import (
    pages_to_outline,
    pages_to_text,
    parse_txt_to_pages,
)
from aiecs.tools.office_tool.pdf.schemas.read import PdfReadArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_read_pdf"

LOCATOR_NOTE = (
    "Edit with office_edit_pdf using page_index and block_index. "
    "Form fields: use office_fill_pdf_form. Do not use office_read_document index."
)

COARSE_NOTE = (
    "Coarse txt read uses page boundaries (\\f or --- page N ---). Re-read fine before edit."
)

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[PDF] Read PDF structure (pdf). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url. "
        "Fine read uses Builder sidecar; coarse uses Conversion txt with page boundaries (ADR-020). "
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
                    "page_range": {"type": "array", "items": {"type": "integer"}},
                    "include_form_fields": {"type": "boolean"},
                    "include_annotations": {"type": "boolean"},
                },
            },
        },
        "required": [],
    },
}


async def office_read_pdf(
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
        args = PdfReadArgs.model_validate(raw)
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, storage_path, source_path_format = resolved
    if classify_file_ext(file_ext) != "pdf":
        cat_err = assert_category_path("pdf", f"file.{file_ext}")
        return err(cat_err or f"Not a PDF file: .{file_ext}")

    read_mode = args.options.read_mode
    page_range = args.options.page_range
    include_form_fields = args.options.include_form_fields

    if read_mode == "fine" and args.format in ("structured", "outline", "text"):
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None,
            url_val or None,
            file_ext,
            PDF_PAGE_EXTRACT_BODY,
            client=client,
        )
        if sidecar_err:
            return err(sidecar_err)

        pages = parse_document_json(parsed or {})
        pages = apply_page_range(pages, page_range)
        if not include_form_fields:
            for page in pages:
                page.pop("form_fields", None)

        title = ""
        if pages and pages[0].get("blocks"):
            title = pages[0]["blocks"][0].get("text", "")[:200]

        if args.format == "text":
            return ok(text=pages_to_text(pages), source_path=storage_path or None, read_mode="fine")

        units = pages_to_outline(pages) if args.format == "outline" else pages
        return build_read_response(
            category="pdf",
            title=title,
            units=units,
            read_mode="fine",
            locator_note=LOCATOR_NOTE,
            source_path=storage_path or None,
            source_path_format=source_path_format,
            word_count=word_count_from_pages(pages),
            extra={"conversion_output_type": "builder_json"},
        )

    output_type = llm_coarse_output_type(file_ext)
    content, fetch_error = await convert_and_fetch(fetch_url, file_ext, output_type, client=client)
    if fetch_error:
        return err(fetch_error)

    if args.format == "text":
        return ok(text=content, source_path=storage_path or None, read_mode="coarse")

    pages, boundary_note = parse_txt_to_pages(content)
    pages = apply_page_range(pages, page_range)
    title = ""
    if pages and pages[0].get("blocks"):
        title = pages[0]["blocks"][0].get("text", "")[:200]

    if args.format == "outline":
        units = pages_to_outline(pages)
    else:
        units = pages

    extra: dict[str, Any] = {"conversion_output_type": output_type, "_note": COARSE_NOTE}
    if boundary_note:
        extra["_note"] = boundary_note

    return build_read_response(
        category="pdf",
        title=title,
        units=units,
        read_mode="coarse",
        locator_note=LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        word_count=word_count_from_pages(pages),
        extra=extra,
    )


handler = office_read_pdf

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_read_pdf"]
