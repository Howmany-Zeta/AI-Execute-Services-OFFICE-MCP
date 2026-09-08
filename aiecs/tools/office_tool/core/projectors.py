"""Project structure[] to markdown / plain text (ADR-048)."""

from __future__ import annotations

from typing import Any


def _heading_prefix(block_type: str) -> str:
    if block_type.startswith("heading"):
        n = "".join(ch for ch in block_type if ch.isdigit()) or "1"
        return "#" * min(6, max(1, int(n))) + " "
    if block_type == "title":
        return "# "
    return ""


def _table_md(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    lines = [
        "| " + " | ".join(str(c) for c in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def structure_to_markdown(structure: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for unit in structure:
        kind = unit.get("kind") or ""
        if kind == "page":
            parts.append(f"<!-- page {int(unit.get('page_index', 0)) + 1} -->")
        if kind == "slide":
            parts.append(f"<!-- slide {int(unit.get('slide_index', 0)) + 1} -->")
        for block in unit.get("blocks") or []:
            btype = block.get("type") or "paragraph"
            if btype == "table":
                md = _table_md(block.get("rows") or [])
                if md:
                    parts.append(md)
                continue
            text = (block.get("text") or "").strip()
            if not text:
                continue
            if btype == "figure":
                parts.append(f"> {text}")
            elif btype == "list":
                for line in text.splitlines():
                    parts.append(f"- {line}")
            else:
                parts.append(f"{_heading_prefix(btype)}{text}")
    return "\n\n".join(parts).strip() + ("\n" if parts else "")


def structure_to_text(structure: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for unit in structure:
        for block in unit.get("blocks") or []:
            if block.get("type") == "table":
                for row in block.get("rows") or []:
                    parts.append("\t".join(str(c) for c in row))
            elif block.get("text"):
                parts.append(str(block["text"]))
    return "\n".join(parts)
