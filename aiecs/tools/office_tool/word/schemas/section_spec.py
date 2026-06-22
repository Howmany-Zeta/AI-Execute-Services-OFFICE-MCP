"""Pydantic schemas for create, merge, template, and edit_script tools."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

SectionType = Literal[
    "heading1",
    "heading2",
    "heading3",
    "paragraph",
    "bullets",
    "table",
    "page_break",
]


class SectionSpec(BaseModel):
    type: SectionType
    text: str | None = None
    bold: bool = False
    items: list[str] | None = None
    level: int = Field(default=1, ge=1, le=9)
    rows: list[list[str]] | None = None
    header_row: bool = False

    @model_validator(mode="after")
    def type_fields(self) -> Self:
        if self.type in ("heading1", "heading2", "heading3", "paragraph") and not (self.text or "").strip():
            raise ValueError(f"{self.type} requires text")
        if self.type == "bullets" and not self.items:
            raise ValueError("bullets requires items")
        if self.type == "table" and not self.rows:
            raise ValueError("table requires rows")
        return self


class WordCreateOptions(BaseModel):
    title: str | None = None
    page_size: Literal["A4", "Letter"] | None = None
    add_toc: bool = False


class WordCreateArgs(BaseModel):
    sections: list[SectionSpec] = Field(min_length=1)
    output_path: str
    options: WordCreateOptions = Field(default_factory=WordCreateOptions)


class WordMergeOptions(BaseModel):
    add_page_break: bool = False
    add_toc: bool = False


class WordMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: WordMergeOptions = Field(default_factory=WordMergeOptions)

    @model_validator(mode="after")
    def paths_xor_urls(self) -> Self:
        paths = self.source_paths or []
        urls = self.source_urls or []
        if paths and urls:
            raise ValueError("Provide source_paths OR source_urls, not both")
        if not paths and not urls:
            raise ValueError("Provide source_paths or source_urls")
        return self


class WordTemplateArgs(BaseModel):
    template_path: str | None = None
    template_url: str | None = None
    data: dict[str, Any]
    output_path: str

    @model_validator(mode="after")
    def template_source(self) -> Self:
        path = (self.template_path or "").strip()
        url = (self.template_url or "").strip()
        if path and url:
            raise ValueError("Provide template_path OR template_url, not both")
        if not path and not url:
            raise ValueError("Provide template_path or template_url")
        return self


class WordEditScriptOptions(BaseModel):
    backup: bool = False


class WordEditScriptArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    edit_script: str
    output_path: str
    options: WordEditScriptOptions = Field(default_factory=WordEditScriptOptions)

    @model_validator(mode="after")
    def source_and_script(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        if path and url:
            raise ValueError("Provide source_path OR source_url, not both")
        if not (self.edit_script or "").strip():
            raise ValueError("edit_script is required")
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self
