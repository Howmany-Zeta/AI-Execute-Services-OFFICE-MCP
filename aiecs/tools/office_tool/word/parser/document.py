"""
Parse ONLYOFFICE doc.ToJSON() output into Word blocks[].
"""

from __future__ import annotations

import json
import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text

from aiecs.tools.office_tool.word.parser.fine import WORD_TOJSON_EXTRACT_BODY

_HEADING_STYLE_MAP = {
    "heading 1": "heading1",
    "heading1": "heading1",
    "heading 2": "heading2",
    "heading2": "heading2",
    "heading 3": "heading3",
    "heading3": "heading3",
}

_HEADING_LEVEL_RE = re.compile(r"(?:heading|标题)\s*([1-6])$", re.I)
_IMAGE_TYPES = frozenset({"image", "drawing", "picture", "pic"})


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text)) if text else 0


def _extract_text(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text") or "")
    if node.get("type") == "run":
        direct = node.get("text")
        if direct:
            return str(direct)
    direct = node.get("text")
    if isinstance(direct, str) and direct:
        return direct
    parts: list[str] = []
    for child in node.get("content") or node.get("elements") or []:
        if isinstance(child, str):
            parts.append(child)
        elif isinstance(child, dict):
            parts.append(_extract_text(child))
    return sanitize_text(" ".join(p for p in parts if p), trim_edges=True)


def _style_to_block_type(style: str) -> str:
    key = (style or "").strip().lower()
    return _HEADING_STYLE_MAP.get(key, "paragraph")


def _heading_level_from_style(style: str) -> int | None:
    text = (style or "").strip()
    if not text:
        return None
    mapped = _HEADING_STYLE_MAP.get(text.lower())
    if mapped and mapped[-1].isdigit():
        return int(mapped[-1])
    match = _HEADING_LEVEL_RE.search(text) or _HEADING_LEVEL_RE.search(text.lower())
    if match:
        return int(match.group(1))
    return None


def _iter_body_nodes(raw: dict | list) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [n for n in raw if isinstance(n, dict)]
    if isinstance(raw, dict):
        for key in ("content", "elements", "body", "document"):
            val = raw.get(key)
            if isinstance(val, list):
                return [n for n in val if isinstance(n, dict)]
        if raw.get("type") in ("paragraph", "table", "section"):
            return [raw]
    return []


def parse_document_json(raw: dict | str) -> list[dict[str, Any]]:
    """Parse ONLYOFFICE ToJSON into blocks with block_index, type, text, heading_path."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    if isinstance(data, dict) and isinstance(data.get("document"), dict) and (
        "sections" in data or "body" in data
    ):
        data = data["document"]

    nodes = _iter_body_nodes(data)
    blocks: list[dict[str, Any]] = []
    heading_stack: list[str] = []

    for index, node in enumerate(nodes):
        ntype = (node.get("type") or "paragraph").lower()
        if ntype == "table":
            rows: list[list[str]] = []
            for row in node.get("rows") or node.get("content") or []:
                if not isinstance(row, dict):
                    continue
                cells = row.get("cells") or row.get("content") or []
                row_texts: list[str] = []
                for cell in cells:
                    if isinstance(cell, dict):
                        row_texts.append(sanitize_text(_extract_text(cell), trim_edges=True))
                    else:
                        row_texts.append(sanitize_text(cell, trim_edges=True))
                if row_texts:
                    rows.append(row_texts)
            if not rows and isinstance(node.get("rows"), list):
                rows = [[str(c) for c in row] for row in node["rows"] if row]
            block = {
                "block_index": index,
                "type": "table",
                "rows": rows,
                "row_count": len(rows),
                "col_count": max((len(r) for r in rows), default=0),
            }
            blocks.append(block)
            continue

        if ntype in {"page_break", "pagebreak"}:
            blocks.append({"block_index": index, "type": "page_break"})
            continue

        if ntype == "textbox":
            text = sanitize_text(_extract_text(node), trim_edges=True)
            if has_visible_text(text):
                block = {"block_index": index, "type": "textbox", "text": text}
                blocks.append(block)
            continue

        if ntype == "chart":
            blocks.append({
                "block_index": index,
                "type": "chart",
                "chart_type": str(node.get("chart_type") or "unknown"),
                "rows": node.get("rows") if isinstance(node.get("rows"), list) else [],
            })
            continue

        if ntype == "caption":
            text = sanitize_text(_extract_text(node), trim_edges=True)
            if has_visible_text(text):
                blocks.append({"block_index": index, "type": "caption", "text": text})
            continue

        if ntype in _IMAGE_TYPES:
            alt = sanitize_text(
                node.get("alt") or node.get("title") or _extract_text(node) or "image",
                trim_edges=True,
            ) or "image"
            blocks.append({
                "block_index": index,
                "type": "image",
                "alt": alt,
                "text": alt,
            })
            continue

        style = str(node.get("style") or node.get("styleName") or "")
        text = sanitize_text(_extract_text(node), trim_edges=True)
        if not has_visible_text(text):
            continue
        heading_level = _heading_level_from_style(style)
        block_type = _style_to_block_type(style)
        block: dict[str, Any] = {
            "block_index": index,
            "type": block_type,
            "text": text,
        }
        if style:
            block["style_name"] = style
        if heading_level is not None:
            block["heading_level"] = heading_level
            heading_stack = heading_stack[: heading_level - 1]
            if text:
                if len(heading_stack) >= heading_level:
                    heading_stack[heading_level - 1] = text
                else:
                    heading_stack.append(text)
            block["heading_path"] = list(heading_stack)
        blocks.append(block)

    return blocks


def blocks_to_outline(blocks: list[dict]) -> list[dict]:
    """Return heading blocks only."""
    return [
        {
            "block_index": b["block_index"],
            "type": b["type"],
            "text": b.get("text", ""),
            "heading_path": b.get("heading_path"),
        }
        for b in blocks
        if str(b.get("type", "")).startswith("heading")
    ]


def blocks_to_text(blocks: list[dict]) -> str:
    """Concatenate block text; tables as tab-separated rows."""
    parts: list[str] = []
    for b in blocks:
        if b.get("type") == "table":
            for row in b.get("rows") or []:
                parts.append("\t".join(str(c) for c in row))
        else:
            text = sanitize_text(b.get("text", ""), trim_edges=True)
            if has_visible_text(text):
                parts.append(text)
    return "\n".join(parts)


def word_count_from_blocks(blocks: list[dict]) -> int:
    total = 0
    for b in blocks:
        if b.get("type") == "table":
            for row in b.get("rows") or []:
                total += sum(_count_words(str(c)) for c in row)
        else:
            total += _count_words(str(b.get("text") or ""))
    return total
