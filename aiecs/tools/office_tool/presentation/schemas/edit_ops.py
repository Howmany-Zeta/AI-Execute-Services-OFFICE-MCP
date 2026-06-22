"""Pydantic schemas for office_edit_presentation operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

OpName = Literal[
    "set_text",
    "set_title",
    "set_bullets",
    "add_slide",
    "delete_slide",
    "duplicate_slide",
    "move_slide",
    "set_notes",
    "replace_image",
    "remove_shape",
]


class EditOperation(BaseModel):
    op: OpName
    slide_index: int | None = Field(default=None, ge=0)
    shape_index: int | None = Field(default=None, ge=0)
    match_text: str | None = None
    role: Literal["title", "body", "subtitle"] | None = None
    text: str | None = None
    items: list[str] | None = None
    after_index: int | None = Field(default=None, ge=-1)
    from_index: int | None = Field(default=None, ge=0)
    to_index: int | None = Field(default=None, ge=0)
    layout: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op in ("set_text", "remove_shape", "replace_image"):
            if self.slide_index is None:
                raise ValueError(f"{self.op} requires slide_index")
            if self.op == "set_text" and not self.text:
                raise ValueError("set_text requires text")
            if self.op == "replace_image" and not self.url:
                raise ValueError("replace_image requires url")
            if self.op in ("set_text", "remove_shape", "replace_image"):
                if self.shape_index is None and not self.match_text and not self.role:
                    raise ValueError(f"{self.op} requires shape_index, match_text, or role")
        elif self.op == "set_title":
            if self.slide_index is None or not self.text:
                raise ValueError("set_title requires slide_index and text")
        elif self.op == "set_bullets":
            if self.slide_index is None or not self.items:
                raise ValueError("set_bullets requires slide_index and items")
        elif self.op == "add_slide":
            if not self.layout:
                raise ValueError("add_slide requires layout (ADR-016)")
        elif self.op == "delete_slide":
            if self.slide_index is None:
                raise ValueError("delete_slide requires slide_index")
        elif self.op == "duplicate_slide":
            if self.slide_index is None:
                raise ValueError("duplicate_slide requires slide_index")
        elif self.op == "move_slide":
            if self.from_index is None or self.to_index is None:
                raise ValueError("move_slide requires from_index and to_index")
        elif self.op == "set_notes":
            if self.slide_index is None or self.text is None:
                raise ValueError("set_notes requires slide_index and text")
        return self


class PresentationEditOptions(BaseModel):
    backup: bool = False


class PresentationEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: PresentationEditOptions = Field(default_factory=PresentationEditOptions)

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


class PresentationMergeOptions(BaseModel):
    separator_slide: bool = False


class PresentationMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: PresentationMergeOptions = Field(default_factory=PresentationMergeOptions)

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


class PresentationTemplateArgs(BaseModel):
    template_path: str | None = None
    template_url: str | None = None
    data: dict
    output_path: str

    @model_validator(mode="after")
    def template_required(self) -> Self:
        path = (self.template_path or "").strip()
        url = (self.template_url or "").strip()
        if path and url:
            raise ValueError("Provide template_path OR template_url, not both")
        if not path and not url:
            raise ValueError("Provide template_path or template_url")
        if not (self.output_path or "").strip():
            raise ValueError("output_path is required")
        return self
