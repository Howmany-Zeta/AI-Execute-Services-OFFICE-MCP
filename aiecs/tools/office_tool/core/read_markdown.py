"""Project sidecar / conversion elements to reading-line Markdown (ADR-049)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text

READ_NOTE = (
    "For model reading only. Do not pass any index, page marker, or media URL to office_edit_*."
)

_HEADING_NUM_RE = re.compile(r"^heading(\d+)$", re.I)
_PAGE_MARKER_RE = re.compile(r"^\[Page \d+\]$")
_HR_CELL_RE = re.compile(r"^:?-{3,}:?$")


@dataclass
class MdBlock:
    type: str
    text: str = ""
    level: int | None = None
    rows: list[list[str]] | None = None
    alt: str = ""
    media_name: str | None = None
    runs: list[dict[str, Any]] | None = None


@dataclass
class MdPage:
    page: int | None
    blocks: list[MdBlock] = field(default_factory=list)
    name: str | None = None
    csv: str | None = None
    show_marker: bool = True


def _heading_level(element: dict[str, Any]) -> int | None:
    raw_type = str(element.get("type") or "")
    match = _HEADING_NUM_RE.match(raw_type)
    if match:
        return min(6, max(1, int(match.group(1))))
    if raw_type in {"heading", "chapter", "title", "outline"}:
        if element.get("level") is not None:
            try:
                return min(6, max(1, int(element["level"])))
            except (TypeError, ValueError):
                return 1
        if element.get("outline_level") is not None:
            try:
                return min(6, max(1, int(element["outline_level"]) + 1))
            except (TypeError, ValueError):
                return 1
        return 1
    if element.get("outline_level") is not None:
        try:
            return min(6, max(1, int(element["outline_level"]) + 1))
        except (TypeError, ValueError):
            return None
    return None


def runs_to_md(runs: list[dict[str, Any]] | None, fallback: str = "") -> str:
    if not runs:
        return sanitize_text(fallback, trim_edges=True)
    parts: list[str] = []
    for run in runs:
        text = str(run.get("text") or "")
        if run.get("bold"):
            text = f"**{text}**"
        if run.get("italic"):
            text = f"*{text}*"
        parts.append(text)
    return "".join(parts)


def _table_md(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    normalized: list[list[str]] = []
    for row in rows:
        if isinstance(row, (list, tuple)):
            normalized.append([sanitize_text(cell, trim_edges=True) for cell in row])
        else:
            normalized.append([sanitize_text(row, trim_edges=True)])
    width = max(len(row) for row in normalized)
    if width == 0:
        return ""
    for row in normalized:
        while len(row) < width:
            row.append("")
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def rows_to_csv(rows: list[list[Any]]) -> str:
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for row in rows:
        if isinstance(row, (list, tuple)):
            writer.writerow(["" if cell is None else cell for cell in row])
        else:
            writer.writerow([row])
    return buf.getvalue()


def element_to_block(element: dict[str, Any]) -> MdBlock | None:
    raw_type = str(element.get("type") or "paragraph")
    heading = _heading_level(element)
    if heading is not None and raw_type not in {"list", "quote", "table", "image"}:
        text = runs_to_md(element.get("runs"), element.get("text") or "")
        if not has_visible_text(text):
            return None
        return MdBlock(type="heading", text=text, level=heading, runs=element.get("runs"))
    if raw_type == "table":
        rows = element.get("rows")
        if not isinstance(rows, list) or not rows:
            return None
        if rows and not isinstance(rows[0], (list, tuple)):
            return None
        return MdBlock(type="table", rows=rows)
    if raw_type == "image":
        alt = sanitize_text(element.get("alt") or element.get("text") or "image", trim_edges=True) or "image"
        return MdBlock(type="image", alt=alt, text=alt, media_name=element.get("media_name"))
    text = runs_to_md(element.get("runs"), element.get("text") or "")
    if raw_type == "list":
        if not has_visible_text(text):
            return None
        return MdBlock(type="list", text=text)
    if raw_type == "quote":
        if not has_visible_text(text):
            return None
        return MdBlock(type="quote", text=text)
    if raw_type in {"header", "footer", "footnote", "toc", "caption", "textbox", "paragraph"}:
        if not has_visible_text(text):
            return None
        return MdBlock(type=raw_type if raw_type != "textbox" else "paragraph", text=text)
    if not has_visible_text(text):
        return None
    return MdBlock(type="paragraph", text=text)


def word_elements_to_pages(elements: list[dict[str, Any]]) -> list[MdPage]:
    by_page: dict[int, list[dict[str, Any]]] = {}
    for element in elements:
        try:
            page_no = int(element.get("page") or 1)
        except (TypeError, ValueError):
            page_no = 1
        by_page.setdefault(page_no, []).append(element)

    seen_headers: set[str] = set()
    seen_footers: set[str] = set()
    pages: list[MdPage] = []
    for page_no in sorted(by_page):
        headers: list[dict[str, Any]] = []
        footers: list[dict[str, Any]] = []
        footnotes: list[dict[str, Any]] = []
        body: list[dict[str, Any]] = []
        for element in by_page[page_no]:
            kind = element.get("type")
            text = sanitize_text(element.get("text"), trim_edges=True)
            if kind == "header":
                if has_visible_text(text) and text not in seen_headers:
                    seen_headers.add(text)
                    headers.append(element)
                continue
            if kind == "footer":
                if has_visible_text(text) and text not in seen_footers:
                    seen_footers.add(text)
                    footers.append(element)
                continue
            if kind == "footnote":
                footnotes.append(element)
                continue
            body.append(element)
        blocks: list[MdBlock] = []
        for element in headers + body + footers + footnotes:
            block = element_to_block(element)
            if block:
                blocks.append(block)
        pages.append(MdPage(page=page_no, blocks=blocks))
    if not pages:
        pages.append(MdPage(page=1, blocks=[]))
    return pages


def conversion_elements_to_pages(elements: list[dict[str, Any]]) -> list[MdPage]:
    blocks: list[MdBlock] = []
    for element in elements:
        block = element_to_block(element)
        if block:
            blocks.append(block)
    return [MdPage(page=1, blocks=blocks)]


def sheet_pages(sheets: list[dict[str, Any]]) -> list[MdPage]:
    pages: list[MdPage] = []
    for index, sheet in enumerate(sheets):
        name = str(sheet.get("name") or f"Sheet{index + 1}")
        csv_text = rows_to_csv(sheet.get("rows") or [])
        pages.append(
            MdPage(
                page=index + 1,
                name=name,
                csv=csv_text,
                blocks=[],
            )
        )
    return pages


def pdf_page_to_blocks(page: dict[str, Any]) -> list[MdBlock]:
    blocks: list[MdBlock] = []
    for raw in page.get("blocks") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "table":
            block = element_to_block({"type": "table", "rows": raw.get("rows") or []})
        else:
            block = element_to_block({"type": "paragraph", "text": raw.get("text") or ""})
        if block:
            blocks.append(block)
    return blocks


def page_visible_chars(page: dict[str, Any]) -> int:
    count = 0
    for raw in page.get("blocks") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "table":
            for row in raw.get("rows") or []:
                cells = row if isinstance(row, (list, tuple)) else [row]
                for cell in cells:
                    count += sum(1 for ch in str(cell) if not ch.isspace())
        else:
            count += sum(1 for ch in str(raw.get("text") or "") if not ch.isspace())
    return count


def block_to_md(block: MdBlock, fmt: str) -> str:
    if fmt == "outline" and block.type != "heading":
        return ""
    if block.type == "heading":
        level = min(6, max(1, block.level or 1))
        return f"{'#' * level} {block.text}".rstrip()
    if block.type == "list":
        lines = [line for line in block.text.splitlines() if has_visible_text(line)]
        return "\n".join(f"- {line}" for line in lines)
    if block.type == "quote":
        return "\n".join(f"> {line}" if line else ">" for line in block.text.splitlines())
    if block.type == "table":
        return _table_md(block.rows or [])
    if block.type == "image":
        target = f"media/{block.media_name}" if block.media_name else ""
        return f"![{block.alt}]({target})"
    return block.text


def assemble_markdown(pages: list[MdPage], fmt: str = "markdown") -> str:
    chunks: list[str] = []
    for page in pages:
        if page.csv is not None:
            lines: list[str] = []
            if page.show_marker and page.page is not None:
                lines.append(f"[Page {page.page}]")
            if page.name:
                lines.append(f"<!-- sheet: {page.name} -->")
            lines.append(page.csv.rstrip("\n"))
            chunks.append("\n".join(lines).rstrip())
            continue
        body_parts: list[str] = []
        for block in page.blocks:
            rendered = block_to_md(block, fmt)
            if rendered:
                body_parts.append(rendered)
        if fmt == "outline" and not body_parts:
            continue
        page_parts: list[str] = []
        if page.show_marker and page.page is not None:
            page_parts.append(f"[Page {page.page}]")
        page_parts.extend(body_parts)
        if page_parts:
            chunks.append("\n\n".join(page_parts))
    text = "\n\n".join(chunks).strip()
    return text + ("\n" if text else "")


def markdown_to_plain(md: str) -> str:
    lines: list[str] = []
    for line in (md or "").splitlines():
        stripped = line.strip()
        if _PAGE_MARKER_RE.match(stripped):
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^>\s?", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = line.replace("**", "")
        line = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", line)
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and all(_HR_CELL_RE.match(cell) for cell in cells):
                continue
            line = "\t".join(cells)
        lines.append(line)
    text = "\n".join(lines).strip()
    return text + ("\n" if text else "")


def title_from_pages(pages: list[MdPage]) -> str:
    for page in pages:
        if page.name:
            return page.name
        for block in page.blocks:
            if block.type == "heading" and has_visible_text(block.text):
                return block.text
        for block in page.blocks:
            if has_visible_text(block.text):
                return block.text[:200]
    return ""


def apply_page_slice(pages: list[MdPage], page_range: tuple[int, int] | None) -> list[MdPage]:
    if not page_range:
        return pages
    start, end = page_range
    return [page for page in pages if page.page is not None and start <= page.page <= end]


def truncate_output(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text, False
    return raw[:max_bytes].decode("utf-8", errors="ignore"), True
