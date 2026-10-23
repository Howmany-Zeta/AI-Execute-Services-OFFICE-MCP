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
    "set_block_text",
    "set_cell_text",
    "set_paragraph_format",
    "replace_image",
    "set_bookmark",
    "delete_bookmark",
    "set_annotation",
]

AlignName = Literal["left", "center", "right", "justify"]


def _model_mcp_item_schema(model: type[BaseModel]) -> dict:
    """JSON Schema for MCP operations[] items; keep $defs for nested BlockSpec."""
    schema = model.model_json_schema()
    if schema.get("title") == model.__name__:
        schema.pop("title", None)
    return schema


class EditOperation(BaseModel):
    op: OpName
    page_index: int | None = Field(default=None, ge=0)
    after_index: int | None = Field(default=None, ge=-1)
    text: str | None = None
    align: AlignName | None = None
    bold: bool | None = None
    font_name: str | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    blocks: list[BlockSpec] | None = None
    degrees: Literal[90, 180, 270] | None = None
    kind: Literal["freetext", "highlight"] | None = None
    rect: dict[str, float] | None = None
    block_index: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    col: int | None = Field(default=None, ge=0)
    rows: list[list[str]] | None = None
    url: str | None = None
    content_base64: str | None = None
    image_index: int | None = Field(default=None, ge=0)
    bookmark_id: str | None = None
    annotation_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op == "add_paragraph":
            if self.page_index is None or not self.text:
                raise ValueError("add_paragraph requires page_index and text")
        elif self.op == "set_page_text":
            if self.page_index is None:
                raise ValueError("set_page_text requires page_index")
            if not self.blocks:
                raise ValueError("set_page_text requires blocks")
        elif self.op == "delete_page":
            if self.page_index is None:
                raise ValueError("delete_page requires page_index")
        elif self.op == "rotate_page":
            if self.page_index is None or self.degrees is None:
                raise ValueError("rotate_page requires page_index and degrees")
        elif self.op == "add_annotation":
            if self.page_index is None or not self.text or not self.rect:
                raise ValueError("add_annotation requires page_index, text, and rect")
        elif self.op == "set_block_text":
            if self.page_index is None or self.block_index is None:
                raise ValueError("set_block_text requires page_index and block_index")
            if self.text is None and not self.rows:
                raise ValueError("set_block_text requires text or rows")
        elif self.op == "set_cell_text":
            if (
                self.page_index is None
                or self.block_index is None
                or self.row is None
                or self.col is None
                or self.text is None
            ):
                raise ValueError("set_cell_text requires page_index, block_index, row, col, and text")
        elif self.op == "set_paragraph_format":
            if self.page_index is None or self.block_index is None:
                raise ValueError("set_paragraph_format requires page_index and block_index")
            if (
                self.align is None
                and self.bold is None
                and not self.font_name
                and self.font_size_pt is None
            ):
                raise ValueError(
                    "set_paragraph_format requires align, bold, font_name, or font_size_pt"
                )
        elif self.op == "replace_image":
            if self.page_index is None:
                raise ValueError("replace_image requires page_index")
            if self.block_index is None and self.image_index is None:
                raise ValueError("replace_image requires block_index or image_index")
            if not self.url and not self.content_base64:
                raise ValueError("replace_image requires url or content_base64")
        elif self.op == "set_bookmark":
            if not self.bookmark_id:
                raise ValueError("set_bookmark requires bookmark_id")
        elif self.op == "delete_bookmark":
            if not self.bookmark_id:
                raise ValueError("delete_bookmark requires bookmark_id")
        elif self.op == "set_annotation":
            if self.page_index is None or self.annotation_index is None:
                raise ValueError("set_annotation requires page_index and annotation_index")
            if self.text is None and self.rect is None and self.kind is None:
                raise ValueError("set_annotation requires text, rect, or kind")
        return self


EDIT_OPERATION_ITEM_SCHEMA: dict = _model_mcp_item_schema(EditOperation)


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
