"""
Unit tests for office_merge_documents tool.

Tests script generation, options (add_page_break, add_toc), validation, GCS integration (mocked).
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_merge_documents, OFFICE_MERGE_DOCUMENTS_TOOL
from aiecs.tools.office_tool.merge_document import _build_merge_script


class TestOfficeMergeDocumentsToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has output_path required; source_paths/source_urls optional (one required)."""
        schema = OFFICE_MERGE_DOCUMENTS_TOOL["inputSchema"]
        assert "output_path" in schema["required"]
        assert "source_paths" in schema["properties"]
        assert "source_urls" in schema["properties"]
        assert "options" in schema["properties"]
        opts = schema["properties"]["options"]["properties"]
        assert "add_page_break" in opts
        assert "add_toc" in opts

    def test_description_mentions_options(self):
        """Description mentions add_page_break and add_toc."""
        desc = OFFICE_MERGE_DOCUMENTS_TOOL["description"]
        assert "add_page_break" in desc
        assert "add_toc" in desc


class TestBuildMergeScript:
    """Test script generation."""

    def test_single_doc_script(self):
        """Single document: OpenFile, ToJSON, CreateFile, ReplaceDocumentContent, SaveFile."""
        script = _build_merge_script(
            ["https://signed/doc1.docx"],
            ["docx"],
            add_page_break=False,
            add_toc=False,
        )
        assert "builder.OpenFile" in script
        assert "ToJSON" in script
        assert "builder.CreateFile" in script
        assert "ReplaceDocumentContent" in script
        assert "builder.SaveFile" in script
        assert "AddPageBreak" not in script
        assert "AddTableOfContents" not in script

    def test_two_docs_with_page_break(self):
        """Two docs: page break between them."""
        script = _build_merge_script(
            ["https://u1", "https://u2"],
            ["docx", "docx"],
            add_page_break=True,
            add_toc=False,
        )
        assert "AddPageBreak" in script
        assert "merge_0" in script
        assert "merge_1" in script

    def test_add_toc(self):
        """add_toc adds AddTableOfContents at start."""
        script = _build_merge_script(
            ["https://u1"],
            ["docx"],
            add_page_break=False,
            add_toc=True,
        )
        assert "AddTableOfContents" in script
        assert "MoveCursorToStart" in script


class TestOfficeMergeDocuments:
    """Test office_merge_documents execution."""

    @pytest.mark.asyncio
    async def test_empty_source_paths_returns_error(self):
        """Empty source_paths returns error."""
        result = await office_merge_documents(source_paths=[], output_path="gs://b/out.docx")
        assert result.get("isError") is True

        result = await office_merge_documents(source_paths="not-a-list", output_path="gs://b/out.docx")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_missing_output_path_returns_error(self):
        """Missing output_path returns error."""
        result = await office_merge_documents(source_paths=["gs://b/a.docx"], output_path="")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_non_object_storage_source_returns_error(self):
        """Non gs:// or s3:// source_path returns error."""
        result = await office_merge_documents(source_paths=["/local/path.docx"], output_path="gs://b/out.docx")
        assert result.get("isError") is True
        assert "gs://" in result.get("text", "") or "s3://" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_merge_success(self):
        """Merge two docs: signed URLs, script_to_url called, Builder called with url, result uploaded."""
        mock_result = {"fileUrl": "http://ds/temp/merged.docx", "fileType": "docx"}
        captured_script = []

        async def capture_script(s):
            captured_script.append(s)
            return "https://fake-script/merge.docbuilder"

        mock_signed = AsyncMock(side_effect=["https://signed1", "https://signed2"])
        with patch("aiecs.tools.office_tool.word.tools.merge.resolve_fetch_url", mock_signed), \
             patch("aiecs.tools.office_tool.core.builder_runtime.script_to_url", side_effect=capture_script), \
             patch("aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.core.builder_runtime.upload_to_storage", new_callable=AsyncMock) as mock_upload:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"merged"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_merge_documents(
                    source_paths=["gs://bucket/a.docx", "gs://bucket/b.docx"],
                    output_path="gs://bucket/merged.docx",
                )

        assert result.get("success") is True
        assert result.get("output_path") == "gs://bucket/merged.docx"
        assert mock_signed.call_count == 2
        script = captured_script[0]
        assert "merge_0" in script
        assert "merge_1" in script
        mock_client.execute_builder.assert_called_once_with(
            url="https://fake-script/merge.docbuilder",
            argument=None,
        )

    @pytest.mark.asyncio
    async def test_options_add_page_break_and_toc(self):
        """options add_page_break and add_toc are passed to script."""
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}
        captured_script = []

        async def capture_script(s):
            captured_script.append(s)
            return "https://fake-script/merge.docbuilder"

        with patch("aiecs.tools.office_tool.word.tools.merge.resolve_fetch_url", new_callable=AsyncMock) as m:
            m.return_value = "https://signed"
            with patch("aiecs.tools.office_tool.core.builder_runtime.script_to_url", side_effect=capture_script), \
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

                    await office_merge_documents(
                        source_paths=["gs://bucket/a.docx", "gs://bucket/b.docx"],
                        output_path="gs://bucket/out.docx",
                        options={"add_page_break": True, "add_toc": True},
                    )

        script = captured_script[0]
        assert "AddPageBreak" in script
        assert "AddTableOfContents" in script
