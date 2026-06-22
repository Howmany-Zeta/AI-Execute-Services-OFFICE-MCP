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
    allowed_layouts: list[str] | None = None


class PresentationCreateArgs(BaseModel):
    slides: list[SlideSpec] = Field(min_length=1)
    output_path: str
    options: PresentationCreateOptions = Field(default_factory=PresentationCreateOptions)


def validate_slides_layouts(
    slides: list[SlideSpec],
    allowed_layouts: list[str] | None,
) -> str | None:
    """
    Reject layouts not in allowed_layouts (ADR-016).
    Returns error message or None if valid.
    """
    if not allowed_layouts:
        return None
    allowed = set(allowed_layouts)
    for i, slide in enumerate(slides):
        if slide.layout not in allowed:
            return f"slide {i}: layout {slide.layout!r} not in allowed layouts {sorted(allowed)!r}"
    return None
