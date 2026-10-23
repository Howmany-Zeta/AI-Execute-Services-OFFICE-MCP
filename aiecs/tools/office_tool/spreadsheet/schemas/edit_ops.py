"""Pydantic schemas for office_edit_spreadsheet (ADR-015: A1/range only)."""

from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

OpName = Literal[
    "set_cell",
    "set_range",
    "clear_range",
    "clear_format",
    "set_cell_style",
    "set_column_width",
    "set_row_height",
    "insert_rows",
    "delete_rows",
    "add_sheet",
    "delete_sheet",
    "rename_sheet",
    "set_formula",
    "copy_sheet",
]

BorderStyle = Literal["none", "thin", "medium", "thick"]
AlignH = Literal["left", "center", "right", "justify"]
AlignV = Literal["top", "center", "bottom"]

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
COLUMN_LETTER_RE = re.compile(r"^[A-Za-z]+$")

STYLE_FIELDS = (
    "number_format",
    "fill_color",
    "border_left",
    "border_right",
    "border_top",
    "border_bottom",
    "border_color",
    "bold",
    "italic",
    "underline",
    "strike",
    "font_name",
    "font_size_pt",
    "font_color",
    "align",
    "vertical_align",
)


def _require_hex(field_name: str, value: str) -> None:
    if not HEX_COLOR_RE.match(value):
        raise ValueError(f"{field_name} must be #RRGGBB")


class EditOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: OpName
    sheet_index: int | None = Field(default=None, ge=0)
    sheet_name: str | None = None
    cell: str | None = None
    range: str | None = None
    value: Any | None = None
    values: list[list[Any]] | None = None
    formula: str | None = None
    at_row: int | None = Field(default=None, ge=1)
    from_row: int | None = Field(default=None, ge=1)
    count: int | None = Field(default=None, ge=1)
    name: str | None = None
    new_name: str | None = None
    number_format: str | None = None
    fill_color: str | None = None
    border_left: BorderStyle | None = None
    border_right: BorderStyle | None = None
    border_top: BorderStyle | None = None
    border_bottom: BorderStyle | None = None
    border_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    font_name: str | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    font_color: str | None = None
    align: AlignH | None = None
    vertical_align: AlignV | None = None
    column: str | None = None
    width_pt: float | None = Field(default=None, gt=0)
    sheet_row: int | None = Field(default=None, ge=1)
    height_pt: float | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def reject_row_col(cls, data: Any) -> Any:
        if isinstance(data, dict) and ("row" in data or "col" in data):
            raise ValueError(
                "row/col are deprecated; use cell or range (A1 notation, ADR-015)"
            )
        return data

    @model_validator(mode="after")
    def op_fields(self) -> Self:
        if self.op == "set_cell":
            if not self.cell:
                raise ValueError("set_cell requires cell (A1)")
        elif self.op == "set_range":
            if not self.range:
                raise ValueError("set_range requires range (A1 notation)")
            if not self.values:
                raise ValueError("set_range requires values")
        elif self.op == "clear_range":
            if not self.range:
                raise ValueError("clear_range requires range")
        elif self.op == "clear_format":
            if not self.range:
                raise ValueError("clear_format requires range")
        elif self.op == "set_cell_style":
            if bool(self.cell) == bool(self.range):
                raise ValueError("set_cell_style requires cell or range")
            provided = [name for name in STYLE_FIELDS if name in self.model_fields_set]
            if not provided:
                raise ValueError(
                    "set_cell_style requires bold, italic, underline, strike, "
                    "font_name, font_size_pt, font_color, number_format, fill_color, "
                    "border_left, border_right, border_top, border_bottom, "
                    "border_color, align, or vertical_align"
                )
            for color_field in ("fill_color", "border_color", "font_color"):
                color = getattr(self, color_field)
                if color_field in self.model_fields_set and color is not None:
                    _require_hex(color_field, color)
        elif self.op == "set_column_width":
            if not self.column or not COLUMN_LETTER_RE.match(self.column):
                raise ValueError("set_column_width requires column (letter)")
            if self.width_pt is None:
                raise ValueError("set_column_width requires width_pt")
        elif self.op == "set_row_height":
            if self.sheet_row is None:
                raise ValueError("set_row_height requires sheet_row (1-based)")
            if self.height_pt is None:
                raise ValueError("set_row_height requires height_pt")
        elif self.op == "set_formula":
            if not self.cell or not self.formula:
                raise ValueError("set_formula requires cell and formula")
        elif self.op == "insert_rows":
            if self.at_row is None or not self.count:
                raise ValueError("insert_rows requires at_row (1-based) and count")
            if self.values is not None:
                if len(self.values) != self.count:
                    raise ValueError("insert_rows values row count must match count")
                if not self.values:
                    raise ValueError("insert_rows values must not be empty")
                widths = {len(row) for row in self.values}
                if len(widths) != 1:
                    raise ValueError("insert_rows values rows must have uniform column count")
        elif self.op == "delete_rows":
            if self.from_row is None or not self.count:
                raise ValueError("delete_rows requires from_row (1-based) and count")
        elif self.op == "add_sheet":
            if not self.name:
                raise ValueError("add_sheet requires name")
            if self.sheet_index is not None or self.sheet_name:
                raise ValueError("add_sheet accepts only name")
        elif self.op == "delete_sheet":
            if self.sheet_index is None and not self.sheet_name:
                raise ValueError("delete_sheet requires sheet_index or sheet_name")
        elif self.op == "rename_sheet":
            if not self.sheet_name or not self.new_name:
                raise ValueError("rename_sheet requires sheet_name and new_name")
        elif self.op == "copy_sheet":
            if self.sheet_index is None and not self.sheet_name:
                raise ValueError("copy_sheet requires sheet_index or sheet_name")
        return self


EDIT_OPERATION_ITEM_SCHEMA: dict = EditOperation.model_json_schema()
EDIT_OPERATION_ITEM_SCHEMA.pop("title", None)
EDIT_OPERATION_ITEM_SCHEMA.pop("$defs", None)


class SpreadsheetEditOptions(BaseModel):
    backup: bool = False


class SpreadsheetEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: SpreadsheetEditOptions = Field(default_factory=SpreadsheetEditOptions)

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


class SpreadsheetMergeOptions(BaseModel):
    rename_conflicts: bool = True


class SpreadsheetMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: SpreadsheetMergeOptions = Field(default_factory=SpreadsheetMergeOptions)

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


class SpreadsheetTemplateArgs(BaseModel):
    template_path: str | None = None
    template_url: str | None = None
    data: dict[str, Any]
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
