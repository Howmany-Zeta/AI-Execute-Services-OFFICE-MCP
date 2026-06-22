"""
Unit tests for office_read_document tool.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_read_document, OFFICE_READ_DOCUMENT_TOOL
from aiecs.tools.office_tool.conversion_output import llm_output_type
from aiecs.tools.office_tool.html_parser import (
    parse_html_to_structure,
    extract_plain_text,
    extract_outline,
    parse_txt_to_structure,
    parse_csv_to_structure,
)


class TestOfficeReadDocumentToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has source_path/source_url (one required), format optional."""
        schema = OFFICE_READ_DOCUMENT_TOOL["inputSchema"]
        assert "source_path" in schema["properties"]
        assert "source_url" in schema["properties"]
        assert "format" in schema["properties"]
        assert schema["properties"]["format"]["enum"] == ["structured", "text", "outline"]

    def test_description_warns_about_index(self):
        """Description warns index is not for GetElement."""
        desc = OFFICE_READ_DOCUMENT_TOOL["description"]
        assert "GetElement" in desc or "index" in desc.lower()
        assert "Search" in desc or "GetStyleName" in desc


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
    async def test_s3_source_path_resolves_presigned_url(self):
        """s3:// source_path uses resolve_document_source (MinIO presign)."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.html"}
        mock_html = "<html><body><p>MinIO doc.</p></body></html>"

        with patch(
            "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=(
                "http://minio:9000/bucket/doc.docx?sig=1",
                "docx",
                "s3://chatbot-use/doc.docx",
                "s3://bucket/path/to/file.ext",
            ),
        ), patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(
                    source_path="s3://chatbot-use/doc.docx",
                    format="text",
                )

        assert not result.get("isError")
        assert result["source_path"] == "s3://chatbot-use/doc.docx"
        assert result["source_path_format"] == "s3://bucket/path/to/file.ext"
        assert result["conversion_output_type"] == "html"
        mock_client.convert_until_complete.assert_called_once()
        convert_args = mock_client.convert_until_complete.call_args[0][0]
        assert convert_args["outputtype"] == "html"
        assert convert_args["filetype"] == "docx"
        assert convert_args["url"].startswith("http://minio")

    @pytest.mark.asyncio
    async def test_invalid_format_returns_error(self):
        """Invalid format returns error."""
        result = await office_read_document(source_path="gs://b/p.docx", format="invalid")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_structured_format_returns_elements(self):
        """format=structured returns elements, word_count, etc."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.html"}
        mock_html = "<html><body><h1>Doc</h1><p>Content.</p></body></html>"

        with patch("aiecs.tools.office_tool.core.coarse_read.resolve_document_source", new_callable=AsyncMock, return_value=("https://signed", "docx", "gs://bucket/doc.docx", "gs://bucket/path/to/file.ext")), \
             patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(source_path="gs://bucket/doc.docx", format="structured")

        assert "isError" not in result or not result.get("isError")
        assert "elements" in result
        assert "word_count" in result
        assert "_note" in result

    @pytest.mark.asyncio
    async def test_text_format_returns_text(self):
        """format=text returns plain text."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.html"}
        mock_html = "<html><body><p>Hello world.</p></body></html>"

        with patch("aiecs.tools.office_tool.core.coarse_read.resolve_document_source", new_callable=AsyncMock, return_value=("https://signed", "docx", "gs://bucket/doc.docx", "gs://bucket/path/to/file.ext")), \
             patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(source_path="gs://bucket/doc.docx", format="text")

        assert not result.get("isError"), result.get("text", "no error msg")
        assert "text" in result
        assert "Hello" in result["text"]

    @pytest.mark.asyncio
    async def test_source_url_path_uses_url_directly(self):
        """source_url (HTTP/HTTPS) is used directly without GCS signed URL."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.html"}
        mock_html = "<html><body><p>From URL.</p></body></html>"

        with patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_html
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(
                    source_url="https://example.com/doc.docx",
                    format="text",
                )

        assert not result.get("isError")
        assert "text" in result
        assert "From URL" in result["text"]
        mock_client.convert_until_complete.assert_called_once()
        call_args = mock_client.convert_until_complete.call_args[0][0]
        assert call_args["url"] == "https://example.com/doc.docx"
        assert call_args["outputtype"] == "html"

    @pytest.mark.asyncio
    async def test_pptx_uses_txt_outputtype(self):
        """pptx converts to txt for LLM consumption."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.txt"}
        mock_txt = "Slide 1\n\nIntro content.\n\nSlide 2\n\nMore content."

        with patch(
            "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "pptx", "gs://bucket/slides.pptx", "gs://bucket/path/to/file.ext"),
        ), patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_txt
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(source_path="gs://bucket/slides.pptx", format="text")

        assert not result.get("isError")
        assert "Intro content" in result["text"]
        assert result["conversion_output_type"] == "txt"
        assert mock_client.convert_until_complete.call_args[0][0]["outputtype"] == "txt"

    @pytest.mark.asyncio
    async def test_xlsx_uses_csv_outputtype(self):
        """xlsx converts to csv for LLM consumption."""
        mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.csv"}
        mock_csv = "Name,Score\nAlice,90"

        with patch(
            "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed", "xlsx", "gs://bucket/data.xlsx", "gs://bucket/path/to/file.ext"),
        ), patch("aiecs.tools.office_tool.core.coarse_read.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert_until_complete = AsyncMock(return_value=mock_convert)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.text = mock_csv
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_read_document(source_path="gs://bucket/data.xlsx", format="structured")

        assert not result.get("isError")
        assert result["conversion_output_type"] == "csv"
        assert any(e["type"] == "row" for e in result["elements"])
        assert mock_client.convert_until_complete.call_args[0][0]["outputtype"] == "csv"