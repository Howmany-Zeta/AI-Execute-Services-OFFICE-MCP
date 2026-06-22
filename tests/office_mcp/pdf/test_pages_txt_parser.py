"""Tests for pdf/parser/pages_txt.py (ADR-020)."""

from aiecs.tools.office_tool.pdf.parser.pages_txt import (
    pages_to_outline,
    pages_to_text,
    parse_txt_to_pages,
)


class TestPagesTxtParser:
    def test_form_feed_split(self):
        text = "Page one content\fPage two content"
        pages, note = parse_txt_to_pages(text)
        assert note is None
        assert len(pages) == 2
        assert pages[0]["page_index"] == 0
        assert pages[1]["blocks"][0]["text"] == "Page two content"

    def test_page_marker_split(self):
        text = "--- page 1 ---\nFirst\n--- page 2 ---\nSecond"
        pages, note = parse_txt_to_pages(text)
        assert note is None
        assert len(pages) == 2

    def test_single_page_with_note(self):
        text = "Only one page of text without boundaries"
        pages, note = parse_txt_to_pages(text)
        assert len(pages) == 1
        assert note is not None
        assert "single page" in note.lower()

    def test_pages_to_text_separator(self):
        pages, _ = parse_txt_to_pages("A\fB")
        text = pages_to_text(pages)
        assert "--- page 1 ---" in text
        assert "--- page 2 ---" in text

    def test_pages_to_outline(self):
        pages, _ = parse_txt_to_pages("Title line\fSecond page")
        outline = pages_to_outline(pages)
        assert outline[0]["title"] == "Title line"

    def test_legacy_read_document_unchanged(self):
        from aiecs.tools.office_tool.presentation.parser.txt import parse_txt_to_structure

        text = "Legacy block one\n\nLegacy block two"
        result = parse_txt_to_structure(text)
        assert result["elements"][0]["text"] == "Legacy block one"
