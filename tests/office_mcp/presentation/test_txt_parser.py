"""Tests for presentation/parser/txt.py (legacy coarse txt)."""

from aiecs.tools.office_tool.presentation.parser.txt import (
    extract_outline_from_txt,
    parse_txt_to_structure,
)


class TestTxtParser:
    def test_parse_txt_to_structure(self):
        text = "Slide One Title\n\nBody line one\n\nSlide Two Title\n\nBody two"
        result = parse_txt_to_structure(text)
        assert len(result["elements"]) >= 1
        assert result["word_count"] > 0
        assert result["title"]

    def test_extract_outline_from_txt(self):
        text = "1. Introduction\n\nContent\n\nSlide 2: Summary"
        outline = extract_outline_from_txt(text)
        assert len(outline) >= 1

    def test_parse_txt_matches_canonical_module(self):
        """Canonical presentation.parser.txt is the single import path (ADR-022)."""
        from aiecs.tools.office_tool.presentation.parser import txt as txt_mod

        text = "Title block\n\nSecond block"
        assert txt_mod.parse_txt_to_structure(text)["elements"][0]["text"] == "Title block"
