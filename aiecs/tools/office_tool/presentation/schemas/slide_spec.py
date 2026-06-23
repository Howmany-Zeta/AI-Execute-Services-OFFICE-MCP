"""Pydantic schemas for office_create_presentation slide specs (ADR-016)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ShapePosition(BaseModel):
    x: int
    y: int


class ShapeSize(BaseModel):
    width: int
    height: int


class ShapeSpec(BaseModel):
    type: Literal["textbox", "image", "title", "body"]
    text: str | None = None
    url: str | None = None
    position: ShapePosition | None = None
    size: ShapeSize | None = None


class SlideSpec(BaseModel):
    layout: str = Field(min_length=1)
    title: str | None = None
    subtitle: str | None = None
    bullets: list[str] | None = None
    shapes: list[ShapeSpec] | None = None
    notes: str | None = None


class PresentationCreateOptions(BaseModel):
    size: dict[str, int] | None = None
    allowed_layouts: list[str] = Field(
        min_length=1,
        description="layouts[] from office_read_presentation fine read (ADR-016)",
    )


class PresentationCreateArgs(BaseModel):
    slides: list[SlideSpec] = Field(min_length=1)
    output_path: str
    options: PresentationCreateOptions


PRESENTATION_CREATE_INPUT_SCHEMA: dict = PresentationCreateArgs.model_json_schema()
PRESENTATION_CREATE_INPUT_SCHEMA.pop("title", None)


def validate_slides_layouts(
    slides: list[SlideSpec],
    allowed_layouts: list[str],
) -> str | None:
    """
    Reject layouts not in allowed_layouts (ADR-016).
    Returns error message or None if valid.
    """
    allowed = set(allowed_layouts)
    for i, slide in enumerate(slides):
        if slide.layout not in allowed:
            return f"slide {i}: layout {slide.layout!r} not in allowed layouts {sorted(allowed)!r}"
    return None


def validate_add_slide_layouts(
    operations: list,
    allowed_layouts: list[str] | None,
) -> str | None:
    """Require allowed_layouts when add_slide is used (ADR-016)."""
    add_ops = [op for op in operations if getattr(op, "op", None) == "add_slide"]
    if not add_ops:
        return None
    if not allowed_layouts:
        return (
            "options.allowed_layouts is required when operations include add_slide "
            "(copy layouts[] from office_read_presentation fine read, ADR-016)"
        )
    allowed = set(allowed_layouts)
    for op in add_ops:
        layout = op.layout
        if layout not in allowed:
            return f"add_slide layout {layout!r} not in allowed layouts {sorted(allowed)!r}"
    return None


def validate_merge_separator_layout(options) -> str | None:
    """Require separator_layout + allowed_layouts when separator_slide is enabled (ADR-042)."""
    if not getattr(options, "separator_slide", False):
        return None
    allowed_layouts = getattr(options, "allowed_layouts", None)
    if not allowed_layouts:
        return (
            "options.allowed_layouts is required when separator_slide is true "
            "(copy layouts[] from office_read_presentation fine read, ADR-016)"
        )
    separator_layout = getattr(options, "separator_layout", None)
    if not separator_layout:
        return "options.separator_layout is required when separator_slide is true"
    allowed = set(allowed_layouts)
    if separator_layout not in allowed:
        return f"separator_layout {separator_layout!r} not in allowed layouts {sorted(allowed)!r}"
    return None
