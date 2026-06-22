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
        assert sheets[1]["sheet_index"] == 1

    def test_filter_sheet_names(self):
        raw = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        sheets = parse_workbook_json(raw)
        filtered = filter_sheet_names(sheets, ["Summary"])
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Summary"

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
        from aiecs.tools.office_tool.spreadsheet.parser.workbook import WORKBOOK_SIDECAR_EXTRACT_BODY

        assert "GetSheetsCount" in WORKBOOK_SIDECAR_EXTRACT_BODY
