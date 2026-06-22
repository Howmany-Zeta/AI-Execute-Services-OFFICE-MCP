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
