"""Coarse Conversion txt → pages[] for office_read_pdf (ADR-020)."""

from __future__ import annotations

import re
from typing import Any


def _blocks_from_text(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines()):
        line = line.strip()
        if line:
            blocks.append({"block_index": len(blocks), "type": "paragraph", "text": line})
    if not blocks and text.strip():
        blocks.append({"block_index": 0, "type": "paragraph", "text": text.strip()})
    return blocks


def parse_txt_to_pages(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """
    Conversion txt → pages[] for office_read_pdf coarse.
    Priority: \\f split → --- page N --- → single page with note.
    """
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    note: str | None = None

    if "\f" in normalized:
        parts = [p.strip() for p in normalized.split("\f") if p.strip()]
        pages = [
            {"page_index": i, "blocks": _blocks_from_text(part)}
            for i, part in enumerate(parts)
        ]
        return pages, None

    page_marker = re.compile(r"^---\s*page\s+(\d+)\s*---\s*$", re.I | re.M)
    if page_marker.search(normalized):
        sections = re.split(r"^---\s*page\s+\d+\s*---\s*$", normalized, flags=re.I | re.M)
        sections = [s.strip() for s in sections if s.strip()]
        pages = [
            {"page_index": i, "blocks": _blocks_from_text(part)}
            for i, part in enumerate(sections)
        ]
        return pages, None

    note = "No page boundaries detected in coarse txt; treated as single page."
    return [{"page_index": 0, "blocks": _blocks_from_text(normalized)}], note


def pages_to_outline(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outline: list[dict[str, Any]] = []
    for page in pages:
        blocks = page.get("blocks") or []
        title = blocks[0].get("text", "")[:120] if blocks else ""
        outline.append({"page_index": page.get("page_index", 0), "title": title})
    return outline


def pages_to_text(pages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for page in pages:
        idx = page.get("page_index", 0)
        parts.append(f"--- page {idx + 1} ---")
        for block in page.get("blocks") or []:
            if block.get("text"):
                parts.append(str(block["text"]))
    return "\n".join(parts)
