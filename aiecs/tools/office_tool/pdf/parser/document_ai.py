"""Map Document AI DocumentLayout JSON to pages[] / structure[] (ADR-048)."""

from __future__ import annotations

from typing import Any


def _block_dict(block: dict[str, Any]) -> dict[str, Any]:
    return block if isinstance(block, dict) else {}


def _page_span(block: dict[str, Any]) -> tuple[int, int]:
    span = block.get("pageSpan") or block.get("page_span") or {}
    start = int(span.get("pageStart") or span.get("page_start") or 1)
    end = int(span.get("pageEnd") or span.get("page_end") or start)
    return max(0, start - 1), max(0, end - 1)


def _text_type(raw: str) -> str:
    t = (raw or "paragraph").lower()
    if t.startswith("heading-") or t.startswith("heading"):
        digit = "".join(ch for ch in t if ch.isdigit()) or "1"
        return f"heading{digit}"
    if t in ("header", "footer", "title", "subtitle"):
        return t
    if t == "list":
        return "list"
    return "paragraph"


def _table_rows(table: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for key in ("headerRows", "header_rows", "bodyRows", "body_rows"):
        for row in table.get(key) or []:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells") or row.get("cells") or []
            texts: list[str] = []
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                cell_blocks = cell.get("blocks") or []
                parts = [_flatten_text(b) for b in cell_blocks]
                texts.append(" ".join(p for p in parts if p))
            if texts:
                rows.append(texts)
    return rows


def _flatten_text(block: dict[str, Any]) -> str:
    text_block = block.get("textBlock") or block.get("text_block")
    if isinstance(text_block, dict):
        return str(text_block.get("text") or "")
    return str(block.get("text") or "")


def _emit_blocks(block: dict[str, Any], page_index: int, acc: dict[int, list[dict]]) -> None:
    text_block = block.get("textBlock") or block.get("text_block")
    table_block = block.get("tableBlock") or block.get("table_block")
    list_block = block.get("listBlock") or block.get("list_block")
    start, end = _page_span(block)
    target = acc.setdefault(start, [])

    if table_block:
        rows = _table_rows(table_block)
        caption = table_block.get("caption") or ""
        target.append({
            "block_index": len(target),
            "type": "table",
            "rows": rows,
            "row_count": len(rows),
            "col_count": max((len(r) for r in rows), default=0),
            "text": caption,
        })
        return
    if list_block:
        entries = list_block.get("listEntries") or list_block.get("list_entries") or []
        texts = []
        for entry in entries:
            if isinstance(entry, dict):
                texts.append(" ".join(_flatten_text(b) for b in (entry.get("blocks") or []) if isinstance(b, dict)))
        target.append({
            "block_index": len(target),
            "type": "list",
            "text": "\n".join(t for t in texts if t),
        })
        return
    if text_block:
        annotations = text_block.get("annotations") or {}
        desc = ""
        if isinstance(annotations, dict):
            desc = str(annotations.get("description") or annotations.get("imageDescription") or "")
        text = str(text_block.get("text") or "")
        btype = _text_type(str(text_block.get("type") or "paragraph"))
        if desc and not text:
            target.append({"block_index": len(target), "type": "figure", "text": desc})
        else:
            item = {"block_index": len(target), "type": btype, "text": text}
            if desc:
                item["figure_text"] = desc
            target.append(item)
        for child in text_block.get("blocks") or []:
            if isinstance(child, dict):
                _emit_blocks(child, page_index, acc)
        return
    # unknown wrapper
    for child in block.get("blocks") or []:
        if isinstance(child, dict):
            _emit_blocks(child, page_index, acc)


def layout_to_pages(document: dict[str, Any]) -> list[dict[str, Any]]:
    layout = document.get("documentLayout") or document.get("document_layout") or document
    blocks = layout.get("blocks") or []
    acc: dict[int, list[dict]] = {}
    for block in blocks:
        if isinstance(block, dict):
            _emit_blocks(block, 0, acc)
    if not acc and document.get("text"):
        acc[0] = [{"block_index": 0, "type": "paragraph", "text": str(document["text"])}]
    pages = []
    for idx in sorted(acc):
        pages.append({"page_index": idx, "kind": "page", "blocks": acc[idx]})
    return pages


def pages_to_structure(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return pages
