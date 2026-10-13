"""Pydantic schemas for office_read_spreadsheet."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aiecs.tools.office_tool.core.caller_io import CallerSourceMixin


class SpreadsheetReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    sheet_names: list[str] | None = None
    max_rows: int | None = Field(default=None, ge=1)
    include_formulas: bool = False
    range: str | None = None


class SpreadsheetReadArgs(CallerSourceMixin):
    format: Literal["structured", "outline", "text"] = "structured"
    options: SpreadsheetReadOptions = Field(default_factory=SpreadsheetReadOptions)
