"""Map Document AI raw blocks and Builder PDF pages to flat structured elements."""

from __future__ import annotations

import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text

_WORD_COUNT_RE = re.compile(r"\S+")
_HEADING_RE = re.compile(r"^heading(?:[-_\s]*(\d+))?$", re.I)
_ORPHAN_PUNCT = frozenset("。、，；：！？,.!?;:…—–->{}[]【】《》〈〉()（）<>")
_REFLOW_TYPES = frozenset({
    "paragraph",
    "heading",
    "header",
    "footer",
    "list",
    "caption",
    "quote",
    "chapter",
    "toc",
})


def _page_of(block: dict[str, Any]) -> int:
    span = block.get("pageSpan") or block.get("page_span") or {}
    if not isinstance(span, dict) or not span:
        return 1
    start = span.get("pageStart", span.get("page_start"))
    if start is None:
        return 1
    try:
        return int(start)
    except (TypeError, ValueError):
        return 1


def _flatten_text(block: dict[str, Any] | None) -> str:
    if not isinstance(block, dict):
        return ""
    text_block = block.get("textBlock") or block.get("text_block")
    if isinstance(text_block, dict):
        return sanitize_text(text_block.get("text"), trim_edges=True)
    return sanitize_text(block.get("text"), trim_edges=True)


def _caption_text(caption: Any) -> str:
    if caption is None:
        return ""
    if isinstance(caption, str):
        return sanitize_text(caption, trim_edges=True)
    if isinstance(caption, dict):
        if caption.get("text"):
            return sanitize_text(caption["text"], trim_edges=True)
        return _flatten_text(caption)
    return sanitize_text(caption, trim_edges=True)


