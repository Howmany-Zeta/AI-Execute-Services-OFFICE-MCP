"""Pydantic schemas for office_read_spreadsheet."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class SpreadsheetReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    sheet_names: list[str] | None = None
    max_rows: int | None = Field(default=None, ge=1)
    include_formulas: bool = False
    range: str | None = None


class SpreadsheetReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: SpreadsheetReadOptions = Field(default_factory=SpreadsheetReadOptions)

    @model_validator(mode="after")
    def source_required(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not path and not url:
            raise ValueError("Provide source_path or source_url")
        return self
