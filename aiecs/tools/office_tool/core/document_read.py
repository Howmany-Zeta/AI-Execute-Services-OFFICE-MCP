"""office_read_document reading-line orchestrator (ADR-049)."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import zipfile
from typing import Any, Optional

import httpx

from aiecs.config import get_office_read_config
from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_json_sidecar import read_sidecar_json
from aiecs.tools.office_tool.core.caller_io import decode_inline_file
from aiecs.tools.office_tool.core.categories import (
    STRUCTURED_BUILDER_PRESENTATION_EXTS,
    STRUCTURED_BUILDER_WORD_EXTS,
    STRUCTURED_DOCUMENT_AI_EXTS,
    SPREADSHEET_EXTENSIONS,
    llm_coarse_output_type,
)
from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch
from aiecs.tools.office_tool.core.coarse_parsers import (
    parse_csv_to_structure,
    parse_html_to_structure,
    parse_txt_to_structure,
)
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.read_markdown import (
    READ_NOTE,
    MdBlock,
    MdPage,
    apply_page_slice,
    assemble_markdown,
    conversion_elements_to_pages,
    element_to_block,
    markdown_to_plain,
    sheet_pages,
    title_from_pages,
    truncate_output,
    word_elements_to_pages,
)
from aiecs.tools.office_tool.core.read_media import (
    collect_package_media,
    public_media,
    realize_media,
)
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SourceTooLargeError,
    download_object_bytes,
    stat_object_size,
)
from aiecs.tools.office_tool.core.structured_read import read_pdf_markdown
from aiecs.tools.office_tool.core.text_sanitize import has_visible_text
from aiecs.tools.office_tool.presentation.parser.structured import (
    STRUCTURED_PRESENTATION_EXTRACT_BODY,
    flatten_shapes,
    shape_kind,
    _element_type_fields,
    _shape_text,
)
from aiecs.tools.office_tool.spreadsheet.parser.workbook import (
    parse_workbook_json,
    workbook_sidecar_extract_body,
)
from aiecs.tools.office_tool.word.parser.structured import (
    STRUCTURED_WORD_EXTRACT_BODY,
    normalize_word_structured,
    word_title_from_elements,
)

logger = logging.getLogger(__name__)

FORMATS = frozenset({"markdown", "plain", "outline"})
ACCEPTS = frozenset({
    "application/json",
    "text/markdown",
    "text/plain",
    "application/zip",
})
DELIVERIES = frozenset({"fetch_token", "caller_bucket"})
PAGE_RANGE_ERR = (
    "Document exceeds the synchronous read limit. "
    "Pass options.page_range to continue with office_read_document."
)
MEDIA_EXTS = frozenset({"docx", "docm", "dotx", "pptx", "pptm", "ppsx", "xlsx", "xlsm", "odt", "odp"})


def _parse_page_range(raw: Any) -> tuple[int, int] | None | dict[str, Any]:
    if raw in (None, "", []):
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return err("options.page_range must be [start, end] with 1-based inclusive pages")
    try:
        start, end = int(raw[0]), int(raw[1])
    except (TypeError, ValueError):
        return err("options.page_range must be [start, end] with 1-based inclusive pages")
    if start < 1 or end < start:
        return err("options.page_range must be [start, end] with 1-based inclusive pages")
    return start, end


def _parse_options(options: dict | None) -> dict[str, Any] | dict:
    opts = options or {}
    if not isinstance(opts, dict):
        return err("options must be an object")
    accept = str(opts.get("accept") or "application/json").strip()
    if accept not in ACCEPTS:
        return err("accept must be application/json, text/markdown, text/plain, or application/zip")
    delivery = str(opts.get("media_delivery") or "fetch_token").strip()
    if delivery not in DELIVERIES:
        return err("media_delivery must be fetch_token or caller_bucket")
    media_output_path = (opts.get("media_output_path") or "").strip() or None
    if delivery == "caller_bucket":
        if not media_output_path or not (
            media_output_path.startswith("s3://") or media_output_path.startswith("gs://")
        ):
            return err("caller_bucket requires options.media_output_path as an s3:// or gs:// directory")
    page_range = _parse_page_range(opts.get("page_range"))
    if isinstance(page_range, dict):
        return page_range
    return {
        "accept": accept,
        "media_delivery": delivery,
        "media_output_path": media_output_path,
        "page_range": page_range,
    }


async def _source_size(storage_path: str, inline: bytes | None) -> int | None:
    if inline is not None:
        return len(inline)
    if storage_path.startswith("gs://") or storage_path.startswith("s3://"):
        try:
            return await stat_object_size(storage_path)
        except Exception:
            return None
    return None


async def _load_bytes(
    storage_path: str,
    fetch_url: str,
    inline: bytes | None,
    max_bytes: int,
) -> bytes | None:
    if inline is not None:
        return inline
    try:
        if storage_path.startswith("gs://") or storage_path.startswith("s3://"):
            return await download_object_bytes(storage_path, max_bytes)
        if fetch_url:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(fetch_url)
                response.raise_for_status()
                return response.content
    except SourceTooLargeError:
        return None
    except Exception:
        logger.exception("Failed to load source bytes")
        return None
    return None


def _presentation_pages(raw: dict[str, Any]) -> list[MdPage]:
    slides = raw.get("slides") if isinstance(raw, dict) else None
    if not isinstance(slides, list):
        return [MdPage(page=1, blocks=[])]
    pages: list[MdPage] = []
    for raw_slide in slides:
        if not isinstance(raw_slide, dict):
            continue
        try:
            page_no = int(raw_slide.get("slide_index") or (len(pages) + 1))
        except (TypeError, ValueError):
            page_no = len(pages) + 1
        blocks = []
        for shape in flatten_shapes(raw_slide.get("shapes") or []):
            kind = shape_kind(shape)
            text = _shape_text(shape, kind)
            if kind == "picture":
                alt = sanitize_visible(text) or "image"
                block = element_to_block({"type": "image", "alt": alt, "text": alt})
                if block:
                    blocks.append(block)
                continue
            if kind == "other" and (shape.get("is_table") or str(shape.get("class_type") or "") == "table"):
                rows = shape.get("rows")
                if isinstance(rows, list) and rows:
                    block = element_to_block({"type": "table", "rows": rows})
                    if block:
                        blocks.append(block)
                    continue
            if not has_visible_text(text):
                continue
            fields = _element_type_fields(shape)
            block = element_to_block({**fields, "text": text, "runs": shape.get("runs")})
            if block:
                blocks.append(block)
        pages.append(MdPage(page=page_no, blocks=blocks))
    return pages or [MdPage(page=1, blocks=[])]


def sanitize_visible(text: str | None) -> str:
    from aiecs.tools.office_tool.core.text_sanitize import sanitize_text

    return sanitize_text(text, trim_edges=True)


def _media_target(item) -> str | None:
    return item.name if getattr(item, "staged", True) else None


def _attach_media(pages: list[MdPage], items) -> None:
    queue = list(items)
    for page in pages:
        for block in page.blocks:
            if block.type != "image":
                continue
            if not queue:
                block.media_name = None
                continue
            item = queue.pop(0)
            block.media_name = _media_target(item)
            block.alt = block.alt or item.alt
        leftover = [item for item in list(queue) if item.page == page.page]
        for item in leftover:
            page.blocks.append(MdBlock(type="image", alt=item.alt, media_name=_media_target(item)))
            queue.remove(item)
    if queue and pages:
        for item in queue:
            pages[-1].blocks.append(MdBlock(type="image", alt=item.alt, media_name=_media_target(item)))


def _apply_skipped_media(pages: list[MdPage], candidates) -> None:
    fail_alts = [
        sanitize_visible(c.alt) or c.kind
        for c in candidates
        if getattr(c, "skipped_reason", None) == "convert_fail"
    ]
    overflow_alts = [
        sanitize_visible(c.alt) or c.kind
        for c in candidates
        if getattr(c, "skipped_reason", None) == "overflow"
    ]
    unpaired = 0
    if fail_alts:
        for page in pages:
            rewritten: list[MdBlock] = []
            for block in page.blocks:
                if block.type == "image" and not block.media_name and fail_alts:
                    rewritten.append(MdBlock(type="paragraph", text=fail_alts.pop(0)))
                else:
                    rewritten.append(block)
            page.blocks = rewritten
        if fail_alts and pages:
            for alt in fail_alts:
                pages[-1].blocks.append(MdBlock(type="paragraph", text=alt))
    for page in pages:
        unpaired += sum(1 for block in page.blocks if block.type == "image" and not block.media_name)
    extras = overflow_alts[unpaired:]
    if extras and pages:
        for alt in extras:
            pages[-1].blocks.append(MdBlock(type="image", alt=alt, media_name=None))


async def read_document_markdown(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    format: str = "markdown",
    client: Optional[DocumentServerClient] = None,
    content_base64: Optional[str] = None,
    source_bytes: Optional[str] = None,
    filename: Optional[str] = None,
    options: Optional[dict] = None,
) -> dict[str, Any] | str:
    fmt = (format or "markdown").strip()
    if fmt not in FORMATS:
        return err("format must be markdown, plain, or outline")
    parsed_opts = _parse_options(options)
    if parsed_opts.get("isError"):
        return parsed_opts
    accept = parsed_opts["accept"]
    if accept == "text/markdown" and fmt not in {"markdown", "outline"}:
        return err("accept=text/markdown requires format=markdown or outline")

    cfg = get_office_read_config()
    path_val = (source_path or "").strip()
    url_val = (source_url or "").strip()
    inline, decode_err = decode_inline_file(content_base64, source_bytes)
    if decode_err:
        return err(decode_err)

    resolved = await resolve_document_source(
        path_val,
        url_val,
        content_base64=content_base64,
        source_bytes=source_bytes,
        filename=filename,
    )
    if isinstance(resolved, dict):
        return resolved
    fetch_url, file_ext, storage_path, source_path_format = resolved
    ext = (file_ext or "").lower().lstrip(".")

    size = await _source_size(storage_path, inline)
    if size is not None and size > cfg.max_source_bytes and not parsed_opts["page_range"]:
        return err(PAGE_RANGE_ERR)

    need_bytes = ext in STRUCTURED_DOCUMENT_AI_EXTS or ext in MEDIA_EXTS
    data = inline
    if need_bytes and data is None:
        data = await _load_bytes(storage_path, fetch_url, inline, max(cfg.max_source_bytes, size or 0, 100 * 1024 * 1024))

    warnings: list[str] = []
    conversion_output_type = ""
    pages: list[MdPage] = []
    title = ""

    if ext in STRUCTURED_BUILDER_WORD_EXTS:
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None, url_val or None, ext, STRUCTURED_WORD_EXTRACT_BODY,
            client=client, fetch_url=fetch_url,
        )
        if sidecar_err:
            return err(sidecar_err)
        elements = normalize_word_structured(parsed or {}).get("elements") or []
        pages = word_elements_to_pages(elements)
        conversion_output_type = "builder_json"
        title = word_title_from_elements(elements)
    elif ext in STRUCTURED_BUILDER_PRESENTATION_EXTS:
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None, url_val or None, ext, STRUCTURED_PRESENTATION_EXTRACT_BODY,
            client=client, fetch_url=fetch_url,
        )
        if sidecar_err:
            return err(sidecar_err)
        pages = _presentation_pages(parsed or {})
        conversion_output_type = "builder_json"
        title = title_from_pages(pages)
    elif ext in SPREADSHEET_EXTENSIONS and ext not in {"csv", "tsv"}:
        body = workbook_sidecar_extract_body(
            include_formulas=False,
            max_rows=cfg.max_sheet_rows,
            max_cols=cfg.max_sheet_cols,
            max_output_bytes=cfg.max_output_bytes,
        )
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None, url_val or None, ext, body,
            client=client, fetch_url=fetch_url,
        )
        if sidecar_err:
            return err(sidecar_err)
        sheets = parse_workbook_json(parsed or {})
        for sheet in sheets:
            limit = sheet.get("truncated")
            if limit:
                warnings.append(f"sheet {sheet.get('name')} truncated ({limit})")
        pages = sheet_pages(sheets)
        conversion_output_type = "builder_json"
        title = sheets[0]["name"] if sheets else ""
    elif ext in STRUCTURED_DOCUMENT_AI_EXTS:
        if data is None:
            return err("Failed to load PDF bytes")
        pdf_result = await read_pdf_markdown(
            source_path=path_val or None,
            source_url=url_val or None,
            file_ext=ext,
            fetch_url=fetch_url,
            client=client,
            data=data,
            page_range=parsed_opts["page_range"],
            max_pages=cfg.max_pages,
        )
        if isinstance(pdf_result, dict):
            return pdf_result
        pages = pdf_result
        conversion_output_type = "builder_json"
        title = title_from_pages(pages)
    else:
        output_type = llm_coarse_output_type(ext)
        content, fetch_error = await convert_and_fetch(fetch_url, ext, output_type, client=client)
        if fetch_error:
            return err(fetch_error)
        conversion_output_type = output_type
        if output_type == "html":
            structure = parse_html_to_structure(content)
            pages = conversion_elements_to_pages(structure.get("elements") or [])
            title = structure.get("title") or title_from_pages(pages)
        elif output_type == "csv":
            structure = parse_csv_to_structure(content)
            pages = sheet_pages([{
                "name": structure.get("title") or "Sheet1",
                "rows": [el.get("cells") or [] for el in structure.get("elements") or []],
            }])
            title = structure.get("title") or ""
        else:
            structure = parse_txt_to_structure(content)
            pages = conversion_elements_to_pages(structure.get("elements") or [])
            title = structure.get("title") or title_from_pages(pages)

    if ext not in STRUCTURED_DOCUMENT_AI_EXTS:
        if parsed_opts["page_range"]:
            pages = apply_page_slice(pages, parsed_opts["page_range"])
        elif sum(1 for p in pages if p.page is not None) > cfg.max_pages:
            return err(PAGE_RANGE_ERR)

    media_items = []
    if data and ext in MEDIA_EXTS:
        candidates = collect_package_media(data, ext)
        stable = hashlib.sha256(data).hexdigest()[:4]
        media_items, media_warnings = await realize_media(
            candidates,
            stable_id=stable,
            cfg=cfg,
            delivery=parsed_opts["media_delivery"],
            media_output_path=parsed_opts["media_output_path"],
            client=client,
        )
        warnings.extend(media_warnings)
        _attach_media(pages, media_items)
        _apply_skipped_media(pages, candidates)

    markdown = assemble_markdown(pages, "outline" if fmt == "outline" else "markdown")
    markdown, truncated = truncate_output(markdown, cfg.max_output_bytes)
    if truncated:
        warnings.append("output truncated to OFFICE_READ_MAX_OUTPUT_BYTES")

    page_count = len([p for p in pages if p.show_marker and p.page is not None]) or len(pages)
    media_public = public_media(media_items)
    meta = {
        "source_path_format": source_path_format,
        "accepted_source_path_formats": ACCEPTED_SOURCE_PATH_FORMATS,
        "conversion_output_type": conversion_output_type,
        "_note": READ_NOTE,
    }
    if storage_path:
        meta["source_path"] = storage_path

    if accept == "text/markdown":
        return markdown
    if accept == "text/plain":
        return markdown_to_plain(markdown) if fmt != "plain" else markdown_to_plain(markdown)
    if accept == "application/zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("document.md", markdown)
            for item in media_items:
                zf.writestr(f"media/{item.name}", item.data)
        return ok(
            content_base64=base64.b64encode(buf.getvalue()).decode("ascii"),
            content_type="application/zip",
            **meta,
        )

    body_key = "text" if fmt == "plain" else "markdown"
    body = markdown_to_plain(markdown) if fmt == "plain" else markdown
    payload: dict[str, Any] = {
        "title": title or title_from_pages(pages),
        body_key: body,
        "page_count": page_count,
        "media": media_public,
        **meta,
    }
    csv_pages = [
        {"page": p.page, "name": p.name, "csv": p.csv or ""}
        for p in pages
        if p.csv is not None
    ]
    if csv_pages:
        payload["pages"] = csv_pages
    if warnings:
        payload["_warnings"] = warnings
    return ok(**payload)
