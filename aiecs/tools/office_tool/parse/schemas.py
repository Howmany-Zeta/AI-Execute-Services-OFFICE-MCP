"""Pydantic schemas for office_parse_document (ADR-048)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


class ParseDocumentOptions(BaseModel):
    page_range: tuple[int, int] | None = None
    inline_max_bytes: int = Field(default=1_048_576, ge=1)
    include_inline: bool = False


class ParseDocumentArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    engine: Literal["auto", "document_ai", "documentserver"] = "auto"
    output_format: list[Literal["markdown", "text", "structured"]] | Literal["markdown", "text", "structured"] = Field(
        default_factory=lambda: ["markdown", "structured"]
    )
    output_path: str
    callback_url: str | None = None
    options: ParseDocumentOptions = Field(default_factory=ParseDocumentOptions)

    @model_validator(mode="after")
    def source_and_output(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not path and not url:
            raise ValueError("Provide source_path or source_url")
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self


class ParseStatusArgs(BaseModel):
    job_id: str
    job_secret: str
    include_inline: bool = False
    inline_max_bytes: int = Field(default=1_048_576, ge=1)
