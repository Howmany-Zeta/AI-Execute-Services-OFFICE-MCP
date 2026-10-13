"""
Unit tests for office_execute_builder tool.

Omit output_path: content_base64 + filename + format.
s3:// / gs:// output_path keeps the old upload.
"""

import base64

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from aiecs.tools.office_tool import OFFICE_EXECUTE_BUILDER_TOOL, office_execute_builder
from aiecs.tools.office_tool.core.file_ext import logical_filename


class TestOfficeExecuteBuilderToolDefinition:
    def test_tool_has_required_schema(self):
        schema = OFFICE_EXECUTE_BUILDER_TOOL["inputSchema"]
        assert "url" in schema["properties"]
        assert "script" in schema["properties"]
        assert "output_path" in schema["properties"]
        assert schema["properties"]["script"]["type"] == "string"
        assert schema["properties"]["url"]["type"] == "string"
        assert schema["properties"]["output_path"]["type"] == "string"

    def test_tool_name_and_description(self):
        assert OFFICE_EXECUTE_BUILDER_TOOL["name"] == "office_execute_builder"
        assert "Builder" in OFFICE_EXECUTE_BUILDER_TOOL["description"]
        assert "content_base64" in OFFICE_EXECUTE_BUILDER_TOOL["description"]
        assert "s3://" in OFFICE_EXECUTE_BUILDER_TOOL["description"]


class TestLogicalFilename:
    def test_s3_path_is_name_only(self):
        name, fmt = logical_filename("s3://caller-bucket/user/report.docx", "pdf")
        assert name == "report.docx"
        assert fmt == "docx"

    def test_bare_name_gets_ext_from_builder(self):
        name, fmt = logical_filename("quarterly", "pptx")
        assert name == "quarterly.pptx"
        assert fmt == "pptx"

    def test_default_when_missing(self):
        name, fmt = logical_filename(None, "docx")
        assert name == "output.docx"
        assert fmt == "docx"


class TestOfficeExecuteBuilder:
    @pytest.mark.asyncio
    async def test_empty_input_returns_error(self):
        result = await office_execute_builder()
        assert result.get("isError") is True
        assert "url" in result.get("text", "").lower() or "script" in result.get("text", "").lower()

        result = await office_execute_builder(script="   ")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_success_returns_file_bytes(self):
        mock_result = {"fileUrl": "http://ds/temp/file.docx", "fileType": "docx"}
        test_url = "https://example.com/script.docbuilder"
        body = b"PK\x03\x04docx-bytes"

        with patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.core.builder_runtime.upload_to_storage", new_callable=AsyncMock) as mock_upload, \
             patch("httpx.AsyncClient") as mock_http:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = body
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await office_execute_builder(url=test_url)

        assert result.get("success") is True
        assert result.get("filename") == "output.docx"
        assert result.get("format") == "docx"
        assert result.get("bytes") == len(body)
        assert base64.b64decode(result["content_base64"]) == body
        assert "vnd.openxmlformats" in (result.get("media_type") or "")
        mock_upload.assert_not_called()
        mock_client.execute_builder.assert_called_once_with(url=test_url, argument=None)

    @pytest.mark.asyncio
    async def test_output_path_s3_keeps_upload(self):
        mock_result = {"fileUrl": "http://ds/temp/file.docx", "fileType": "docx"}
        body = b"generated-docx"

        with patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.core.builder_runtime.upload_to_storage", new_callable=AsyncMock) as mock_upload, \
             patch("httpx.AsyncClient") as mock_http:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = body
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await office_execute_builder(
                url="https://example.com/script.docbuilder",
                output_path="s3://caller-minio/user_e2e/out.docx",
            )

        assert result.get("success") is True
        assert result.get("output_path") == "s3://caller-minio/user_e2e/out.docx"
        assert "content_base64" not in result
        mock_upload.assert_awaited_once_with(body, "s3://caller-minio/user_e2e/out.docx")

    @pytest.mark.asyncio
    async def test_documentserver_error_returns_is_error(self):
        import httpx

        with patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get:
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
        with patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value={"end": True})
            mock_get.return_value = mock_client

            result = await office_execute_builder(url="https://example.com/script.docbuilder")

        assert result.get("isError") is True
        assert "fileUrl" in result.get("text", "")
