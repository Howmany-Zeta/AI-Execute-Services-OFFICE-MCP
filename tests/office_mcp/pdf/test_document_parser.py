"""Tests for pdf/parser/document.py."""

import json
from pathlib import Path

from aiecs.tools.office_tool.pdf.parser.document import (
    PDF_PAGE_EXTRACT_BODY,
    apply_page_range,
    parse_document_json,
    pdf_page_extract_body,
    sidecar_bookmarks,
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
        assert pages[0]["annotations"][0]["annotation_index"] == 0
        assert "annotations" not in pages[1]

    def test_sidecar_extracts_rotation_drawings_and_bookmarks(self):
        assert "GetRotation" in PDF_PAGE_EXTRACT_BODY
        assert "GetAllDrawings" in PDF_PAGE_EXTRACT_BODY
        assert "GetAllBookmarksNames" in PDF_PAGE_EXTRACT_BODY

    def test_pdf_page_extract_body_limits_page_walk(self):
        body = pdf_page_extract_body((0, 2))
        assert "for (var i = 0; i < pageCount && i <= 2; i++)" in body
        assert pdf_page_extract_body() == PDF_PAGE_EXTRACT_BODY

    def test_normalize_degrees_and_justify(self):
        pages = parse_document_json(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "degrees": 180,
                        "blocks": [
                            {
                                "block_index": 0,
                                "type": "paragraph",
                                "text": "Title",
                                "align": "both",
                                "bold": True,
                                "font_name": "Calibri",
                                "font_size_pt": 16,
                            }
                        ],
                    }
                ]
            }
        )
        page = pages[0]
        assert page["degrees"] == 180
        block = page["blocks"][0]
        assert block["align"] == "justify"
        assert block["bold"] is True
        assert block["font_name"] == "Calibri"
        assert block["font_size_pt"] == 16

    def test_normalize_table_cells_keep_empty(self):
        pages = parse_document_json(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "blocks": [
                            {"block_index": 0, "type": "table", "rows": [["A", ""], ["", "D"]]}
                        ],
                    }
                ]
            }
        )
        cells = pages[0]["blocks"][0]["cells"]
        assert {"row": 0, "col": 1, "text": ""} in cells
        assert {"row": 1, "col": 0, "text": ""} in cells
        assert {"row": 1, "col": 1, "text": "D"} in cells

    def test_normalize_image_block_and_page_images(self):
        pages = parse_document_json(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "blocks": [
                            {
                                "block_index": 1,
                                "type": "image",
                                "alt": "Logo",
                                "width_pt": 80,
                                "height_pt": 40,
                            }
                        ],
                        "images": [{"image_index": 0, "alt": "Banner", "width_pt": 200}],
                    }
                ]
            }
        )
        image_block = pages[0]["blocks"][0]
        assert image_block["type"] == "image"
        assert image_block["block_index"] == 1
        assert image_block["alt"] == "Logo"
        assert image_block["width_pt"] == 80
        assert pages[0]["images"][0]["image_index"] == 0
        assert pages[0]["images"][0]["alt"] == "Banner"

    def test_normalize_annotation_rect_and_freetext_kind(self):
        pages = parse_document_json(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "annotations": [
                            {
                                "kind": "FreeTextAnnot",
                                "text": "Note",
                                "rect": {"x": 10, "y": 20, "width": 80, "height": 30},
                            }
                        ],
                    }
                ]
            }
        )
        annot = pages[0]["annotations"][0]
        assert annot["kind"] == "freetext"
        assert annot["annotation_index"] == 0
        assert annot["rect"] == {"x": 10.0, "y": 20.0, "width": 80.0, "height": 30.0}

    def test_normalize_form_type_and_page_index(self):
        pages = parse_document_json(
            {
                "pages": [
                    {
                        "page_index": 2,
                        "form_fields": [
                            {"name": "Agree", "type": "checkboxField", "value": "true"},
                            {"name": "Other", "type": "mysteryWidget", "value": ""},
                        ],
                    }
                ]
            }
        )
        fields = pages[0]["form_fields"]
        assert fields[0]["page_index"] == 2
        assert fields[0]["type"] == "checkbox"
        assert fields[1]["type"] == "unknown"

    def test_sidecar_bookmarks_empty_when_missing(self):
        assert sidecar_bookmarks({"pages": []}) == []

    def test_sidecar_bookmarks_use_name_as_id(self):
        bookmarks = sidecar_bookmarks(
            {"bookmarks": [{"name": "Intro", "text": "Hello"}]}
        )
        assert bookmarks == [{"bookmark_id": "Intro", "name": "Intro", "text": "Hello"}]
