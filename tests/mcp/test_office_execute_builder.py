"""
Unit tests for office_execute_builder tool.

Tests script passthrough, output_path handling, validation, and error handling.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_execute_builder, OFFICE_EXECUTE_BUILDER_TOOL


class TestOfficeExecuteBuilderToolDefinition:
    """Test tool definition (inputSchema, description)."""

    def test_tool_has_required_schema(self):
        """inputSchema has url, script (one required), output_path (optional)."""
        schema = OFFICE_EXECUTE_BUILDER_TOOL["inputSchema"]
        assert "url" in schema["properties"]
        assert "script" in schema["properties"]
        assert "output_path" in schema["properties"]
        assert schema["properties"]["script"]["type"] == "string"
        assert schema["properties"]["url"]["type"] == "string"
        assert schema["properties"]["output_path"]["type"] == "string"

    def test_tool_name_and_description(self):
        """Tool has correct name and description."""
        assert OFFICE_EXECUTE_BUILDER_TOOL["name"] == "office_execute_builder"
        assert "Builder" in OFFICE_EXECUTE_BUILDER_TOOL["description"]
        assert "script" in OFFICE_EXECUTE_BUILDER_TOOL["description"].lower()


class TestOfficeExecuteBuilder:
    """Test office_execute_builder execution."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_error(self):
        """Empty or missing url/script returns isError."""
        result = await office_execute_builder()
        assert result.get("isError") is True
        assert "url" in result.get("text", "").lower() or "script" in result.get("text", "").lower()

        result = await office_execute_builder(script="   ")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_url_passthrough_returns_file_url(self):
        """Valid url POSTs to DocumentServer and returns file_url when no output_path."""
        mock_result = {"fileUrl": "http://ds/temp/file.docx", "fileType": "docx"}
        test_url = "https://example.com/script.docbuilder"

        with patch("aiecs.tools.office_tool.execute_builder.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            result = await office_execute_builder(url=test_url)

        assert result.get("success") is True
        assert result.get("file_url") == "http://ds/temp/file.docx"
        mock_client.execute_builder.assert_called_once_with(url=test_url, argument=None)

    @pytest.mark.asyncio
    async def test_with_output_path_downloads_and_uploads(self):
        """With output_path, downloads from fileUrl and uploads to storage."""
        mock_result = {"fileUrl": "http://ds/temp/file.docx", "fileType": "docx"}
        test_url = "https://example.com/script.docbuilder"

        with patch("aiecs.tools.office_tool.execute_builder.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.execute_builder.upload_to_storage", new_callable=AsyncMock) as mock_upload:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"docx content"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_execute_builder(
                    url=test_url,
                    output_path="/tmp/out.docx",
                )

        assert result.get("success") is True
        assert result.get("output_path") == "/tmp/out.docx"
        mock_upload.assert_called_once_with(b"docx content", "/tmp/out.docx")

    @pytest.mark.asyncio
    async def test_documentserver_error_returns_is_error(self):
        """DocumentServer HTTP error returns isError."""
        import httpx

        with patch("aiecs.tools.office_tool.execute_builder.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(
                side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=MagicMock())
            )
            mock_get.return_value = mock_client

            result = await office_execute_builder(url="https://example.com/script.docbuilder")

        assert result.get("isError") is True
        assert "error" in result.get("text", "").lower() or "403" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_no_file_url_in_response_returns_error(self):
        """When DocumentServer returns no fileUrl, return isError."""
        with patch("aiecs.tools.office_tool.execute_builder.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value={"end": True})  # no fileUrl
            mock_get.return_value = mock_client

            result = await office_execute_builder(url="https://example.com/script.docbuilder")

        assert result.get("isError") is True
        assert "fileUrl" in result.get("text", "")
