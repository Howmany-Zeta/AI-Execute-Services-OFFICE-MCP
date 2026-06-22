"""Tests for core/read_response.py."""

from aiecs.tools.office_tool.core.read_response import build_read_response

LOCATOR = "Use block_index for edits."


class TestBuildReadResponse:
    def test_word_mirrors_blocks(self):
        units = [{"block_index": 0, "text": "Hello"}]
        resp = build_read_response(
            category="word",
            title="Doc",
            units=units,
            read_mode="fine",
            locator_note=LOCATOR,
        )
        assert resp["success"] is True
        assert resp["category"] == "word"
        assert resp["units"] == units
        assert resp["blocks"] == units
        assert resp["unit_count"] == 1
        assert resp["_locator_note"] == LOCATOR

    def test_presentation_mirrors_slides_and_count(self):
        units = [{"slide_index": 0}]
        resp = build_read_response(
            category="presentation",
            title="Deck",
            units=units,
            read_mode="fine",
            locator_note=LOCATOR,
        )
        assert resp["slides"] == units
        assert resp["slide_count"] == 1

    def test_spreadsheet_mirrors_sheets(self):
        units = [{"sheet_index": 0, "name": "Sheet1"}]
        resp = build_read_response(
            category="spreadsheet",
            title="Book",
            units=units,
            read_mode="fine",
            locator_note=LOCATOR,
        )
        assert resp["sheets"] == units

    def test_pdf_mirrors_pages_and_count(self):
        units = [{"page_index": 0}]
        resp = build_read_response(
            category="pdf",
            title="PDF",
            units=units,
            read_mode="fine",
            locator_note=LOCATOR,
        )
        assert resp["pages"] == units
        assert resp["page_count"] == 1

    def test_extra_fields_merged(self):
        resp = build_read_response(
            category="word",
            title="T",
            units=[],
            read_mode="coarse",
            locator_note=LOCATOR,
            source_path="gs://b/f.docx",
            extra={"layouts": []},
        )
        assert resp["source_path"] == "gs://b/f.docx"
        assert resp["layouts"] == []
