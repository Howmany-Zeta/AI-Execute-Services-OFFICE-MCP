"""Pydantic schemas for office_read_presentation."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class PresentationReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    slide_range: tuple[int, int] | None = None
    include_notes: bool = False
    include_layout_meta: bool = False


class PresentationReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: PresentationReadOptions = Field(default_factory=PresentationReadOptions)

    @model_validator(mode="after")
    def source_required(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not path and not url:
            raise ValueError("Provide source_path or source_url")
        return self
