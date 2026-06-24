"""Pydantic schemas for office_create_pdf."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def _model_mcp_item_schema(model: type[BaseModel]) -> dict:
    """JSON Schema for MCP pages[] items; keep $defs for nested BlockSpec."""
    schema = model.model_json_schema()
    if schema.get("title") == model.__name__:
        schema.pop("title", None)
    return schema


class BlockSpec(BaseModel):
    type: Literal["paragraph", "table"] = "paragraph"
    text: str | None = None
    align: Literal["left", "center", "right"] | None = None
    bold: bool = False
    rows: list[list[str]] | None = None


class PageSpec(BaseModel):
    blocks: list[BlockSpec] = Field(min_length=1)


class PdfCreateOptions(BaseModel):
    page_size: Literal["A4", "Letter"] | None = None
    create_mode: Literal["native", "via_docx"] = "native"


class PdfCreateArgs(BaseModel):
    pages: list[PageSpec] = Field(min_length=1)
    output_path: str
    options: PdfCreateOptions = Field(default_factory=PdfCreateOptions)


PAGE_ITEM_SCHEMA: dict = _model_mcp_item_schema(PageSpec)
