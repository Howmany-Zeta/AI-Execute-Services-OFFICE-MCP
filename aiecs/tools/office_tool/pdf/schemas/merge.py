"""Pydantic schemas for office_merge_pdfs."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class PdfMergeOptions(BaseModel):
    engine: Literal["builder", "conversion"] = "builder"


class PdfMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: PdfMergeOptions = Field(default_factory=PdfMergeOptions)

    @model_validator(mode="after")
    def sources_required(self) -> Self:
        paths = self.source_paths or []
        urls = self.source_urls or []
        if paths and urls:
            raise ValueError("Provide source_paths OR source_urls, not both")
        if not paths and not urls:
            raise ValueError("Provide source_paths or source_urls")
        count = len(paths) if paths else len(urls)
        if count < 2:
            raise ValueError("merge requires at least 2 sources")
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self
