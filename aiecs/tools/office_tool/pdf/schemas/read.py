"""Pydantic schemas for office_read_pdf."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from aiecs.tools.office_tool.core.caller_io import CallerSourceMixin


class PdfReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    engine: Literal["documentserver", "document_ai"] = "documentserver"
    page_range: tuple[int, int] | None = None
    include_form_fields: bool = True
    include_annotations: bool = False


class PdfReadArgs(CallerSourceMixin):
    format: Literal["structured", "outline", "text"] = "structured"
    options: PdfReadOptions = Field(default_factory=PdfReadOptions)
