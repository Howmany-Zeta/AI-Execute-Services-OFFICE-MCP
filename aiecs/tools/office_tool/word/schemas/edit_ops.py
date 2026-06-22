"""Pydantic schemas for office_edit_word operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

OpName = Literal[
    "search_replace",
    "set_block_text",
    "set_heading",
    "insert_paragraph",
    "insert_bullets",
    "insert_table",
    "delete_block",
    "apply_style",
    "add_page_break",
    "insert_section_break",
    "insert_toc",
]


class EditOperation(BaseModel):
    op: OpName
    search_string: str | None = None
    replace_string: str | None = None
    block_index: int | None = Field(default=None, ge=0)
    heading_path: list[str] | None = None
    match_text: str | None = None
    text: str | None = None
    style_name: str | None = None
    items: list[str] | None = None
    rows: list[list[str]] | None = None
    after: str | Literal["start", "end"] | None = None
    block_type: str | None = None
    scope: Literal["document", "subtree"] | None = None

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op == "search_replace":
            if not self.search_string:
                raise ValueError("search_replace requires search_string")
            if self.scope == "subtree" and self.block_index is None and not self.match_text and not self.heading_path:
                raise ValueError("search_replace scope=subtree requires block_index, match_text, or heading_path")
        elif self.op in ("set_block_text", "delete_block", "apply_style"):
            if self.block_index is None and not self.match_text and not self.heading_path:
                raise ValueError(f"{self.op} requires block_index, match_text, or heading_path")
            if self.op == "delete_block" and self.block_type == "table":
                raise ValueError("delete_block on table blocks is not supported (ADR-010)")
        elif self.op == "set_heading":
            if not self.text:
                raise ValueError("set_heading requires text")
        elif self.op == "insert_paragraph":
            if not self.text:
                raise ValueError("insert_paragraph requires text")
        elif self.op == "insert_bullets":
            if not self.items:
                raise ValueError("insert_bullets requires items")
        elif self.op == "insert_table":
            if not self.rows:
                raise ValueError("insert_table requires rows")
        elif self.op == "apply_style":
            if not self.style_name:
                raise ValueError("apply_style requires style_name")
        return self

    @model_validator(mode="after")
    def no_relative_index(self) -> Self:
        if "relative_index" in self.model_dump():
            raise ValueError("relative_index is not supported (ADR-011)")
        return self


EDIT_OPERATION_ITEM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "op": {
            "type": "string",
            "enum": [
                "search_replace",
                "set_block_text",
                "set_heading",
                "insert_paragraph",
                "insert_bullets",
                "insert_table",
                "delete_block",
                "apply_style",
                "add_page_break",
                "insert_section_break",
                "insert_toc",
            ],
        },
        "search_string": {"type": "string"},
        "replace_string": {"type": "string"},
        "scope": {"type": "string", "enum": ["document", "subtree"]},
        "block_index": {"type": "integer", "minimum": 0},
        "heading_path": {"type": "array", "items": {"type": "string"}},
        "match_text": {"type": "string"},
        "text": {"type": "string"},
        "style_name": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "after": {"type": "string", "description": "insert position: start, end, or heading snippet"},
        "block_type": {"type": "string"},
    },
    "required": ["op"],
}


class WordEditOptions(BaseModel):
    backup: bool = False


class WordEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: WordEditOptions = Field(default_factory=WordEditOptions)

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
