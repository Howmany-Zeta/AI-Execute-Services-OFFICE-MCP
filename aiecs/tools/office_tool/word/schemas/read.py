"""Pydantic schemas for office_read_word."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aiecs.tools.office_tool.core.caller_io import CallerSourceMixin


class WordReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    include_tables: bool = True
    max_blocks: int | None = Field(default=None, ge=1)


class WordReadArgs(CallerSourceMixin):
    format: Literal["structured", "outline", "text"] = "structured"
    options: WordReadOptions = Field(default_factory=WordReadOptions)