def _table_rows(table: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for key in ("headerRows", "header_rows", "bodyRows", "body_rows"):
        for row in table.get(key) or []:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells") or []
            texts: list[str] = []
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                parts = [_flatten_text(b) for b in (cell.get("blocks") or []) if isinstance(b, dict)]
                texts.append(sanitize_text(" ".join(p for p in parts if p), trim_edges=True))
            rows.append(texts)
    return rows


def _is_orphan_punct(text: str) -> bool:
    core = sanitize_text(text, trim_edges=True).strip()
    if not core or len(core) > 2:
        return False
    return all(ch in _ORPHAN_PUNCT for ch in core)


def _can_reflow_into(element: dict[str, Any]) -> bool:
    return element.get("type") in _REFLOW_TYPES and "text" in element


def _reflow_reading_order(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach orphan punct and hyphenated splits using Document AI block order."""
    out: list[dict[str, Any]] = []
    for element in elements:
        if element.get("type") == "table":
            out.append(element)
            continue
        text = sanitize_text(element.get("text"), trim_edges=True)
        if not has_visible_text(text):
            continue
        element = dict(element)
        element["text"] = text
        if (
            out
            and _can_reflow_into(out[-1])
            and out[-1].get("page") == element.get("page")
        ):
            prev = out[-1]
            prev_text = str(prev.get("text") or "")
            if _is_orphan_punct(text):
                prev["text"] = prev_text + text.strip()
                continue
            if prev_text.endswith("-") and text[:1].isalpha():
                prev["text"] = prev_text[:-1] + text
                continue
        if _is_orphan_punct(text):
            continue
        out.append(element)
    return out


def _figure_description(block: dict[str, Any], text_block: dict[str, Any] | None) -> str:
    for source in (text_block or {}, block):
        annotations = source.get("annotations") or {}
        if isinstance(annotations, dict):
            desc = annotations.get("description") or annotations.get("imageDescription") or annotations.get("image_description")
            if desc:
                return sanitize_text(desc, trim_edges=True)
        for key in ("description", "figure_text", "caption"):
            if source.get(key):
                return sanitize_text(source[key], trim_edges=True)
    figure = block.get("figure")
    if isinstance(figure, dict):
        return sanitize_text(figure.get("description") or figure.get("text") or "", trim_edges=True)
    if isinstance(figure, str):
        return sanitize_text(figure, trim_edges=True)
    return ""


def _map_text_type(raw_type: str) -> tuple[str, int | None]:
    text = (raw_type or "").strip()
    low = text.lower()
    match = _HEADING_RE.match(low)
    if match:
        level = int(match.group(1)) if match.group(1) else 1
        return "heading", level
    if low == "title":
        return "heading", 1
    if low == "subtitle":
        return "paragraph", None
    if low in {"header", "footer"}:
        return low, None
    return "paragraph", None


def _emit_leaf_text(block: dict[str, Any], text_block: dict[str, Any], out: list[dict[str, Any]]) -> None:
    raw_type = str(text_block.get("type") or block.get("type") or "paragraph")
    low = raw_type.lower()
    if low == "figure" or block.get("figure") is not None:
        desc = _figure_description(block, text_block)
        if has_visible_text(desc):
            out.append({"page": _page_of(block), "type": "paragraph", "text": desc})
        return
    mapped, level = _map_text_type(raw_type)
    text = sanitize_text(text_block.get("text"), trim_edges=True)
    if not has_visible_text(text):
        return
    element: dict[str, Any] = {
        "page": _page_of(block),
        "type": mapped,
        "text": text,
    }
    if level is not None:
        element["level"] = level
    out.append(element)


def _walk_block(block: dict[str, Any], out: list[dict[str, Any]]) -> None:
    if not isinstance(block, dict):
        return
    text_block = block.get("textBlock") or block.get("text_block")
    table_block = block.get("tableBlock") or block.get("table_block")
    list_block = block.get("listBlock") or block.get("list_block")

    if list_block:
        page = _page_of(block)
        entries = list_block.get("listEntries") or list_block.get("list_entries") or []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            parts = [
                part
                for part in (_flatten_text(b) for b in (entry.get("blocks") or []) if isinstance(b, dict))
                if has_visible_text(part)
            ]
            if parts:
                out.append({"page": page, "type": "list", "text": "\n".join(parts)})
        return

    if table_block:
        page = _page_of(block)
        caption = _caption_text(table_block.get("caption"))
        if has_visible_text(caption):
            out.append({"page": page, "type": "paragraph", "text": caption})
        out.append({"page": page, "type": "table", "rows": _table_rows(table_block)})
        return

    if isinstance(text_block, dict):
        children = [c for c in (text_block.get("blocks") or []) if isinstance(c, dict)]
        if children:
            for child in children:
                _walk_block(child, out)
            return
        _emit_leaf_text(block, text_block, out)
        return

    if block.get("figure") is not None or str(block.get("type") or "").lower() == "figure":
        desc = _figure_description(block, None)
        if has_visible_text(desc):
            out.append({"page": _page_of(block), "type": "paragraph", "text": desc})
        return

    children = [c for c in (block.get("blocks") or []) if isinstance(c, dict)]
    if children:
        for child in children:
            _walk_block(child, out)
        return

    if block.get("type") or block.get("text"):
        _emit_leaf_text(block, {"type": block.get("type"), "text": block.get("text") or ""}, out)


def layout_to_elements(document: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Map Document AI raw documentLayout blocks to flat elements. Does not use layout_to_pages."""
    data = document if isinstance(document, dict) else {}
    layout = data.get("documentLayout") or data.get("document_layout") or data
    blocks = layout.get("blocks") if isinstance(layout, dict) else []
    out: list[dict[str, Any]] = []
    for block in blocks or []:
        if isinstance(block, dict):
            _walk_block(block, out)
    if not out and data.get("text"):
        fallback = sanitize_text(data["text"], trim_edges=True)
        if has_visible_text(fallback):
            out.append({"page": 1, "type": "paragraph", "text": fallback})
    return _reflow_reading_order(out)


def builder_pages_to_elements(pages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Flatten PDF_PAGE_EXTRACT_BODY pages[] into top-level elements."""
    elements: list[dict[str, Any]] = []
    for index, page in enumerate(pages or []):
        if not isinstance(page, dict):
            continue
        try:
            page_no = int(page.get("page_index", index)) + 1
        except (TypeError, ValueError):
            page_no = index + 1
        for block in page.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "table":
                rows = block.get("rows") if isinstance(block.get("rows"), list) else []
                sanitized_rows = [
                    [sanitize_text(cell, trim_edges=True) for cell in row]
                    if isinstance(row, (list, tuple))
                    else [sanitize_text(row, trim_edges=True)]
                    for row in rows
                ]
                elements.append({"page": page_no, "type": "table", "rows": sanitized_rows})
            else:
                text = sanitize_text(block.get("text"), trim_edges=True)
                if has_visible_text(text):
                    elements.append({
                        "page": page_no,
                        "type": "paragraph",
                        "text": text,
                    })
    return elements


def pdf_title_from_elements(elements: list[dict[str, Any]]) -> str:
    for element in elements:
        if element.get("type") == "heading" and element.get("text"):
            return str(element["text"])
    for element in elements:
        if element.get("text"):
            return str(element["text"])[:200]
    return ""


def word_count_from_pdf_elements(elements: list[dict[str, Any]]) -> int:
    total = 0
    for element in elements:
        if element.get("type") == "table":
            for row in element.get("rows") or []:
                if isinstance(row, (list, tuple)):
                    total += sum(len(_WORD_COUNT_RE.findall(str(cell))) for cell in row)
        else:
            total += len(_WORD_COUNT_RE.findall(str(element.get("text") or "")))
    return total


def pdf_page_count(elements: list[dict[str, Any]]) -> int:
    pages = [int(el["page"]) for el in elements if isinstance(el.get("page"), int)]
    return max(pages) if pages else 1
