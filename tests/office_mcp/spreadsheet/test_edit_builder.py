"""Tests for spreadsheet/builder/edit.py and merge.py script generation."""

from aiecs.tools.office_tool.spreadsheet.builder.edit import build_edit_script
from aiecs.tools.office_tool.spreadsheet.builder.merge import build_merge_script
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import EditOperation


class TestBuildEditScript:
    def test_copy_sheet_by_name_with_new_name(self):
        ops = [
            EditOperation(op="copy_sheet", sheet_name="Summary", new_name="Summary Copy"),
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert 'Api.GetSheetByName("Summary")' in script
        assert "var copiedSheet =" in script
        assert "Copy(Api.GetActiveSheet())" in script
        assert "Copy(ws)" not in script
        assert 'copiedSheet.SetName("Summary Copy")' in script

    def test_copy_sheet_by_index_without_new_name(self):
        ops = [EditOperation(op="copy_sheet", sheet_index=0)]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "Api.GetSheet(0)" in script
        assert "Copy(Api.GetActiveSheet())" in script
        assert "SetName" not in script

    def test_set_cell_uses_json_literals(self):
        ops = [
            EditOperation(
                op="set_cell",
                sheet_name="Data",
                cell="A1",
                value='He said "hello"\nline2',
            )
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert script.count("SetValue(") == 1
        assert "He said \\\"hello\\\"\\nline2" in script
        assert "SetValue('He said" not in script

    def test_insert_rows_with_values(self):
        ops = [
            EditOperation(
                op="insert_rows",
                sheet_name="Data",
                at_row=5,
                count=1,
                values=[["a", "b"]],
            )
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "InsertRows(4, 1)" in script
        assert "SetValue" in script

    def test_add_sheet_matches_create_api(self):
        ops = [EditOperation(op="add_sheet", name="Notes")]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "Api.AddSheet();" in script
        assert 'Api.AddSheet("Notes")' not in script
        assert "GetSheetsCount() - 1" in script
        assert 'SetName("Notes")' in script

    def test_sheet_name_wins_when_both_locators_set(self):
        ops = [
            EditOperation(
                op="set_cell",
                sheet_name="Summary",
                sheet_index=3,
                cell="A1",
                value=1,
            )
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert 'Api.GetSheetByName("Summary")' in script
        assert "Api.GetSheet(3)" not in script

    def test_clear_range_sets_empty_value(self):
        ops = [EditOperation(op="clear_range", range="A1:B2", sheet_index=0)]
        script = build_edit_script(ops, file_ext="xlsx")
        assert 'SetValue("")' in script
        assert ".Clear()" not in script

    def test_set_cell_style_emits_format_not_value(self):
        ops = [
            EditOperation.model_validate(
                {
                    "op": "set_cell_style",
                    "sheet_name": "Data",
                    "cell": "B3",
                    "bold": True,
                    "border_left": "thin",
                }
            )
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "SetBold(true)" in script
        assert "SetBorders" in script
        assert "SetValue" not in script
        assert "SetItalic" not in script

    def test_set_cell_style_null_clears_field(self):
        ops = [
            EditOperation.model_validate(
                {
                    "op": "set_cell_style",
                    "cell": "A1",
                    "bold": None,
                    "fill_color": None,
                }
            )
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "SetBold(false)" in script
        assert "CreateNoFill()" in script
        assert "SetItalic" not in script

    def test_clear_format_does_not_set_value(self):
        ops = [EditOperation(op="clear_format", range="A1:B2", sheet_index=0)]
        script = build_edit_script(ops, file_ext="xlsx")
        assert "SetNumberFormat" in script
        assert "SetBold(false)" in script
        assert "SetValue" not in script

    def test_column_width_and_row_height_emit_range(self):
        ops = [
            EditOperation(op="set_column_width", column="B", width_pt=72, sheet_index=0),
            EditOperation(op="set_row_height", sheet_row=5, height_pt=18, sheet_index=0),
        ]
        script = build_edit_script(ops, file_ext="xlsx")
        assert 'GetRange("B:B").SetColumnWidth(72.0)' in script
        assert 'GetRange("5:5").SetRowHeight(18.0)' in script


class TestBuildMergeScript:
    def test_rename_conflicts_true_emits_suffix_resolver(self):
        script = build_merge_script(
            ["https://a/a.xlsx", "https://a/b.xlsx"],
            ["xlsx", "xlsx"],
            output_path="gs://b/merged.xlsx",
            rename_conflicts=True,
        )
        assert "_resolveMergeSheetName" in script
        assert 'name + "_" + n' in script
        assert "copied.SetName(targetName)" in script
        assert "GlobalVariable" not in script

    def test_rename_conflicts_false_emits_conflict_error(self):
        script = build_merge_script(
            ["https://a/a.xlsx"],
            ["xlsx"],
            output_path="gs://b/merged.xlsx",
            rename_conflicts=False,
        )
        assert "Sheet name conflict" in script
        assert "_resolveMergeSheetName(name, false)" in script
