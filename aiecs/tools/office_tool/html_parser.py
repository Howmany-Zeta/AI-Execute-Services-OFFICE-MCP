"""
HTML parser for office_read_document.

Parses ONLYOFFICE Conversion API HTML output. ONLYOFFICE uses non-standard
semantic tags (e.g. div.para, span.h1, table.table). This parser handles
common patterns; may need adjustment based on real conversion samples.
"""

import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup


def _get_text(el) -> str:
    """Extract plain text from element."""
    return el.get_text(separator=" ", strip=True) if el else ""


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(re.findall(r"\S+", text)) if text else 0


def parse_html_to_structure(html: str) -> Dict[str, Any]:
    """
    Parse ONLYOFFICE HTML to structured elements.

    Handles: h1-h6, p, table, div (with class hints like .para, .h1).
    Returns elements, word_count, page_count, title.
    """
    soup = BeautifulSoup(html, "html.parser")
    elements: List[Dict[str, Any]] = []
    all_text_parts: List[str] = []
    title = ""

    # Common selectors: standard + ONLYOFFICE-style classes
    heading_selectors = [
        "h1", "h2", "h3", "h4", "h5", "h6",
        "[class*='heading']", "[class*='Heading']", "[class*='h1']", "[class*='h2']",
    ]
    para_selectors = ["p", "[class*='para']", "[class*='Para']"]
    table_selector = "table"

    def add_element(idx: int, el_type: str, **kwargs) -> None:
        elements.append({"index": idx, "type": el_type, **kwargs})

    idx = 0
    seen = set()

    # Headings
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if id(tag) in seen:
            continue
        seen.add(id(tag))
        text = _get_text(tag)
        level = int(tag.name[1]) if tag.name and len(tag.name) == 2 else 1
        add_element(idx, f"heading{level}", text=text)
        all_text_parts.append(text)
        if not title and text:
            title = text
        idx += 1

    # Class-based headings (ONLYOFFICE may use span.h1, div.h2, etc.)
    for sel in ["[class*='Heading1']", "[class*='heading1']", "[class*='h1']",
                "[class*='Heading2']", "[class*='heading2']", "[class*='h2']",
                "[class*='Heading3']", "[class*='heading3']", "[class*='h3']"]:
        for el in soup.select(sel):
            if id(el) in seen:
                continue
            seen.add(id(el))
            text = _get_text(el)
            if not text:
                continue
            level = 1
            if "2" in sel or "h2" in sel.lower():
                level = 2
            elif "3" in sel or "h3" in sel.lower():
                level = 3
            add_element(idx, f"heading{level}", text=text)
            all_text_parts.append(text)
            if not title and text:
                title = text
            idx += 1

    # Paragraphs
    for tag in soup.find_all("p"):
        if id(tag) in seen:
            continue
        seen.add(id(tag))
        text = _get_text(tag)
        add_element(idx, "paragraph", text=text)
        all_text_parts.append(text)
        idx += 1

    # div.para, etc.
    for el in soup.select("[class*='para']"):
        if id(el) in seen:
            continue
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            continue
        seen.add(id(el))
        text = _get_text(el)
        if text:
            add_element(idx, "paragraph", text=text)
            all_text_parts.append(text)
            idx += 1

    # Tables
    for tag in soup.find_all("table"):
        if id(tag) in seen:
            continue
        seen.add(id(tag))
        rows = len(tag.find_all("tr"))
        cols = 0
        for row in tag.find_all("tr"):
            cells = len(row.find_all(["td", "th"]))
            cols = max(cols, cells)
        add_element(idx, "table", rows=rows, cols=cols)
        idx += 1

    # Fallback: any remaining text blocks
    body = soup.find("body") or soup
    for block in body.find_all(["div", "section"], recursive=True):
        if id(block) in seen:
            continue
        text = _get_text(block)
        if not text or len(text) < 2:
            continue
        # Skip if child elements already captured
        if block.find("h1") or block.find("h2") or block.find("p") or block.find("table"):
            continue
        seen.add(id(block))
        add_element(idx, "paragraph", text=text)
        all_text_parts.append(text)
        idx += 1

    full_text = " ".join(all_text_parts)
    word_count = _count_words(full_text)

    # page_count: not typically in HTML; try to find or default 0
    page_count = 0
    page_el = soup.find(class_=re.compile(r"page|Page", re.I))
    if page_el:
        page_count = max(1, len(soup.find_all(class_=re.compile(r"page|Page", re.I))))

    return {
        "elements": elements,
        "word_count": word_count,
        "page_count": page_count,
        "title": title or "",
    }


def extract_plain_text(html: str) -> str:
    """Extract plain text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def extract_outline(html: str) -> List[Dict[str, Any]]:
    """Extract only heading hierarchy (for outline/TOC)."""
    structure = parse_html_to_structure(html)
    return [
        {"index": e["index"], "type": e["type"], "text": e.get("text", "")}
        for e in structure["elements"]
        if e["type"].startswith("heading")
    ]
