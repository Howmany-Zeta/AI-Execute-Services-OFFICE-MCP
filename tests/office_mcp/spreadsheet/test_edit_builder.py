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
