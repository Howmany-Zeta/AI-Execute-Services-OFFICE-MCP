"""Pydantic schemas for office_edit_pdf (ADR-030: no fill_form_field)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from aiecs.tools.office_tool.pdf.schemas.page_spec import BlockSpec

OpName = Literal[
    "add_paragraph",
    "set_page_text",
    "add_page",
    "delete_page",
    "rotate_page",
    "add_annotation",
]


class EditOperation(BaseModel):
    op: OpName
    page_index: int | None = Field(default=None, ge=0)
    after_index: int | None = Field(default=None, ge=-1)
    text: str | None = None
    align: Literal["left", "center", "right"] | None = None
    blocks: list[BlockSpec] | None = None
    degrees: Literal[90, 180, 270] | None = None
    kind: Literal["freetext", "highlight"] | None = None
    rect: dict[str, float] | None = None

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op == "add_paragraph":
            if self.page_index is None or not self.text:
                raise ValueError("add_paragraph requires page_index and text")
        elif self.op == "set_page_text":
            if self.page_index is None:
                raise ValueError("set_page_text requires page_index")
        elif self.op == "delete_page":
            if self.page_index is None:
                raise ValueError("delete_page requires page_index")
        elif self.op == "rotate_page":
            if self.page_index is None or self.degrees is None:
                raise ValueError("rotate_page requires page_index and degrees")
        elif self.op == "add_annotation":
            if self.page_index is None or not self.text or not self.rect:
                raise ValueError("add_annotation requires page_index, text, and rect")
        return self


class PdfEditOptions(BaseModel):
    backup: bool = False


class PdfEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: PdfEditOptions = Field(default_factory=PdfEditOptions)

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
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self
