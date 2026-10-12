"""Tests for pdf/parser/pages_txt.py (ADR-020)."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.legacy.read_document import office_read_document
from aiecs.tools.office_tool.pdf.parser.pages_txt import (
    pages_to_outline,
    pages_to_text,
    parse_txt_to_pages,
)

pytestmark = pytest.mark.asyncio


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

    async def test_legacy_read_document_pdf_uses_document_ai_elements(self):
        layout = {
            "documentLayout": {
                "blocks": [
                    {
                        "pageSpan": {"pageStart": 1, "pageEnd": 1},
                        "textBlock": {"type": "paragraph", "text": "Legacy block one"},
                    },
                    {
                        "pageSpan": {"pageStart": 1, "pageEnd": 1},
                        "textBlock": {"type": "paragraph", "text": "Legacy block two"},
                    },
                ]
            }
        }
        client = AsyncMock()
        client.process_pdf_online = AsyncMock(return_value=layout)
        with patch(
            "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.structured_read.stat_object_size",
            new_callable=AsyncMock,
            return_value=100,
        ), patch(
            "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 /Type /Page ",
        ), patch(
            "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
            return_value=1,
        ), patch(
            "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
            return_value=client,
        ), patch(
            "aiecs.config.get_documentai_config",
        ) as cfg:
            cfg.return_value.is_configured.return_value = True
            result = await office_read_document(
                source_path="gs://b/doc.pdf",
                format="structured",
            )

        assert result.get("isError") is not True
        assert "elements" in result
        assert "pages" not in result
        assert result["elements"][0]["text"] == "Legacy block one"
        assert result["conversion_output_type"] == "document_layout"

        pages, _ = parse_txt_to_pages("Legacy block one\n\nLegacy block two")
        assert "page_index" in pages[0]
        assert "elements" not in pages[0]
