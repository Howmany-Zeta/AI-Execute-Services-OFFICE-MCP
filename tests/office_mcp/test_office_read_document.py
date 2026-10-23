"""
Unit tests for office_read_document tool.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_read_document, OFFICE_READ_DOCUMENT_TOOL
from aiecs.tools.office_tool.core.categories import llm_coarse_output_type as llm_output_type
from aiecs.tools.office_tool.presentation.parser.txt import parse_txt_to_structure
from aiecs.tools.office_tool.spreadsheet.parser.csv import parse_csv_to_structure
from aiecs.tools.office_tool.word.parser.html import (
    extract_outline,
    extract_plain_text,
    parse_html_to_structure,
)


class TestOfficeReadDocumentToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has source_path/source_url, format markdown/plain/outline."""
        schema = OFFICE_READ_DOCUMENT_TOOL["inputSchema"]
        assert "source_path" in schema["properties"]
        assert "source_url" in schema["properties"]
        assert "content_base64" in schema["properties"]
        assert "internal" in schema["properties"]["source_path"]["description"].lower()
        assert "format" in schema["properties"]
        assert schema["properties"]["format"]["enum"] == ["markdown", "plain", "outline"]
        assert "options" in schema["properties"]

    def test_description_is_read_only(self):
        desc = OFFICE_READ_DOCUMENT_TOOL["description"]
        assert "For model reading only" in desc
        assert "office_edit_*" in desc


class TestHtmlParser:
    """Test HTML parser."""

    def test_parse_simple_html(self):
        """Parse headings and paragraphs."""
        html = """
        <html><body>
        <h1>Title</h1>
        <p>First paragraph.</p>
        <p>Second paragraph.</p>
        <h2>Section</h2>
        <p>More text.</p>
        </body></html>
        """
        result = parse_html_to_structure(html)
        assert result["title"] == "Title"
        assert len(result["elements"]) >= 4
        assert result["word_count"] > 0
        assert any(e.get("type") == "heading1" for e in result["elements"])
        assert any(e.get("type") == "paragraph" for e in result["elements"])

    def test_extract_plain_text(self):
        """Extract plain text."""
        html = "<html><body><h1>Hi</h1><p>Hello world.</p></body></html>"
        text = extract_plain_text(html)
        assert "Hi" in text
        assert "Hello" in text

    def test_extract_outline(self):
        """Extract headings only."""
        html = "<html><body><h1>A</h1><p>X</p><h2>B</h2></body></html>"
        outline = extract_outline(html)
        assert len(outline) >= 2
        assert any(o["text"] == "A" for o in outline)

    def test_parse_txt_to_structure(self):
        """Parse plain text into paragraph elements."""
        text = "Slide title\n\nBody line one.\nBody line two."
        result = parse_txt_to_structure(text)
        assert result["word_count"] > 0
        assert len(result["elements"]) >= 1

    def test_parse_csv_to_structure(self):
        """Parse CSV into row elements."""
        csv_text = "Name,Score\nAlice,90\nBob,85"
        result = parse_csv_to_structure(csv_text)
        assert len(result["elements"]) == 3
        assert result["elements"][0]["type"] == "row"
        assert result["elements"][1]["cells"] == ["Alice", "90"]


class TestConversionOutput:
    """Test LLM output type selection."""

    def test_word_uses_html(self):
        assert llm_output_type("docx") == "html"

    def test_presentation_uses_txt(self):
        assert llm_output_type("pptx") == "txt"
        assert llm_output_type("ppt") == "txt"

    def test_spreadsheet_uses_csv(self):
        assert llm_output_type("xlsx") == "csv"
        assert llm_output_type("xls") == "csv"


