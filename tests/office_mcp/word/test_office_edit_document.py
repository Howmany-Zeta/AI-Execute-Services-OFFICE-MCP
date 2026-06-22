"""
Unit tests for office_edit_document tool.

Tests script injection, backup, validation, GCS integration (mocked).
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_edit_document, OFFICE_EDIT_DOCUMENT_TOOL


class TestOfficeEditDocumentToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has edit_script, output_path required; source_path/source_url optional (one required)."""
        schema = OFFICE_EDIT_DOCUMENT_TOOL["inputSchema"]
        assert set(schema["required"]) == {"edit_script", "output_path"}
        assert "source_path" in schema["properties"]
        assert "source_url" in schema["properties"]
        assert "options" in schema["properties"]

    def test_description_recommends_search_getstylename(self):
        """Description recommends Search() or GetStyleName(), not GetElement(index)."""
        desc = OFFICE_EDIT_DOCUMENT_TOOL["description"]
        assert "Search" in desc
        assert "GetStyleName" in desc
        assert "GetElement(index)" in desc or "GetElement" in desc


class TestOfficeEditDocument:
    """Test office_edit_document execution."""

    @pytest.mark.asyncio
    async def test_missing_params_return_error(self):
        """Missing required params return isError."""
        result = await office_edit_document(source_path="", edit_script="script", output_path="out.docx")
        assert result.get("isError") is True

        result = await office_edit_document(source_path="gs://b/p.docx", edit_script="", output_path="out.docx")
        assert result.get("isError") is True

        result = await office_edit_document(source_path="gs://b/p.docx", edit_script="script", output_path="")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_non_object_storage_source_returns_error(self):
        """Non gs:// or s3:// source_path returns error."""
        result = await office_edit_document(
            source_path="/local/path.docx", edit_script="script", output_path="out.docx"
        )
        assert result.get("isError") is True
        assert "gs://" in result.get("text", "") or "s3://" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_script_injection_and_success(self):
        """OpenFile/SaveFile/CloseFile are injected, script_to_url called, Builder called with url, result uploaded."""
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}
        captured_script = []

        async def capture_script(s):
            captured_script.append(s)
            return "https://fake-script/doc.docbuilder"

        with patch("aiecs.tools.office_tool.word.tools.edit_script.resolve_document_source", new_callable=AsyncMock) as mock_resolved, \
             patch("aiecs.tools.office_tool.core.builder_runtime.script_to_url", side_effect=capture_script), \
             patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.core.builder_runtime.upload_to_storage", new_callable=AsyncMock) as mock_upload:
            mock_resolved.return_value = (
                "https://signed-url/doc.docx",
                "docx",
                "gs://bucket/source.docx",
                "gs://bucket/path/to/file.ext",
            )
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"content"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_edit_document(
                    source_path="gs://bucket/source.docx",
                    edit_script="oDoc.GetElement(0).SetText('Hi');",
                    output_path="gs://bucket/out.docx",
                )

        assert result.get("success") is True
        assert result.get("output_path") == "gs://bucket/out.docx"
        mock_resolved.assert_called_once()
        script = captured_script[0]
        assert "builder.OpenFile" in script
        assert "builder.SaveFile" in script
        assert "builder.CloseFile" in script
        assert "oDoc.GetElement(0).SetText" in script
        mock_client.execute_builder.assert_called_once_with(
            url="https://fake-script/doc.docbuilder",
            argument=None,
        )

    @pytest.mark.asyncio
    async def test_backup_option_copies_before_edit(self):
        """options.backup=true calls copy_gcs_file before edit."""
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}

        mock_resolved = AsyncMock(
            return_value=(
                "https://signed",
                "docx",
                "gs://bucket/source.docx",
                "gs://bucket/path/to/file.ext",
            )
        )
        mock_copy = AsyncMock()
        mock_script_to_url = AsyncMock(return_value="https://fake-script/doc.docbuilder")
        with patch("aiecs.tools.office_tool.word.tools.edit_script.resolve_document_source", mock_resolved), \
             patch("aiecs.tools.office_tool.word.tools.edit_script.copy_storage_file", mock_copy), \
             patch("aiecs.tools.office_tool.core.builder_runtime.script_to_url", mock_script_to_url), \
             patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.core.builder_runtime.upload_to_storage", new_callable=AsyncMock):
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"x"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                await office_edit_document(
                    source_path="gs://bucket/source.docx",
                    edit_script="oDoc.GetElement(0).SetText('x');",
                    output_path="gs://bucket/source.docx",
                    options={"backup": True},
                )

        mock_copy.assert_called_once_with("gs://bucket/source.docx", "gs://bucket/source.docx.backup")
