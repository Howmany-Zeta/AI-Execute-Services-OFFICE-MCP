"""office_read_word — fine/coarse Word document read."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_json_sidecar import read_sidecar_json
from aiecs.tools.office_tool.core.categories import assert_category_path, llm_coarse_output_type
from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch
from aiecs.tools.office_tool.core.caller_io import INLINE_SOURCE_PROPERTIES, SOURCE_PATH_INTERNAL, caller_source_kwargs
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.read_response import build_read_response
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.text_sanitize import sanitize_text
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.parser.document import (
    blocks_to_outline,
    blocks_to_text,
    word_count_from_blocks,
)
from aiecs.tools.office_tool.word.parser.fine import WORD_TOJSON_EXTRACT_BODY, parse_fine_sidecar
from aiecs.tools.office_tool.word.parser.html import parse_html_to_structure
from aiecs.tools.office_tool.word.schemas.read import WordReadArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_read_word"

LOCATOR_NOTE = (
    "Edit with office_edit_word using block_index, heading_path, match_text, "
    "run_index, row/col, or section_index. "
    "Header and footer ops use section_index and variant=default|first|even. "
    "search_replace is body paragraphs only — not headers, footers, footnotes, comments, or text boxes. "
    "Do not pass office_read_document [Page N], media URLs, or index."
)

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Word] Read Word document structure (docx, odt, doc). "
        "source_url or content_base64. "
        f"source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) is internal compatibility only. "
        "Fine read uses Builder ToJSON; coarse uses Conversion html. "
        + LOCATOR_NOTE
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string", "description": SOURCE_PATH_INTERNAL},
            "source_url": {"type": "string"},
            **INLINE_SOURCE_PROPERTIES,
            "format": {
                "type": "string",
                "enum": ["structured", "outline", "text"],
                "default": "structured",
            },
            "options": {
                "type": "object",
                "properties": {
                    "read_mode": {"type": "string", "enum": ["fine", "coarse"]},
                    "include_tables": {"type": "boolean"},
                    "max_blocks": {"type": "integer", "minimum": 1},
                },
            },
        },
        "required": [],
    },
}

handler = None  # set after function definition


def _coarse_html_to_blocks(html: str, include_tables: bool) -> list[dict]:
    structure = parse_html_to_structure(html)
    blocks: list[dict] = []
    for el in structure.get("elements") or []:
        etype = el.get("type", "paragraph")
        if etype == "table" and not include_tables:
            continue
        block: dict[str, Any] = {
            "block_index": len(blocks),
            "type": etype if etype != "row" else "paragraph",
            "text": el.get("text", ""),
        }
        if etype.startswith("heading"):
            block["heading_path"] = [el.get("text", "")]
        if etype == "table":
            block["row_count"] = el.get("rows", 0)
            block["col_count"] = el.get("cols", 0)
        blocks.append(block)
    return blocks


async def office_read_word(
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
        args = WordReadArgs.model_validate(raw)
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val, **caller_source_kwargs(args))
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, storage_path, source_path_format = resolved
    cat_err = assert_category_path("word", f"file.{file_ext}")
    if cat_err:
        from aiecs.tools.office_tool.core.categories import classify_file_ext

        if classify_file_ext(file_ext) != "word":
            return err(cat_err)

    read_mode = args.options.read_mode
    include_tables = args.options.include_tables
    max_blocks = args.options.max_blocks

    if read_mode == "fine" and args.format in ("structured", "outline", "text"):
        parsed, sidecar_err = await read_sidecar_json(
            path_val or None,
            url_val or None,
            file_ext,
            WORD_TOJSON_EXTRACT_BODY,
            client=client,
            fetch_url=fetch_url,
        )
        if sidecar_err:
            return err(sidecar_err)
        blocks, sections, warnings, extras = parse_fine_sidecar(parsed or {})
        if not include_tables:
            blocks = [b for b in blocks if b.get("type") != "table"]
        truncated = False
        if max_blocks is not None and len(blocks) > max_blocks:
            blocks = blocks[:max_blocks]
            truncated = True
        title = blocks[0].get("text", "") if blocks else ""
        if args.format == "text":
            return ok(
                text=blocks_to_text(blocks),
                source_path=storage_path or None,
                read_mode="fine",
            )
        if args.format == "outline":
            units = blocks_to_outline(blocks)
        else:
            units = blocks
        extra: dict[str, Any] = {"conversion_output_type": "builder_json"}
        if truncated:
            extra["_truncated"] = True
        if args.format == "structured":
            extra["sections"] = sections
            for key in ("footnotes", "endnotes", "comments"):
                if extras.get(key):
                    extra[key] = extras[key]
            if warnings:
                extra["_warnings"] = warnings
        resp = build_read_response(
            category="word",
            title=title,
            units=units,
            read_mode="fine",
            locator_note=LOCATOR_NOTE,
            source_path=storage_path or None,
            source_path_format=source_path_format,
            word_count=word_count_from_blocks(blocks),
            extra=extra,
        )
        return resp

    output_type = llm_coarse_output_type(file_ext)
    content, fetch_error = await convert_and_fetch(fetch_url, file_ext, output_type, client=client)
    if fetch_error:
        return err(fetch_error)

    if args.format == "text":
        from aiecs.tools.office_tool.word.parser.html import extract_plain_text

        text = extract_plain_text(content) if output_type == "html" else content
        return ok(text=sanitize_text(text, trim_edges=True), source_path=storage_path or None, read_mode="coarse")

    blocks = _coarse_html_to_blocks(content, include_tables) if output_type == "html" else [
        {"block_index": 0, "type": "paragraph", "text": sanitize_text(content[:5000], trim_edges=True)}
    ]
    if max_blocks is not None:
        blocks = blocks[:max_blocks]
    if args.format == "outline":
        units = blocks_to_outline(blocks)
    else:
        units = blocks
    title = blocks[0].get("text", "") if blocks else ""
    return build_read_response(
        category="word",
        title=title,
        units=units,
        read_mode="coarse",
        locator_note=LOCATOR_NOTE,
        source_path=storage_path or None,
        source_path_format=source_path_format,
        word_count=word_count_from_blocks(blocks),
        extra={"conversion_output_type": output_type},
    )


handler = office_read_word

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_read_word"]
