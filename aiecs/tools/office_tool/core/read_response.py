"""Unified read response builder for office_read_{category} tools (ADR-028)."""

from typing import Any, Optional

from aiecs.tools.office_tool.core.categories import DocumentCategory

_CATEGORY_ALIASES: dict[DocumentCategory, tuple[str, str | None]] = {
    "word": ("blocks", None),
    "presentation": ("slides", "slide_count"),
    "spreadsheet": ("sheets", None),
    "pdf": ("pages", "page_count"),
}


def build_read_response(
    *,
    category: DocumentCategory,
    title: str,
    units: list[dict],
    read_mode: str,
    locator_note: str,
    note: str | None = None,
    source_path: str | None = None,
    source_path_format: str | None = None,
    word_count: int | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """
    Build canonical read response with category, units[], mirrors, and locator notes.

    ``_locator_note`` carries edit positioning guidance. Optional ``note`` sets
    ``_note`` for operational warnings (e.g. coarse read caveats) without duplicating
    the locator text.
    """
    response: dict[str, Any] = {
        "success": True,
        "category": category,
        "title": title,
        "units": units,
        "unit_count": len(units),
        "read_mode": read_mode,
        "_locator_note": locator_note,
    }
    if note is not None:
        response["_note"] = note

    if source_path is not None:
        response["source_path"] = source_path
    if source_path_format is not None:
        response["source_path_format"] = source_path_format
    if word_count is not None:
        response["word_count"] = word_count

    alias_key, count_key = _CATEGORY_ALIASES.get(category, (None, None))
    if alias_key:
        response[alias_key] = units
    if count_key:
        response[count_key] = len(units)

    if extra:
        response.update(extra)

    return response
