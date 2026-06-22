"""Pydantic schemas for office_create_spreadsheet."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SheetSpec(BaseModel):
    name: str = Field(min_length=1, max_length=31)
    rows: list[list[Any]] = Field(min_length=1)
    header_row: bool = False


class SpreadsheetCreateOptions(BaseModel):
    default_col_width: float | None = Field(default=None, gt=0)


class SpreadsheetCreateArgs(BaseModel):
    sheets: list[SheetSpec] = Field(min_length=1)
    output_path: str
    options: SpreadsheetCreateOptions = Field(default_factory=SpreadsheetCreateOptions)
