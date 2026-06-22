"""Pydantic schemas for office_read_word."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class WordReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    include_tables: bool = True
    max_blocks: int | None = Field(default=None, ge=1)


class WordReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: WordReadOptions = Field(default_factory=WordReadOptions)

    @model_validator(mode="after")
    def exactly_one_source(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not path and not url:
            raise ValueError("Provide source_path or source_url")
        return self
