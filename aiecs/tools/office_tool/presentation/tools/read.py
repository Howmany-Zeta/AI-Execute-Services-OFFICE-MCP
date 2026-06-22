"""office_read_presentation — fine/coarse presentation read."""

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
from aiecs.tools.office_tool.presentation.parser.slides import (
    SLIDES_TOJSON_EXTRACT_BODY,
    apply_slide_range,
    parse_slides_json,
    slides_to_outline,
    slides_to_text,
    word_count_from_slides,
)
from aiecs.tools.office_tool.presentation.parser.txt import parse_txt_to_structure
from aiecs.tools.office_tool.presentation.schemas.read import PresentationReadArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_read_presentation"

LOCATOR_NOTE = (
    "Use slide_index and shape_index with office_edit_presentation. "
    "layout values for create/add_slide must match layouts[] exactly (ADR-016). "
    "Do not use office_read_document index."
)

COARSE_NOTE = (
    "Coarse txt read is for preview only — re-read with read_mode=fine before edit."
)

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Presentation] Read presentation structure (pptx, ppt, odp). "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) or source_url. "
        "Fine read uses Builder SlidesToJSON; coarse uses Conversion txt. "
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
                    "slide_range": {"type": "array", "items": {"type": "integer"}},
                    "include_notes": {"type": "boolean"},
                    "include_layout_meta": {"type": "boolean"},
                },
            },
        },
        "required": [],
    },
}


def _coarse_elements_to_slides(structure: dict[str, Any]) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for el in structure.get("elements") or []:
        slides.append(
            {
                "slide_index": el.get("index", len(slides)),
                "title": (el.get("text") or "")[:200],
                "layout": "",
                "shapes": [{"shape_index": 0, "type": "shape", "text": el.get("text", "")}],
            }
        )
    return slides


async def office_read_presentation(
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
        args = PresentationReadArgs.model_validate(raw)
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, storage_path, source_path_format = resolved
    if classify_file_ext(file_ext) != "presentation":
        cat_err = assert_category_path("presentation", f"file.{file_ext}")
        return err(cat_err or f"Not a presentation file: .{file_ext}")

    read_mode = args.options.read_mode
    slide_range = args.options.slide_range
    include_notes = args.options.include_notes

    if read_mode == "fine" and args.format in ("structured", "outline", "text"):
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None,
            url_val or None,
            file_ext,
            SLIDES_TOJSON_EXTRACT_BODY,
            client=client,
        )
        if sidecar_err:
            return err(sidecar_err)

        slides, layouts = parse_slides_json(parsed or {})
        slides = apply_slide_range(slides, slide_range)
        if not include_notes:
            for slide in slides:
                slide.pop("notes", None)

        title = slides[0].get("title", "") if slides else ""

        if args.format == "text":
            return ok(
                text=slides_to_text(slides),
                source_path=storage_path or None,
                read_mode="fine",
            )

        units = slides_to_outline(slides) if args.format == "outline" else slides
        extra: dict[str, Any] = {
            "layouts": layouts,
            "conversion_output_type": "builder_json",
        }
        if args.options.include_layout_meta:
            extra["layout_meta"] = [{"name": n} for n in layouts]

        return build_read_response(
            category="presentation",
            title=title,
            units=units,
            read_mode="fine",
            locator_note=LOCATOR_NOTE,
            source_path=storage_path or None,
            source_path_format=source_path_format,
            word_count=word_count_from_slides(slides),
            extra=extra,
        )

    output_type = llm_coarse_output_type(file_ext)
    content, fetch_error = await convert_and_fetch(fetch_url, file_ext, output_type, client=client)
    if fetch_error:
        return err(fetch_error)

    if args.format == "text":
        return ok(text=content, source_path=storage_path or None, read_mode="coarse")

    structure = parse_txt_to_structure(content)
    slides = _coarse_elements_to_slides(structure)
    slides = apply_slide_range(slides, slide_range)
    title = structure.get("title") or (slides[0].get("title", "") if slides else "")

    if args.format == "outline":
        units = slides_to_outline(slides)
    else:
        units = slides

    return build_read_response(
        category="presentation",
        title=title,
        units=units,
        read_mode="coarse",
        locator_note=LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        word_count=structure.get("word_count"),
        extra={
            "conversion_output_type": output_type,
            "_note": COARSE_NOTE,
        },
    )


handler = office_read_presentation

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_read_presentation"]
