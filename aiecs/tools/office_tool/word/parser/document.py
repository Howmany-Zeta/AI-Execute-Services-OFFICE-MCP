"""
Parse ONLYOFFICE doc.ToJSON() output into Word blocks[].
"""

from __future__ import annotations

import json
import re
from typing import Any

WORD_TOJSON_EXTRACT_BODY = """var doc = Api.GetDocument();
var jsonStr = JSON.stringify(doc.ToJSON(false, false, false, false, false, false));"""

_HEADING_STYLE_MAP = {
    "heading 1": "heading1",
    "heading1": "heading1",
    "heading 2": "heading2",
    "heading2": "heading2",
    "heading 3": "heading3",
    "heading3": "heading3",
}


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
    return " ".join(p for p in parts if p).strip()


def _style_to_block_type(style: str) -> str:
    key = (style or "").strip().lower()
    return _HEADING_STYLE_MAP.get(key, "paragraph")


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

    nodes = _iter_body_nodes(data)
    blocks: list[dict[str, Any]] = []
    heading_stack: list[str] = []

    for node in nodes:
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
                        row_texts.append(_extract_text(cell))
                    else:
                        row_texts.append(str(cell))
                if row_texts:
                    rows.append(row_texts)
            if not rows and isinstance(node.get("rows"), list):
                rows = [[str(c) for c in row] for row in node["rows"] if row]
            block = {
                "block_index": len(blocks),
                "type": "table",
                "rows": rows,
                "row_count": len(rows),
                "col_count": max((len(r) for r in rows), default=0),
            }
            blocks.append(block)
            continue

        style = str(node.get("style") or node.get("styleName") or "")
        text = _extract_text(node)
        block_type = _style_to_block_type(style)
        block: dict[str, Any] = {
            "block_index": len(blocks),
            "type": block_type,
            "text": text,
        }
        if style:
            block["style_name"] = style
        if block_type.startswith("heading"):
            level = int(block_type[-1]) if block_type[-1].isdigit() else 1
            heading_stack = heading_stack[: level - 1]
            if text:
                if len(heading_stack) >= level:
                    heading_stack[level - 1] = text
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
            text = b.get("text", "")
            if text:
                parts.append(str(text))
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
