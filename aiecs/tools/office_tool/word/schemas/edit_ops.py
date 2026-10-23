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
    "set_run_format",
    "set_paragraph_format",
    "set_list",
    "set_cell_text",
    "insert_table_row",
    "delete_table_row",
    "insert_table_column",
    "delete_table_column",
    "delete_table",
    "set_header",
    "set_footer",
    "insert_image",
    "replace_image",
    "set_hyperlink",
    "remove_hyperlink",
    "move_block",
    "set_section",
    "insert_footnote",
    "set_footnote_text",
    "delete_footnote",
    "insert_comment",
    "set_comment",
    "delete_comment",
    "insert_caption",
    "insert_chart",
    "set_chart_data",
    "insert_textbox",
    "set_textbox_geometry",
]

AlignName = Literal["left", "center", "right", "justify"]
ListTypeName = Literal["bullet", "number"]
HeaderVariant = Literal["default", "first", "even"]
BreakTypeName = Literal["next", "continuous", "even", "odd"]
NoteTypeName = Literal["footnote", "endnote"]
_DELETE_BLOCK_OK = frozenset({"page_break", "textbox", "chart", "caption", "image", None})


class PageNumberSpec(BaseModel):
    position: Literal["left", "center", "right"] | None = None
    format: str | None = None
    start: int | None = None


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
    run_index: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    col: int | None = Field(default=None, ge=0)
    list_type: ListTypeName | None = None
    list_level: int | None = Field(default=None, ge=0)
    heading_level: int | None = Field(default=None, ge=1, le=6)
    section_index: int | None = Field(default=None, ge=0)
    variant: HeaderVariant | None = None
    page_number: PageNumberSpec | None = None
    url: str | None = None
    content_base64: str | None = None
    alt: str | None = None
    width_pt: float | None = Field(default=None, gt=0)
    height_pt: float | None = Field(default=None, gt=0)
    image_index: int | None = Field(default=None, ge=0)
    to_block_index: int | None = Field(default=None, ge=0)
    font_name: str | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    highlight: str | None = None
    font_color: str | None = None
    align: AlignName | None = None
    break_type: BreakTypeName | None = None
    columns: int | None = Field(default=None, ge=1)
    different_first_page: bool | None = None
    odd_even_headers: bool | None = None
    footnote_id: str | None = None
    comment_id: str | None = None
    type: NoteTypeName | None = None
    chart_type: str | None = None
    x_pt: float | None = None
    y_pt: float | None = None
    target_block_index: int | None = Field(default=None, ge=0)

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
            if self.op == "delete_block" and self.block_type not in _DELETE_BLOCK_OK:
                raise ValueError(
                    "delete_block may target page_break, textbox, chart, caption, or image"
                )
            if self.op == "apply_style" and not self.style_name:
                raise ValueError("apply_style requires style_name")
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
        elif self.op == "set_run_format":
            if self.block_index is None and not self.match_text:
                raise ValueError("set_run_format requires block_index or match_text")
            if (
                self.bold is None
                and self.italic is None
                and self.underline is None
                and self.strike is None
                and self.highlight is None
                and self.font_color is None
                and not self.font_name
                and self.font_size_pt is None
            ):
                raise ValueError(
                    "set_run_format requires bold, italic, underline, strike, highlight, "
                    "font_name, font_size_pt, or font_color"
                )
        elif self.op == "set_paragraph_format":
            if self.block_index is None and not self.match_text and not self.heading_path:
                raise ValueError("set_paragraph_format requires block_index, match_text, or heading_path")
            if self.align is None and not self.style_name:
                raise ValueError("set_paragraph_format requires align or style_name")
        elif self.op == "set_list":
            if self.block_index is None and not self.match_text and not self.heading_path:
                raise ValueError("set_list requires block_index, match_text, or heading_path")
            if self.list_type is None and self.list_level is None:
                raise ValueError("set_list requires list_type or list_level")
        elif self.op == "set_cell_text":
            if self.block_index is None or self.row is None or self.col is None or self.text is None:
                raise ValueError("set_cell_text requires block_index, row, col, and text")
        elif self.op in ("insert_table_row", "delete_table_row"):
            if self.block_index is None or self.row is None:
                raise ValueError(f"{self.op} requires block_index and row")
        elif self.op in ("insert_table_column", "delete_table_column"):
            if self.block_index is None or self.col is None:
                raise ValueError(f"{self.op} requires block_index and col")
        elif self.op == "delete_table":
            if self.block_index is None:
                raise ValueError("delete_table requires block_index")
        elif self.op in ("set_header", "set_footer"):
            if self.text is None and self.page_number is None:
                raise ValueError(f"{self.op} requires text or page_number")
        elif self.op == "set_section":
            if self.section_index is None:
                raise ValueError("set_section requires section_index")
            if (
                self.columns is None
                and self.different_first_page is None
                and self.odd_even_headers is None
            ):
                raise ValueError(
                    "set_section requires columns, different_first_page, or odd_even_headers"
                )
        elif self.op == "insert_footnote":
            if self.block_index is None or self.run_index is None:
                raise ValueError("insert_footnote requires block_index and run_index")
            if self.text is None:
                raise ValueError("insert_footnote requires text")
        elif self.op == "set_footnote_text":
            if not self.footnote_id or self.text is None:
                raise ValueError("set_footnote_text requires footnote_id and text")
        elif self.op == "delete_footnote":
            if not self.footnote_id:
                raise ValueError("delete_footnote requires footnote_id")
        elif self.op == "insert_comment":
            if self.block_index is None or self.text is None:
                raise ValueError("insert_comment requires block_index and text")
        elif self.op == "set_comment":
            if not self.comment_id or self.text is None:
                raise ValueError("set_comment requires comment_id and text")
        elif self.op == "delete_comment":
            if not self.comment_id:
                raise ValueError("delete_comment requires comment_id")
        elif self.op == "insert_caption":
            if self.text is None:
                raise ValueError("insert_caption requires text")
        elif self.op == "insert_chart":
            if not self.chart_type or not self.rows:
                raise ValueError("insert_chart requires chart_type and rows")
        elif self.op == "set_chart_data":
            if self.block_index is None or not self.rows:
                raise ValueError("set_chart_data requires block_index and rows")
        elif self.op == "insert_textbox":
            if self.width_pt is None or self.height_pt is None:
                raise ValueError("insert_textbox requires width_pt and height_pt")
        elif self.op == "set_textbox_geometry":
            if self.block_index is None:
                raise ValueError("set_textbox_geometry requires block_index")
            if (
                self.x_pt is None
                and self.y_pt is None
                and self.width_pt is None
                and self.height_pt is None
            ):
                raise ValueError("set_textbox_geometry requires x_pt, y_pt, width_pt, or height_pt")
        elif self.op == "insert_image":
            if not self.url and not self.content_base64:
                raise ValueError("insert_image requires url or content_base64")
        elif self.op == "replace_image":
            if self.block_index is None and self.image_index is None:
                raise ValueError("replace_image requires block_index or image_index")
            if not self.url and not self.content_base64:
                raise ValueError("replace_image requires url or content_base64")
        elif self.op == "set_hyperlink":
            if self.block_index is None or self.run_index is None or not self.url:
                raise ValueError("set_hyperlink requires block_index, run_index, and url")
        elif self.op == "remove_hyperlink":
            if self.block_index is None or self.run_index is None:
                raise ValueError("remove_hyperlink requires block_index and run_index")
        elif self.op == "move_block":
            if self.block_index is None:
                raise ValueError("move_block requires block_index")
            if self.to_block_index is None and not self.heading_path:
                raise ValueError("move_block requires to_block_index or heading_path")
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
                "set_run_format",
                "set_paragraph_format",
                "set_list",
                "set_cell_text",
                "insert_table_row",
                "delete_table_row",
                "insert_table_column",
                "delete_table_column",
                "delete_table",
                "set_header",
                "set_footer",
                "insert_image",
                "replace_image",
                "set_hyperlink",
                "remove_hyperlink",
                "move_block",
                "set_section",
                "insert_footnote",
                "set_footnote_text",
                "delete_footnote",
                "insert_comment",
                "set_comment",
                "delete_comment",
                "insert_caption",
                "insert_chart",
                "set_chart_data",
                "insert_textbox",
                "set_textbox_geometry",
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
        "run_index": {"type": "integer", "minimum": 0},
        "row": {"type": "integer", "minimum": 0},
        "col": {"type": "integer", "minimum": 0},
        "list_type": {"type": "string", "enum": ["bullet", "number"]},
        "list_level": {"type": "integer", "minimum": 0},
        "heading_level": {"type": "integer", "minimum": 1, "maximum": 6},
        "section_index": {"type": "integer", "minimum": 0},
        "variant": {"type": "string", "enum": ["default", "first", "even"]},
        "page_number": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["left", "center", "right"]},
                "format": {"type": "string"},
                "start": {"type": "integer"},
            },
        },
        "url": {"type": "string"},
        "content_base64": {"type": "string"},
        "alt": {"type": "string"},
        "width_pt": {"type": "number"},
        "height_pt": {"type": "number"},
        "image_index": {"type": "integer", "minimum": 0},
        "to_block_index": {"type": "integer", "minimum": 0},
        "font_name": {"type": "string"},
        "font_size_pt": {"type": "number"},
        "bold": {"type": "boolean"},
        "italic": {"type": "boolean"},
        "underline": {"type": "boolean"},
        "strike": {"type": "boolean"},
        "highlight": {"type": "string"},
        "font_color": {"type": "string"},
        "align": {"type": "string", "enum": ["left", "center", "right", "justify"]},
        "break_type": {"type": "string", "enum": ["next", "continuous", "even", "odd"]},
        "columns": {"type": "integer", "minimum": 1},
        "different_first_page": {"type": "boolean"},
        "odd_even_headers": {"type": "boolean"},
        "footnote_id": {"type": "string"},
        "comment_id": {"type": "string"},
        "type": {"type": "string", "enum": ["footnote", "endnote"]},
        "chart_type": {"type": "string"},
        "x_pt": {"type": "number"},
        "y_pt": {"type": "number"},
        "target_block_index": {"type": "integer", "minimum": 0},
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
