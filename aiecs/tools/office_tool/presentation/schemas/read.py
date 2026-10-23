"""Pydantic schemas for office_read_presentation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from aiecs.tools.office_tool.core.caller_io import CallerSourceMixin


class PresentationReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    slide_range: tuple[int, int] | None = None
    include_notes: bool = True
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


class PresentationReadArgs(CallerSourceMixin):
    format: Literal["structured", "outline", "text"] = "structured"
    options: PresentationReadOptions = Field(default_factory=PresentationReadOptions)


PRESENTATION_READ_INPUT_SCHEMA: dict = PresentationReadArgs.model_json_schema()
PRESENTATION_READ_INPUT_SCHEMA.pop("title", None)
