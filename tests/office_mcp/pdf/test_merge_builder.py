"""Tests for pdf/builder/merge.py script generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiecs.tools.office_tool.pdf.builder.merge import (
    build_merge_script_builder,
    merge_pdfs_conversion,
)

pytestmark = pytest.mark.asyncio


class TestBuildMergeScriptBuilder:
    def test_merge_two_pdfs_uses_tojson_and_create_file(self):
        script = build_merge_script_builder(
            ["https://ds/a.pdf", "https://ds/b.pdf"],
            ["pdf", "pdf"],
            output_ext="pdf",
        )
        assert 'GlobalVariable["merge_0"]' in script
        assert 'GlobalVariable["merge_1"]' in script
        assert 'builder.CreateFile("pdf")' in script
        assert "Api.ReplaceDocumentContent(content0)" in script
        assert "doc.Push(elements[j])" in script
        assert script.index('builder.SaveFile("pdf"') > script.index("ReplaceDocumentContent")
        assert script.count("builder.OpenFile") == 2
        assert script.count("builder.CloseFile") == 3

    def test_does_not_reopen_first_source_before_save(self):
        script = build_merge_script_builder(
            ["https://ds/a.pdf", "https://ds/b.pdf"],
            ["pdf", "pdf"],
            output_ext="pdf",
        )
        save_idx = script.index('builder.SaveFile("pdf"')
        tail = script[:save_idx]
        assert tail.count('builder.OpenFile("https://ds/a.pdf"') == 1


class TestMergePdfsConversion:
    async def test_uploads_merged_file_to_output_path(self):
        mock_client = AsyncMock()
        mock_client.convert = AsyncMock(
            side_effect=[
                {"fileUrl": "https://ds/merged-step1.pdf"},
                {"fileUrl": "https://ds/merged-final.pdf"},
            ]
        )
        with patch(
            "aiecs.tools.office_tool.pdf.builder.merge.get_documentserver_client",
            return_value=mock_client,
        ), patch("httpx.AsyncClient") as mock_http, patch(
            "aiecs.tools.office_tool.pdf.builder.merge.upload_to_storage",
            new_callable=AsyncMock,
        ) as mock_upload:
            mock_response = MagicMock()
            mock_response.content = b"%PDF-1.4 merged"
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await merge_pdfs_conversion(
                ["https://ds/a.pdf", "https://ds/b.pdf"],
                "gs://bucket/merged.pdf",
                client=mock_client,
            )

        assert result.get("success") is True
        assert result.get("output_path") == "gs://bucket/merged.pdf"
        mock_upload.assert_awaited_once_with(b"%PDF-1.4 merged", "gs://bucket/merged.pdf")
