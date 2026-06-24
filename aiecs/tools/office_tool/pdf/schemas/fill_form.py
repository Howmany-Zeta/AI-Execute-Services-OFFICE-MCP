"""Pydantic schemas for office_fill_pdf_form."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator


class PdfFillFormArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    data: dict
    output_path: str

    @model_validator(mode="after")
    def source_required(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not path and not url:
            raise ValueError("Provide source_path or source_url")
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self
