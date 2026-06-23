"""Pydantic schemas for office_create_spreadsheet."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SheetSpec(BaseModel):
    name: str = Field(min_length=1, max_length=31)
    rows: list[list[Any]] = Field(min_length=1)
    header_row: bool = False


class SpreadsheetCreateArgs(BaseModel):
    sheets: list[SheetSpec] = Field(min_length=1)
    output_path: str


SPREADSHEET_CREATE_INPUT_SCHEMA: dict = SpreadsheetCreateArgs.model_json_schema()
SPREADSHEET_CREATE_INPUT_SCHEMA.pop("title", None)
