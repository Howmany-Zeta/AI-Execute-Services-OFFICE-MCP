"""Pydantic schemas for office_read_presentation."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class PresentationReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    slide_range: tuple[int, int] | None = None
    include_notes: bool = False
    include_layout_meta: bool = False
    allow_coarse_fallback: bool = True

    @field_validator("slide_range", mode="before")
    @classmethod
    def coerce_slide_range(cls, value: object) -> tuple[int, int] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return int(value[0]), int(value[1])
        return value  # type: ignore[return-value]


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


PRESENTATION_READ_INPUT_SCHEMA: dict = PresentationReadArgs.model_json_schema()
PRESENTATION_READ_INPUT_SCHEMA.pop("title", None)
