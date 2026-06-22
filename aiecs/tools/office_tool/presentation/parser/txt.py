"""Coarse plain-text parser for presentation Conversion output (legacy pptx txt)."""

from __future__ import annotations

import re
from typing import Any


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text)) if text else 0


def parse_txt_to_structure(text: str) -> dict[str, Any]:
    """Parse plain-text conversion output into structured elements."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    elements: list[dict[str, Any]] = []
    all_text_parts: list[str] = []
    title = ""

    blocks = re.split(r"\n{3,}|\f", normalized) if normalized else []
    if len(blocks) <= 1 and normalized:
        blocks = [line.strip() for line in normalized.splitlines() if line.strip()]

    for idx, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
        elements.append({"index": idx, "type": "paragraph", "text": block})
        all_text_parts.append(block)
        if not title:
            title = block.split("\n", 1)[0][:200]

    full_text = " ".join(all_text_parts)
    return {
        "elements": elements,
        "word_count": _count_words(full_text),
        "page_count": max(1, len(blocks)) if blocks else 0,
        "title": title,
    }


def extract_outline_from_txt(text: str) -> list[dict[str, Any]]:
    """Heuristic outline from plain text (slide titles, numbered headings)."""
    outline: list[dict[str, Any]] = []
    for idx, line in enumerate((text or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        if len(line) <= 120 and (
            re.match(r"^[\d.]+\s+\S", line)
            or line.endswith(":")
            or re.match(r"^Slide \d+", line, re.I)
        ):
            outline.append({"index": idx, "type": "heading1", "text": line})
    return outline
