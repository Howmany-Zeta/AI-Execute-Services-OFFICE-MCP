"""Tests for spreadsheet/parser/csv.py (legacy coarse csv)."""

from aiecs.tools.office_tool.spreadsheet.parser.csv import (
    csv_to_coarse_sheets,
    extract_outline_from_csv,
    parse_csv_to_structure,
)


class TestCsvParser:
    def test_parse_csv_to_structure(self):
        text = "Name,Value\nAlpha,1\nBeta,2"
        result = parse_csv_to_structure(text)
        assert len(result["elements"]) == 3
        assert result["title"] == "Name"

    def test_csv_to_coarse_sheets(self):
        text = "A,B\n1,2\n3,4"
        sheets = csv_to_coarse_sheets(text)
        assert len(sheets) == 1
        assert sheets[0]["name"] == "Sheet1"
        assert len(sheets[0]["rows"]) == 3

    def test_csv_parser_canonical_import(self):
        from aiecs.tools.office_tool.spreadsheet.parser import csv as csv_mod

        text = "H1,H2\nv1,v2"
        assert csv_mod.parse_csv_to_structure(text)["elements"][0]["cells"] == ["H1", "H2"]

    def test_extract_outline_from_csv(self):
        text = "Col1,Col2\n1,2"
        outline = extract_outline_from_csv(text)
        assert len(outline) == 2