class TestOfficeReadDocument:
    """Test office_read_document execution."""

    @pytest.mark.asyncio
    async def test_missing_source_returns_error(self):
        """Missing source_path and source_url returns error."""
        result = await office_read_document(source_path="", source_url="")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_non_object_storage_source_returns_error(self):
        """Non gs:// or s3:// source_path returns error."""
        result = await office_read_document(source_path="/local/path.docx")
        assert result.get("isError") is True
        assert "gs://" in result.get("text", "") or "s3://" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_invalid_format_returns_error(self):
        result = await office_read_document(source_path="gs://b/p.docx", format="invalid")
        assert result.get("isError") is True
        assert "markdown, plain, or outline" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_structured_and_text_rejected(self):
        for fmt in ("structured", "text"):
            result = await office_read_document(source_path="gs://b/p.docx", format=fmt)
            assert result.get("isError") is True
            assert "markdown, plain, or outline" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_markdown_format_returns_markdown(self):
        sidecar = {
            "sections": [{
                "break_type": "continuous",
                "header": [],
                "footer": [],
                "body": [
                    {"class": "paragraph", "style_names": ["Heading 1"], "text": "Doc", "page_breaks": 0},
                    {"class": "paragraph", "style_names": ["Normal"], "text": "Content.", "page_breaks": 0},
                ],
            }],
            "footnotes": [],
        }

        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "docx", "gs://bucket/doc.docx", "gs://bucket/path/to/file.ext"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.convert_and_fetch",
            new_callable=AsyncMock,
        ) as convert:
            result = await office_read_document(source_path="gs://bucket/doc.docx", format="markdown")

        assert not result.get("isError")
        assert "elements" not in result
        assert "slides" not in result
        assert "[Page 1]" in result["markdown"]
        assert "# Doc" in result["markdown"]
        assert "Content." in result["markdown"]
        assert "must not" in result["_note"].lower() or "Do not pass" in result["_note"]
        assert result["conversion_output_type"] == "builder_json"
        convert.assert_not_called()

    @pytest.mark.asyncio
    async def test_plain_format_returns_text(self):
        sidecar = {
            "sections": [{
                "break_type": "continuous",
                "header": [],
                "footer": [],
                "body": [
                    {"class": "paragraph", "style_names": ["Heading 1"], "text": "Hello world.", "page_breaks": 0},
                ],
            }],
            "footnotes": [],
        }
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "docx", "gs://bucket/doc.docx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://bucket/doc.docx", format="plain")

        assert not result.get("isError"), result.get("text", "no error msg")
        assert "text" in result
        assert "markdown" not in result
        assert "Hello" in result["text"]

    @pytest.mark.asyncio
    async def test_xlsx_workbook_sidecar_csv_pages(self):
        sidecar = {"sheets": [
            {"sheet_index": 0, "name": "A", "rows": [["n", "s"], ["1", "2"]]},
            {"sheet_index": 1, "name": "B", "rows": [["x"]]},
        ]}
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "xlsx", "gs://bucket/data.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://bucket/data.xlsx", format="markdown")

        assert not result.get("isError")
        assert result["page_count"] == 2
        assert "[Page 1]" in result["markdown"]
        assert "[Page 2]" in result["markdown"]
        assert "<!-- sheet: A -->" in result["markdown"]
        assert "elements" not in result

    @pytest.mark.asyncio
    async def test_html_still_uses_conversion(self):
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "html", "gs://bucket/doc.html", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=("<html><body><h1>Doc</h1><p>Content.</p></body></html>", None),
        ):
            result = await office_read_document(source_path="gs://bucket/doc.html", format="markdown")

        assert not result.get("isError")
        assert result["conversion_output_type"] == "html"
        assert "elements" not in result
        assert "# Doc" in result["markdown"]

    @pytest.mark.asyncio
    async def test_pptx_markdown_has_no_shape_id(self):
        sidecar = {
            "slides": [{
                "slide_index": 1,
                "width_emu": 12700,
                "height_emu": 12700,
                "shapes": [{
                    "placeholder_type": "title",
                    "text": "Deck",
                    "x_emu": 0,
                    "y_emu": 0,
                    "width_emu": 12700,
                    "height_emu": 12700,
                }],
            }]
        }
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "pptx", "gs://bucket/slides.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://bucket/slides.pptx", format="markdown")

        assert not result.get("isError")
        assert "slides" not in result
        assert "elements" not in result
        assert "[Page 1]" in result["markdown"]
        assert "# Deck" in result["markdown"]
        assert "s1-1" not in result["markdown"]

    @pytest.mark.asyncio
    async def test_page_cap_error_mentions_page_range_not_parse(self, monkeypatch):
        from aiecs.config import OfficeReadConfig

        sidecar = {
            "slides": [
                {"slide_index": i, "shapes": [{"text": f"s{i}", "placeholder_type": "title"}]}
                for i in range(1, 6)
            ]
        }
        monkeypatch.setattr(
            "aiecs.tools.office_tool.core.document_read.get_office_read_config",
            lambda: OfficeReadConfig(max_pages=2),
        )
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "pptx", "gs://b/s.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://b/s.pptx", format="markdown")
        assert result.get("isError") is True
        assert "page_range" in result["text"]
        assert "office_parse_document" not in result["text"]

    @pytest.mark.asyncio
    async def test_output_cap_truncates_success(self, monkeypatch):
        from aiecs.config import OfficeReadConfig

        sidecar = {
            "sections": [{
                "break_type": "continuous",
                "header": [],
                "footer": [],
                "body": [
                    {"class": "paragraph", "text": "A" * 200, "page_breaks": 0},
                ],
            }],
            "footnotes": [],
        }
        monkeypatch.setattr(
            "aiecs.tools.office_tool.core.document_read.get_office_read_config",
            lambda: OfficeReadConfig(max_output_bytes=40),
        )
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "docx", "gs://b/doc.docx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://b/doc.docx", format="markdown")
        assert result.get("success") is True
        assert "[Page 1]" in result["markdown"]
        assert any("OFFICE_READ_MAX_OUTPUT_BYTES" in w for w in result.get("_warnings") or [])
        assert len(result["markdown"].encode("utf-8")) <= 40

    @pytest.mark.asyncio
    async def test_page_range_reads_slice_over_cap(self, monkeypatch):
        from aiecs.config import OfficeReadConfig

        sidecar = {
            "slides": [
                {"slide_index": i, "shapes": [{"text": f"s{i}", "placeholder_type": "title"}]}
                for i in range(1, 6)
            ]
        }
        monkeypatch.setattr(
            "aiecs.tools.office_tool.core.document_read.get_office_read_config",
            lambda: OfficeReadConfig(max_pages=2),
        )
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "pptx", "gs://b/s.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(
                source_path="gs://b/s.pptx",
                format="markdown",
                options={"page_range": [2, 3]},
            )
        assert result.get("success") is True
        assert "[Page 2]" in result["markdown"]
        assert "[Page 3]" in result["markdown"]
        assert "[Page 1]" not in result["markdown"]
        assert "[Page 5]" not in result["markdown"]

    @pytest.mark.asyncio
    async def test_truncated_sheet_warning(self):
        sidecar = {"sheets": [{"name": "Big", "rows": [["a"]], "truncated": "rows"}]}
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "xlsx", "gs://b/data.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_document(source_path="gs://b/data.xlsx", format="markdown")
        assert result.get("success") is True
        assert any("Big" in w and "rows" in w for w in result.get("_warnings") or [])