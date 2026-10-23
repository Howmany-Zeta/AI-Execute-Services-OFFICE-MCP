"""Tests for spreadsheet/parser/workbook.py."""

import json
from pathlib import Path

import pytest

from aiecs.tools.office_tool.spreadsheet.parser.workbook import (
    apply_max_rows,
    filter_sheet_names,
    parse_a1,
    parse_range,
    parse_workbook_json,
    sheets_to_outline,
    sheets_to_text,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestWorkbookParser:
    def test_parse_workbook_json_multi_sheet(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        assert len(sheets) == 2
        assert sheets[0]["name"] == "Summary"
        assert sheets[0]["rows"][0] == ["Product", "Units", "Price"]
        assert sheets[0]["headers"] == ["Product", "Units", "Price"]
        assert sheets[1]["sheet_index"] == 1
        assert sheets[1]["headers"] == ["Region", "Sales"]

    def test_apply_range_filter_before_max_rows(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import apply_range_filter

        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        clipped = apply_range_filter(sheets, "B1:C2")
        assert clipped[0]["rows"] == [["Units", "Price"], [120, 9.99]]
        assert clipped[0]["headers"] == ["Units", "Price"]
        assert clipped[0]["used_range"] == "B1:C2"
        trimmed, truncated = apply_max_rows(clipped, 1)
        assert truncated is True
        assert trimmed[0]["rows"] == [["Units", "Price"]]
        assert trimmed[0]["headers"] == ["Units", "Price"]

    def test_parse_workbook_json_empty_used_range(self):
        raw = json.loads((FIXTURES / "workbook_empty_sheet_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        assert len(sheets) == 2
        empty = sheets[0]
        assert empty["name"] == "Empty"
        assert empty["rows"] == []
        assert empty["row_count"] == 0
        assert empty["col_count"] == 0
        assert "headers" not in empty
        assert "used_range" not in empty
        assert sheets[1]["headers"] == ["Label", "Value"]

    def test_filter_sheet_names(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        filtered = filter_sheet_names(sheets, ["Summary"])
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Summary"

    def test_filter_sheet_names_keeps_workbook_sheet_index(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        filtered = filter_sheet_names(sheets, ["Details"])
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Details"
        assert filtered[0]["sheet_index"] == 1

    def test_apply_max_rows(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        trimmed, truncated = apply_max_rows(sheets, 2)
        assert truncated is True
        assert trimmed[0]["row_count"] == 2

    def test_parse_a1(self):
        assert parse_a1("A1") == (0, 0)
        assert parse_a1("B2") == (1, 1)
        assert parse_a1("C10") == (9, 2)

    def test_parse_range(self):
        assert parse_range("B2:D5") == (1, 1, 4, 3)

    def test_parse_a1_invalid(self):
        with pytest.raises(ValueError):
            parse_a1("invalid")

    def test_sheets_to_outline(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        outline = sheets_to_outline(sheets)
        assert outline[0]["name"] == "Summary"
        assert "used_range" in outline[0]

    def test_sheets_to_text(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        text = sheets_to_text(sheets)
        assert "--- Summary ---" in text
        assert "Product" in text

    def test_sidecar_body_uses_get_sheets_count(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import (
            WORKBOOK_SIDECAR_EXTRACT_BODY,
            workbook_sidecar_extract_body,
        )

        assert "GetSheetsCount" in WORKBOOK_SIDECAR_EXTRACT_BODY
        assert "Api.GetSheet(_si)" in WORKBOOK_SIDECAR_EXTRACT_BODY
        assert "GetFormula" not in WORKBOOK_SIDECAR_EXTRACT_BODY
        assert "GetFormula" in workbook_sidecar_extract_body(include_formulas=True)
        assert "_readFormula" in workbook_sidecar_extract_body(include_formulas=True)
        assert "_readCell" in workbook_sidecar_extract_body()
        assert "_cellScalar" in workbook_sidecar_extract_body()
        assert "_office_sidecar" in workbook_sidecar_extract_body()
        assert "used.GetValue && used.GetValue(r, c)" not in workbook_sidecar_extract_body()
        assert 'GetRange("A1:Z64")' in workbook_sidecar_extract_body()

    def test_default_sidecar_has_no_sheet_caps(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import workbook_sidecar_extract_body

        default = workbook_sidecar_extract_body()
        assert "2000000" not in default
        assert "6000" not in default
        assert "_usedDims" in default
        limited = workbook_sidecar_extract_body(max_rows=2_000_000, max_cols=6_000, max_output_bytes=1024)
        assert "2000000" in limited
        assert "6000" in limited
        windowed = workbook_sidecar_extract_body(max_rows=12, range="A1:Z12")
        assert 'GetRange("A1:Z12")' in windowed
        assert "if (!rowCount)" in default
        assert "if (r >= 2000000)" in limited
        assert "if (c >= 6000)" in limited
        assert "outBytes" in limited

    def test_truncated_sheet_flag_roundtrip(self):
        sheets = parse_workbook_json({
            "sheets": [{"name": "Big", "rows": [["a"]], "truncated": "rows"}],
        })
        assert sheets[0]["truncated"] == "rows"

    def test_range_filter_uses_used_range_origin(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import apply_range_filter

        sheets = parse_workbook_json({
            "sheets": [
                {
                    "sheet_index": 0,
                    "name": "Offset",
                    "used_range": "B2:D4",
                    "rows": [
                        ["B2", "C2", "D2"],
                        ["B3", "C3", "D3"],
                        ["B4", "C4", "D4"],
                    ],
                }
            ]
        })
        clipped = apply_range_filter(sheets, "C3:D3")
        assert clipped[0]["rows"] == [["C3", "D3"]]
        assert clipped[0]["used_range"] == "C3:D3"
        assert clipped[0]["headers"] == clipped[0]["rows"][0]
        trimmed, truncated = apply_max_rows(clipped, 1)
        assert truncated is False
        assert trimmed[0]["used_range"] == "C3:D3"
        assert trimmed[0]["rows"][0][0] == "C3"

    def test_max_rows_does_not_rewrite_used_range_origin(self):
        sheets = parse_workbook_json({
            "sheets": [
                {
                    "sheet_index": 0,
                    "name": "Offset",
                    "used_range": "B2:D4",
                    "rows": [
                        ["B2", "C2", "D2"],
                        ["B3", "C3", "D3"],
                        ["B4", "C4", "D4"],
                    ],
                }
            ]
        })
        trimmed, truncated = apply_max_rows(sheets, 1)
        assert truncated is True
        assert trimmed[0]["used_range"] == "B2:D4"
        assert trimmed[0]["rows"] == [["B2", "C2", "D2"]]

    def test_parse_styles_drop_defaults_and_keep_sixteen_keys(self):
        sheets = parse_workbook_json({
            "sheets": [
                {
                    "name": "Styled",
                    "used_range": "B2:C3",
                    "rows": [["1", "2"], ["3", "4"]],
                    "cell_styles": [
                        {
                            "cell": "B2",
                            "number_format": "0.00",
                            "fill_color": "#FF0000",
                            "border_left": "thin",
                            "border_right": "none",
                            "border_top": "none",
                            "border_bottom": "none",
                            "border_color": "#000000",
                            "bold": True,
                            "italic": False,
                            "underline": False,
                            "strike": False,
                            "font_name": "Arial",
                            "font_size_pt": 12,
                            "font_color": "#111111",
                            "align": "center",
                            "vertical_align": "top",
                        },
                        {
                            "cell": "C3",
                            "number_format": "",
                            "fill_color": "",
                            "border_left": "none",
                            "border_right": "none",
                            "border_top": "none",
                            "border_bottom": "none",
                            "border_color": "",
                            "bold": False,
                            "italic": False,
                            "underline": False,
                            "strike": False,
                            "font_name": "",
                            "font_size_pt": None,
                            "font_color": "",
                            "align": "left",
                            "vertical_align": "bottom",
                        },
                    ],
                    "column_widths": [{"column": "B", "width_pt": 80}, {"column": "C", "width_pt": 90}],
                    "row_heights": [{"sheet_row": 2, "height_pt": 18}, {"sheet_row": 3, "height_pt": 20}],
                }
            ]
        })
        styles = sheets[0]["cell_styles"]
        assert len(styles) == 1
        assert styles[0]["cell"] == "B2"
        assert set(styles[0]) == {
            "cell",
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
        }

    def test_range_filter_clips_style_arrays(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import apply_range_filter

        sheets = parse_workbook_json({
            "sheets": [
                {
                    "name": "Styled",
                    "used_range": "B2:C3",
                    "rows": [["1", "2"], ["3", "4"]],
                    "cell_styles": [
                        {
                            "cell": "B2",
                            "number_format": "0.00",
                            "fill_color": "",
                            "border_left": "none",
                            "border_right": "none",
                            "border_top": "none",
                            "border_bottom": "none",
                            "border_color": "",
                            "bold": True,
                            "italic": False,
                            "underline": False,
                            "strike": False,
                            "font_name": "",
                            "font_size_pt": None,
                            "font_color": "",
                            "align": "left",
                            "vertical_align": "bottom",
                        },
                        {
                            "cell": "C3",
                            "number_format": "0%",
                            "fill_color": "",
                            "border_left": "none",
                            "border_right": "none",
                            "border_top": "none",
                            "border_bottom": "none",
                            "border_color": "",
                            "bold": False,
                            "italic": True,
                            "underline": False,
                            "strike": False,
                            "font_name": "",
                            "font_size_pt": None,
                            "font_color": "",
                            "align": "left",
                            "vertical_align": "bottom",
                        },
                    ],
                    "column_widths": [{"column": "B", "width_pt": 80}, {"column": "C", "width_pt": 90}],
                    "row_heights": [{"sheet_row": 2, "height_pt": 18}, {"sheet_row": 3, "height_pt": 20}],
                }
            ]
        })
        clipped = apply_range_filter(sheets, "C3:C3")
        assert clipped[0]["used_range"] == "C3"
        assert [item["cell"] for item in clipped[0]["cell_styles"]] == ["C3"]
        assert [item["column"] for item in clipped[0]["column_widths"]] == ["C"]
        assert [item["sheet_row"] for item in clipped[0]["row_heights"]] == [3]

    def test_sidecar_body_styles_and_formulas(self):
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import workbook_sidecar_extract_body

        default = workbook_sidecar_extract_body()
        assert "GetNumberFormat" not in default
        assert "GetFormula" not in default
        styled = workbook_sidecar_extract_body(include_styles=True)
        assert "GetNumberFormat" in styled
        assert "GetFormula" not in styled
        both = workbook_sidecar_extract_body(include_formulas=True, include_styles=True)
        assert "GetFormula" in both
        assert "GetNumberFormat" in both
        formulas_only = workbook_sidecar_extract_body(include_formulas=True)
        assert "GetFormula" in formulas_only
        assert "GetNumberFormat" not in formulas_only

    def test_parse_skips_sidecar_sheet_and_flattens_leaked_grids(self):
        sheets = parse_workbook_json({
            "sheets": [
                {
                    "sheet_index": 0,
                    "name": "Data",
                    "rows": [
                        ["姓名", [["", "", "姓名"]], "地点"],
                    ],
                },
                {
                    "sheet_index": 1,
                    "name": "_office_sidecar",
                    "rows": [["<<<OFFICE_SIDECAR>>>"]],
                },
            ]
        })
        assert [s["name"] for s in sheets] == ["Data"]
        assert sheets[0]["rows"][0] == ["姓名", "", "地点"]
        assert sheets[0]["headers"] == ["姓名", "", "地点"]
