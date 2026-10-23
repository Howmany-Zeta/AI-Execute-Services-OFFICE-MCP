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

    def test_set_cell_rejects_row_col_with_adr015_message(self):
        with pytest.raises(ValidationError, match="row/col are deprecated"):
            EditOperation.model_validate(
                {"op": "set_cell", "sheet_index": 0, "row": 3, "col": 2, "value": 1}
            )

    def test_set_range_requires_range(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_range", values=[["a"]])

    def test_insert_rows_1based(self):
        op = EditOperation(op="insert_rows", sheet_index=0, at_row=5, count=2)
        assert op.at_row == 5

    def test_insert_rows_values_shape(self):
        op = EditOperation(
            op="insert_rows",
            sheet_index=0,
            at_row=5,
            count=2,
            values=[["a", "b"], ["c", "d"]],
        )
        assert op.values is not None

    def test_insert_rows_values_rejects_row_mismatch(self):
        with pytest.raises(ValidationError):
            EditOperation(
                op="insert_rows",
                sheet_index=0,
                at_row=5,
                count=2,
                values=[["a"]],
            )

    def test_add_sheet_rejects_initial_rows(self):
        with pytest.raises(ValidationError):
            EditOperation.model_validate(
                {"op": "add_sheet", "name": "NewSheet", "rows": [["x"]]}
            )

    def test_add_sheet_rejects_sheet_index(self):
        with pytest.raises(ValidationError, match="only name"):
            EditOperation.model_validate({"op": "add_sheet", "name": "NewSheet", "sheet_index": 0})

    def test_set_cell_style_null_vs_omitted(self):
        omitted = EditOperation.model_validate(
            {"op": "set_cell_style", "cell": "A1", "bold": True}
        )
        assert "bold" in omitted.model_fields_set
        assert "italic" not in omitted.model_fields_set
        cleared = EditOperation.model_validate(
            {"op": "set_cell_style", "cell": "A1", "bold": None}
        )
        assert "bold" in cleared.model_fields_set
        assert cleared.bold is None

    def test_set_cell_style_requires_style_field(self):
        with pytest.raises(ValidationError, match="set_cell_style requires"):
            EditOperation.model_validate({"op": "set_cell_style", "cell": "A1"})

    def test_set_cell_style_rejects_bad_color(self):
        with pytest.raises(ValidationError, match="#RRGGBB"):
            EditOperation.model_validate(
                {"op": "set_cell_style", "cell": "A1", "fill_color": "red"}
            )

    def test_clear_format_requires_range(self):
        with pytest.raises(ValidationError, match="clear_format requires range"):
            EditOperation.model_validate({"op": "clear_format", "sheet_index": 0})
        op = EditOperation.model_validate({"op": "clear_format", "range": "A1:B2"})
        assert op.range == "A1:B2"

    def test_set_column_width_and_row_height(self):
        width = EditOperation.model_validate(
            {"op": "set_column_width", "column": "B", "width_pt": 72}
        )
        assert width.column == "B"
        height = EditOperation.model_validate(
            {"op": "set_row_height", "sheet_row": 5, "height_pt": 18}
        )
        assert height.sheet_row == 5
        with pytest.raises(ValidationError):
            EditOperation.model_validate({"op": "set_column_width", "column": "B"})
        with pytest.raises(ValidationError):
            EditOperation.model_validate({"op": "set_row_height", "sheet_row": 5})

    def test_set_row_height_rejects_row_col(self):
        with pytest.raises(ValidationError, match="row/col are deprecated"):
            EditOperation.model_validate(
                {"op": "set_row_height", "row": 5, "height_pt": 18}
            )

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
