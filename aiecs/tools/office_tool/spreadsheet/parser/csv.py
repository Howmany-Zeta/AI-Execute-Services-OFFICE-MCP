"""Coarse CSV parser for spreadsheet Conversion output (legacy xlsx csv)."""

from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Any


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text)) if text else 0


def parse_csv_to_structure(text: str) -> dict[str, Any]:
    """Parse CSV conversion output into row elements."""
    reader = csv.reader(StringIO(text or ""))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    elements: list[dict[str, Any]] = []
    all_text_parts: list[str] = []

    for idx, row in enumerate(rows):
        row_text = ", ".join(row)
        elements.append({"index": idx, "type": "row", "cells": row, "text": row_text})
        all_text_parts.extend(row)

    full_text = " ".join(all_text_parts)
    title = rows[0][0].strip() if rows and rows[0] else ""
    return {
        "elements": elements,
        "word_count": _count_words(full_text),
        "page_count": 1 if rows else 0,
        "title": title,
    }


def extract_outline_from_csv(text: str) -> list[dict[str, Any]]:
    """Use header row as outline when present."""
    reader = csv.reader(StringIO(text or ""))
    rows = list(reader)
    if not rows:
        return []
    header = rows[0]
    return [
        {"index": idx, "type": "heading1", "text": cell.strip()}
        for idx, cell in enumerate(header)
        if cell.strip()
    ]


def csv_to_coarse_sheets(text: str) -> list[dict[str, Any]]:
    """
    Coarse read: single-sheet snapshot from csv conversion.
    Multi-sheet workbooks may lose sheets in coarse mode.
    """
    reader = csv.reader(StringIO(text or ""))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    return [
        {
            "sheet_index": 0,
            "name": "Sheet1",
            "rows": rows,
            "row_count": len(rows),
            "col_count": max((len(r) for r in rows), default=0),
            "used_range": f"A1:{_col_letter(max((len(r) for r in rows), default=1) - 1)}{len(rows)}" if rows else None,
        }
    ]


def _col_letter(col_index: int) -> str:
    """0-based column index to Excel letter (0=A)."""
    result = ""
    n = col_index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result or "A"
