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
    "set_run_format",
    "set_shape_geometry",
    "set_paragraph_format",
    "insert_textbox",
]

AlignName = Literal["left", "center", "right", "justify"]


def _require_slide_or_layout(op: EditOperation) -> None:
    has_slide = op.slide_index is not None
    has_layout = bool(op.layout_name)
    if has_slide == has_layout:
        raise ValueError(f"{op.op} requires slide_index or layout_name")


class EditOperation(BaseModel):
    op: OpName
    slide_index: int | None = Field(default=None, ge=0)
    shape_index: int | None = Field(default=None, ge=0)
    layout_name: str | None = None
    match_text: str | None = None
    role: Literal["title", "body", "subtitle"] | None = None
    text: str | None = None
    title: str | None = None
    subtitle: str | None = None
    items: list[str] | None = None
    after_index: int | None = Field(default=None, ge=-1)
    from_index: int | None = Field(default=None, ge=0)
    to_index: int | None = Field(default=None, ge=0)
    layout: str | None = None
    url: str | None = None
    run_index: int | None = Field(default=None, ge=0)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font_name: str | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    align: AlignName | None = None
    x_pt: float | None = None
    y_pt: float | None = None
    width_pt: float | None = Field(default=None, gt=0)
    height_pt: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op in ("set_text", "remove_shape", "replace_image"):
            _require_slide_or_layout(self)
            if self.op == "set_text" and not self.text:
                raise ValueError("set_text requires text")
            if self.op == "replace_image" and not self.url:
                raise ValueError("replace_image requires url")
            if self.shape_index is None and not self.match_text and not self.role:
                raise ValueError(f"{self.op} requires shape_index, match_text, or role")
        elif self.op == "set_run_format":
            _require_slide_or_layout(self)
            if self.shape_index is None or self.run_index is None:
                raise ValueError("set_run_format requires shape_index and run_index")
            if (
                self.bold is None
                and self.italic is None
                and self.underline is None
                and not self.font_name
                and self.font_size_pt is None
            ):
                raise ValueError(
                    "set_run_format requires bold, italic, underline, font_name, or font_size_pt"
                )
        elif self.op == "set_shape_geometry":
            _require_slide_or_layout(self)
            if self.shape_index is None:
                raise ValueError("set_shape_geometry requires shape_index")
            if (
                self.x_pt is None
                and self.y_pt is None
                and self.width_pt is None
                and self.height_pt is None
            ):
                raise ValueError("set_shape_geometry requires x_pt, y_pt, width_pt, or height_pt")
        elif self.op == "set_paragraph_format":
            _require_slide_or_layout(self)
            if self.shape_index is None:
                raise ValueError("set_paragraph_format requires shape_index")
            if self.align is None:
                raise ValueError("set_paragraph_format requires align")
        elif self.op == "insert_textbox":
            _require_slide_or_layout(self)
            if self.width_pt is None or self.height_pt is None:
                raise ValueError("insert_textbox requires width_pt and height_pt")
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


def _model_mcp_item_schema(model: type[BaseModel]) -> dict:
    """JSON Schema for MCP tool items; strips document title, keeps property fields."""
    schema = model.model_json_schema()
    schema.pop("$defs", None)
    if schema.get("title") == model.__name__:
        schema.pop("title", None)
    return schema


EDIT_OPERATION_ITEM_SCHEMA: dict = _model_mcp_item_schema(EditOperation)


class PresentationEditOptions(BaseModel):
    backup: bool = False
    allowed_layouts: list[str] | None = None


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


PRESENTATION_EDIT_INPUT_SCHEMA: dict = PresentationEditArgs.model_json_schema()
if PRESENTATION_EDIT_INPUT_SCHEMA.get("title") == PresentationEditArgs.__name__:
    PRESENTATION_EDIT_INPUT_SCHEMA.pop("title", None)


class PresentationMergeOptions(BaseModel):
    separator_slide: bool = False
    separator_layout: str | None = None
    allowed_layouts: list[str] | None = None

    @model_validator(mode="after")
    def separator_layout_fields(self) -> Self:
        if not self.separator_slide:
            return self
        if not self.allowed_layouts:
            raise ValueError(
                "options.allowed_layouts is required when separator_slide is true "
                "(copy layouts[] from office_read_presentation fine read, ADR-016)"
            )
        if not self.separator_layout:
            raise ValueError("options.separator_layout is required when separator_slide is true")
        allowed = set(self.allowed_layouts)
        if self.separator_layout not in allowed:
            raise ValueError(
                f"separator_layout {self.separator_layout!r} not in allowed layouts {sorted(allowed)!r}"
            )
        return self


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
