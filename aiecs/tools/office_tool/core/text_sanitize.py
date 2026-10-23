"""Sanitize caller-facing document text. No layout or run-merge rules here."""

from __future__ import annotations

import re
from typing import Any

# C0 except TAB / LF / CR.
_C0_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_NBSP_TO_SPACE = str.maketrans({"\u00a0": " ", "\u3000": " "})


def ltrim_regular_spaces(text: str) -> str:
    start = 0
    while start < len(text) and text[start] == " ":
        start += 1
    return text[start:]


def rtrim_regular_spaces(text: str) -> str:
    end = len(text)
    while end > 0 and text[end - 1] == " ":
        end -= 1
    return text[:end]


def trim_regular_spaces(text: str) -> str:
    return rtrim_regular_spaces(ltrim_regular_spaces(text))


def sanitize_text(value: Any, *, trim_edges: bool = True) -> str:
    """Strip harmful C0, fold NBSP / ideographic space, optionally trim regular spaces."""
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = str(value)
    else:
        text = str(value)
    text = text.translate(_NBSP_TO_SPACE)
    text = _C0_RE.sub("", text)
    if trim_edges:
        text = trim_regular_spaces(text)
    return text


def has_visible_text(value: Any) -> bool:
    """True when sanitize_text leaves a character that is not space / tab / newline."""
    return bool(sanitize_text(value, trim_edges=True).strip())
