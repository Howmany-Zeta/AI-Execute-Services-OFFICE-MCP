"""Tests for spreadsheet Pydantic schemas (ADR-015)."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import EditOperation, SpreadsheetEditArgs
from aiecs.tools.office_tool.spreadsheet.schemas.workbook_spec import SheetSpec, SpreadsheetCreateArgs


class TestEditOpsSchema:
    def test_set_cell_requires_a1(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_cell", value=1)

    def test_set_cell_accepts_a1(self):
        op = EditOperation(op="set_cell", cell="B3", value=42, sheet_index=0)
        assert op.cell == "B3"

    def test_set_range_requires_range(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_range", values=[["a"]])

    def test_insert_rows_1based(self):
        op = EditOperation(op="insert_rows", sheet_index=0, at_row=5, count=2)
        assert op.at_row == 5

    def test_edit_args_source_required(self):
        with pytest.raises(ValidationError):
            SpreadsheetEditArgs(
                output_path="gs://b/out.xlsx",
                operations=[{"op": "set_cell", "cell": "A1", "value": 1, "sheet_index": 0}],
            )


class TestWorkbookSpec:
    def test_create_requires_sheets(self):
        with pytest.raises(ValidationError):
            SpreadsheetCreateArgs(sheets=[], output_path="gs://b/out.xlsx")

    def test_sheet_spec(self):
        args = SpreadsheetCreateArgs(
            sheets=[SheetSpec(name="Data", rows=[["a", "b"]])],
            output_path="gs://b/out.xlsx",
        )
        assert args.sheets[0].name == "Data"
