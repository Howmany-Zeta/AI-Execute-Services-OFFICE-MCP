"""office_read_pdf — fine/coarse PDF read."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_json_sidecar import read_sidecar_json
from aiecs.tools.office_tool.core.categories import assert_category_path, classify_file_ext, llm_coarse_output_type
from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.read_response import build_read_response
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.clients.documentai_client import (
    BATCH_MAX_PAGES,
    DocumentAIOnlineLimitError,
    get_documentai_client,
    online_max_bytes,
)
from aiecs.tools.office_tool.core.dai_batch import document_has_structure, process_pdf_batch
from aiecs.tools.office_tool.core.pdf_pages import estimate_pdf_pages
from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SourceTooLargeError,
    download_object_bytes,
    stat_object_size,
)
from aiecs.tools.office_tool.pdf.parser.document import (
    PDF_PAGE_EXTRACT_BODY,
    apply_page_range,
    parse_document_json,
    word_count_from_pages,
)
from aiecs.tools.office_tool.pdf.parser.document_ai import layout_to_pages
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

LAYOUT_LOCATOR_NOTE = (
    "Document AI layout is not an edit locator. "
    "Do not call office_edit_pdf from these units."
)

_READ_BATCH_TIMEOUT_SEC = 600.0


async def _pdf_builder_read(
    *,
    args,
    path_val: str,
    url_val: str,
    file_ext: str,
    storage_path: str,
    source_path_format: str,
    client: DocumentServerClient | None,
) -> dict[str, Any]:
    parsed, sidecar_err = await read_sidecar_json(
        path_val or None,
        url_val or None,
        file_ext,
        PDF_PAGE_EXTRACT_BODY,
        client=client,
    )
    if sidecar_err:
        return err(sidecar_err)
    pages = apply_page_range(parse_document_json(parsed or {}), args.options.page_range)
    title = ""
    if pages and pages[0].get("blocks"):
        title = str(pages[0]["blocks"][0].get("text") or "")[:200]
    if args.format == "text":
        return ok(text=pages_to_text(pages), source_path=storage_path or None, read_mode="fine")
    units = pages_to_outline(pages) if args.format == "outline" else pages
    extra: dict[str, Any] = {"conversion_output_type": "builder_json"}
    widgets_api = (parsed or {}).get("widgets_api_available", True)
    if args.options.include_form_fields and widgets_api is False:
        extra["_note"] = FORM_FIELDS_NOTE
    if not args.options.include_form_fields:
        for page in pages:
            page.pop("form_fields", None)
    if not args.options.include_annotations:
        for page in pages:
            page.pop("annotations", None)
    return build_read_response(
        category="pdf",
        title=title,
        units=units,
        read_mode="fine",
        locator_note=LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        word_count=word_count_from_pages(pages),
        extra=extra,
    )


def _layout_read_response(
    document: dict[str, Any],
    *,
    args,
    storage_path: str,
    source_path_format: str,
    document_ai_mode: str,
) -> dict[str, Any] | None:
    if not document_has_structure(document):
        return None
    pages = apply_page_range(layout_to_pages(document), args.options.page_range)
    if not pages:
        return None
    title = ""
    if pages[0].get("blocks"):
        title = str(pages[0]["blocks"][0].get("text") or "")[:200]
    if args.format == "text":
        return ok(text=pages_to_text(pages), source_path=storage_path or None, read_mode="layout")
    units = pages_to_outline(pages) if args.format == "outline" else pages
    return build_read_response(
        category="pdf",
        title=title,
        units=units,
        read_mode="layout",
        locator_note=LAYOUT_LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        word_count=word_count_from_pages(pages),
        extra={
            "parse_engine": "document_ai",
            "conversion_output_type": "document_layout",
            "document_ai_mode": document_ai_mode,
        },
    )


async def _read_pdf_document_ai(
    *,
    args,
    file_ext: str,
    fetch_url: str,
    storage_path: str,
    source_path_format: str,
    path_val: str,
    url_val: str,
    client: DocumentServerClient | None,
) -> dict[str, Any]:
    if file_ext.lower() != "pdf":
        return err("document_ai engine accepts .pdf only")
    from aiecs.config import get_documentai_config

    if not get_documentai_config().is_configured():
        return err("DOCUMENT_AI_PROJECT and DOCUMENT_AI_PROCESSOR_ID are required")
    max_bytes = online_max_bytes()
    data: bytes | None = None
    oversize = False
    try:
        if path_val.startswith("gs://") or path_val.startswith("s3://"):
            size = await stat_object_size(path_val)
            if size > max_bytes:
                oversize = True
            else:
                data = await download_object_bytes(path_val, max_bytes)
        else:
            import httpx

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
                resp = await http_client.get(fetch_url)
                resp.raise_for_status()
                data = resp.content
            if len(data) > max_bytes:
                oversize = True
    except SourceTooLargeError:
        oversize = True
    except Exception as e:
        return err(str(e))

    if oversize or data is None:
        return await _pdf_builder_read(
            args=args,
            path_val=path_val,
            url_val=url_val,
            file_ext=file_ext,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
        )

    pages_est = estimate_pdf_pages(data)
    if pages_est is not None and pages_est > BATCH_MAX_PAGES:
        return await _pdf_builder_read(
            args=args,
            path_val=path_val,
            url_val=url_val,
            file_ext=file_ext,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
        )

    page_indexes = None
    if args.options.page_range:
        start, end = args.options.page_range
        page_indexes = list(range(int(start), int(end) + 1))

    async def _batch() -> dict[str, Any]:
        return await process_pdf_batch(
            source_path=path_val,
            data=data,
            work_id=f"read-{uuid.uuid4().hex}",
            timeout_sec=_READ_BATCH_TIMEOUT_SEC,
        )

    async def _builder() -> dict[str, Any]:
        return await _pdf_builder_read(
            args=args,
            path_val=path_val,
            url_val=url_val,
            file_ext=file_ext,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
        )

    try:
        document = await get_documentai_client().process_pdf_online(
            raw_bytes=data,
            page_indexes=page_indexes,
        )
    except DocumentAIOnlineLimitError:
        try:
            document = await _batch()
        except Exception:
            logger.exception("office_read_pdf Document AI batch fallback failed")
            return await _builder()
        batched = _layout_read_response(
            document,
            args=args,
            storage_path=storage_path,
            source_path_format=source_path_format,
            document_ai_mode="batch",
        )
        return batched if batched is not None else await _builder()
    except Exception as e:
        return err(str(e))

    online = _layout_read_response(
        document,
        args=args,
        storage_path=storage_path,
        source_path_format=source_path_format,
        document_ai_mode="online",
    )
    if online is not None:
        return online
    try:
        document = await _batch()
    except Exception:
        logger.exception("office_read_pdf Document AI batch fallback failed")
        return await _builder()
    batched = _layout_read_response(
        document,
        args=args,
        storage_path=storage_path,
        source_path_format=source_path_format,
        document_ai_mode="batch",
    )
    return batched if batched is not None else await _builder()

COARSE_NOTE = (
    "Coarse txt read uses page boundaries (\\f or --- page N ---). Re-read fine before edit."
)

FORM_FIELDS_NOTE = (
    "Fine read form_fields require DocumentServer page.GetAllWidgets; omitted when API unavailable."
)

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[PDF] Read PDF structure (pdf). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url. "
        "Fine read uses Builder sidecar; coarse uses Conversion txt with page boundaries (ADR-020). "
        "options.engine=document_ai tries Document AI online, then batch, then Builder; "
        "form_fields need page.GetAllWidgets on DocumentServer. "
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
                    "engine": {"type": "string", "enum": ["documentserver", "document_ai"]},
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

    if args.options.engine == "document_ai":
        return await _read_pdf_document_ai(
            args=args,
            file_ext=file_ext,
            fetch_url=fetch_url,
            storage_path=storage_path,
            source_path_format=source_path_format,
            path_val=path_val,
            url_val=url_val,
            client=client,
        )

    read_mode = args.options.read_mode
    page_range = args.options.page_range
    include_form_fields = args.options.include_form_fields
    include_annotations = args.options.include_annotations

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
        if not include_annotations:
            for page in pages:
                page.pop("annotations", None)

        fine_extra: dict[str, Any] = {"conversion_output_type": "builder_json"}
        widgets_api = (parsed or {}).get("widgets_api_available", True)
        if include_form_fields and widgets_api is False:
            fine_extra["_note"] = FORM_FIELDS_NOTE

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
            extra=fine_extra,
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
