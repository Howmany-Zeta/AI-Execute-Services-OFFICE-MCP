"""Tests for pdf/parser/document.py."""

import json
from pathlib import Path

from aiecs.tools.office_tool.pdf.parser.document import (
    PDF_PAGE_EXTRACT_BODY,
    apply_page_range,
    parse_document_json,
    word_count_from_pages,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestDocumentParser:
    def test_parse_document_json(self):
        raw = json.loads((FIXTURES / "document_sidecar.json").read_text())
        pages = parse_document_json(raw)
        assert len(pages) == 2
        assert pages[0]["blocks"][0]["text"] == "Page One Title"
        assert pages[0]["form_fields"][0]["name"] == "company_name"

    def test_apply_page_range(self):
        raw = json.loads((FIXTURES / "document_sidecar.json").read_text())
        pages = parse_document_json(raw)
        filtered = apply_page_range(pages, (1, 1))
        assert len(filtered) == 1
        assert filtered[0]["page_index"] == 1

    def test_word_count_from_pages(self):
        raw = json.loads((FIXTURES / "document_sidecar.json").read_text())
        pages = parse_document_json(raw)
        assert word_count_from_pages(pages) > 0

    def test_sidecar_uses_get_document(self):
        assert "GetDocument" in PDF_PAGE_EXTRACT_BODY

    def test_sidecar_extracts_form_fields_per_page_via_widgets(self):
        assert "GetAllWidgets" in PDF_PAGE_EXTRACT_BODY
        assert "GetAllForms" not in PDF_PAGE_EXTRACT_BODY

    def test_sidecar_extracts_annotations_per_page(self):
        assert "GetAllAnnots" in PDF_PAGE_EXTRACT_BODY

    def test_sidecar_detects_table_blocks(self):
        assert 'cls === "table"' in PDF_PAGE_EXTRACT_BODY
        assert "GetRowsCount" in PDF_PAGE_EXTRACT_BODY

    def test_sidecar_records_widgets_api_availability(self):
        assert "widgets_api_available" in PDF_PAGE_EXTRACT_BODY

    def test_parse_document_json_table_block(self):
        raw = {
            "pages": [
                {
                    "page_index": 0,
                    "blocks": [
                        {"block_index": 0, "type": "table", "rows": [["A", "B"], ["1", "2"]]}
                    ],
                }
            ]
        }
        pages = parse_document_json(raw)
        assert pages[0]["blocks"][0]["type"] == "table"
        assert pages[0]["blocks"][0]["rows"][1][1] == "2"

    def test_word_count_from_pages_includes_table_cells(self):
        pages = [
            {
                "page_index": 0,
                "blocks": [{"block_index": 0, "type": "table", "rows": [["Hello", "World"]]}],
            }
        ]
        assert word_count_from_pages(pages) == 2

    def test_parse_document_json_form_fields_only_on_pages_with_widgets(self):
        raw = json.loads((FIXTURES / "document_sidecar.json").read_text())
        pages = parse_document_json(raw)
        assert "form_fields" in pages[0]
        assert "form_fields" not in pages[1]

    def test_parse_document_json_annotations(self):
        raw = json.loads((FIXTURES / "document_sidecar.json").read_text())
        pages = parse_document_json(raw)
        assert pages[0]["annotations"][0]["kind"] == "highlight"
        assert "annotations" not in pages[1]
