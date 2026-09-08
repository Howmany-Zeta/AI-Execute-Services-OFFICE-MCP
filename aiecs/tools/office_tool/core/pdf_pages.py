"""Lightweight PDF page estimate (trailer / Type Page count)."""

from __future__ import annotations

import re

_PAGE_RE = re.compile(rb"/Type\s*/Page(?!s)\b")


def estimate_pdf_pages(data: bytes) -> int | None:
    if not data or not data.startswith(b"%PDF"):
        return None
    count = len(_PAGE_RE.findall(data))
    return count if count > 0 else None
