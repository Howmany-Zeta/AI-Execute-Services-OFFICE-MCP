"""
Parse ONLYOFFICE SlidesToJSON output into slides[] and layouts[] (ADR-016).
"""

from __future__ import annotations

import json
import re
from typing import Any


def build_slides_extract_body(start: int = 0, end: int | None = None) -> str:
    """Builder extract body: SlidesToJSON(start, end) inclusive 0-based (ADR-045)."""
    if end is None:
        return f"""var pres = Api.GetPresentation();
var last = pres.GetSlidesCount() - 1;
var jsonStr = JSON.stringify(pres.SlidesToJSON({start}, last, false, false, false, false));"""
    return f"""var pres = Api.GetPresentation();
var jsonStr = JSON.stringify(pres.SlidesToJSON({start}, {end}, false, false, false, false));"""


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text)) if text else 0


def _infer_role(shape: dict[str, Any]) -> str | None:
    placeholder = (shape.get("placeholder_type") or shape.get("placeholderType") or "").lower()
    if placeholder == "title" or shape.get("role") == "title":
        return "title"
    if placeholder in ("body", "content") or shape.get("role") == "body":
        return "body"
    if placeholder == "subtitle" or shape.get("role") == "subtitle":
        return "subtitle"
    return shape.get("role")


def _normalize_shape(raw: dict[str, Any], shape_index: int) -> dict[str, Any]:
    text = raw.get("text") or raw.get("content") or ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text)
    shape: dict[str, Any] = {
        "shape_index": shape_index,
        "type": raw.get("type") or "shape",
        "text": str(text).strip(),
    }
    placeholder = raw.get("placeholder_type") or raw.get("placeholderType")
    if placeholder:
        shape["placeholder_type"] = placeholder
    role = _infer_role(raw)
    if role:
        shape["role"] = role
    return shape


def _normalize_slide(raw: dict[str, Any], slide_index: int) -> dict[str, Any]:
    layout = raw.get("layout") or raw.get("layoutName") or raw.get("layout_name") or ""
    shapes_raw = raw.get("shapes") or raw.get("spTree") or raw.get("content") or []
    shapes: list[dict[str, Any]] = []
    if isinstance(shapes_raw, list):
        for si, s in enumerate(shapes_raw):
            if isinstance(s, dict):
                shapes.append(_normalize_shape(s, si))

    title = raw.get("title") or ""
    if not title:
        for sh in shapes:
            if sh.get("role") == "title" and sh.get("text"):
                title = sh["text"]
                break

    slide: dict[str, Any] = {
        "slide_index": slide_index,
        "title": title,
        "layout": layout,
        "shapes": shapes,
    }
    notes = raw.get("notes") or raw.get("notesText") or ""
    if notes:
        slide["notes"] = str(notes)
    return slide


def _iter_slides_raw(data: dict | list) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    if isinstance(data, dict):
        for key in ("slides", "Slides", "content"):
            val = data.get(key)
            if isinstance(val, list):
                return [s for s in val if isinstance(s, dict)]
        if "layout" in data or "shapes" in data:
            return [data]
    return []


def parse_slides_json(raw: dict | str) -> tuple[list[dict[str, Any]], list[str]]:
    """
    SlidesToJSON parse → (slides[], layouts[]).
    layouts[] is deduplicated layout names from slides (ADR-016 enum source).
    """
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    layouts_from_meta: list[str] = []
    if isinstance(data, dict):
        meta_layouts = data.get("layouts") or data.get("layoutNames")
        if isinstance(meta_layouts, list):
            layouts_from_meta = [str(x) for x in meta_layouts if x]

    slides_raw = _iter_slides_raw(data)
    slides = [_normalize_slide(s, i) for i, s in enumerate(slides_raw)]

    layout_set: list[str] = []
    seen: set[str] = set()
    for name in layouts_from_meta:
        if name and name not in seen:
            seen.add(name)
            layout_set.append(name)
    for slide in slides:
        layout = slide.get("layout") or ""
        if layout and layout not in seen:
            seen.add(layout)
            layout_set.append(layout)

    return slides, layout_set


def slides_to_outline(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return {slide_index, title} only."""
    return [{"slide_index": s.get("slide_index", i), "title": s.get("title", "")} for i, s in enumerate(slides)]


def slides_to_text(slides: list[dict[str, Any]]) -> str:
    """Join slides with \\n--- slide N ---\\n separators."""
    parts: list[str] = []
    for slide in slides:
        idx = slide.get("slide_index", 0)
        parts.append(f"--- slide {idx + 1} ---")
        if slide.get("title"):
            parts.append(str(slide["title"]))
        for shape in slide.get("shapes") or []:
            text = shape.get("text") or ""
            if text:
                parts.append(text)
        if slide.get("notes"):
            parts.append(f"[notes] {slide['notes']}")
    return "\n".join(parts)


def apply_slide_range(
    slides: list[dict[str, Any]],
    slide_range: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    """Inclusive filter by slide_index."""
    if not slide_range:
        return slides
    start, end = slide_range
    return [s for s in slides if start <= s.get("slide_index", 0) <= end]


def word_count_from_slides(slides: list[dict[str, Any]]) -> int:
    parts: list[str] = []
    for slide in slides:
        if slide.get("title"):
            parts.append(str(slide["title"]))
        for shape in slide.get("shapes") or []:
            if shape.get("text"):
                parts.append(str(shape["text"]))
        if slide.get("notes"):
            parts.append(str(slide["notes"]))
    return _count_words(" ".join(parts))
