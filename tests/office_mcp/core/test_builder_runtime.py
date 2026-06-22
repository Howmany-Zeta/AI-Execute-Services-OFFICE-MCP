"""
Unit tests for core/builder_runtime.py.

Mocks DocumentServer client and storage; no live DS required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiecs.tools.office_tool.core.builder_js import close_file, escape_js, open_file, save_file, wrap_script
from aiecs.tools.office_tool.core.builder_runtime import run_builder_on_source, run_builder_script

pytestmark = pytest.mark.asyncio


class TestBuilderJs:
    """Test builder_js helpers."""

    def test_escape_js_special_chars(self):
        assert escape_js('Say "hi"\\') == 'Say \\"hi\\"\\\\'
        assert escape_js("line\tbreak") == "line\\tbreak"
        assert escape_js("\u2028\u2029") == "\\u2028\\u2029"

    def test_open_file_and_save_file(self):
        assert open_file("https://x/doc.docx", "docx") == 'builder.OpenFile("https://x/doc.docx", "docx");'
        assert save_file("docx", "output.docx") == 'builder.SaveFile("docx", "output.docx");'
        assert close_file() == "builder.CloseFile();"

    def test_wrap_script_appends_close_when_missing(self):
        wrapped = wrap_script("builder.CreateFile('docx');")
        assert "builder.CloseFile();" in wrapped

    def test_wrap_script_keeps_existing_close(self):
        body = "builder.CreateFile('docx');\nbuilder.CloseFile();"
        assert wrap_script(body) == body


class TestRunBuilderScript:
    """Test run_builder_script happy path and errors."""

    async def test_script_success_returns_file_url(self):
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}

        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.script_to_url",
            new_callable=AsyncMock,
            return_value="https://hosted/script.docbuilder",
        ), patch(
            "aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client"
        ) as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            result = await run_builder_script("builder.CreateFile('docx'); builder.CloseFile();")

        assert result == {"success": True, "file_url": "http://ds/temp/out.docx"}
        mock_client.execute_builder.assert_called_once_with(
            url="https://hosted/script.docbuilder",
            argument=None,
        )

    async def test_url_success_with_output_path(self):
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}

        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client"
        ) as mock_get, patch(
            "aiecs.tools.office_tool.core.builder_runtime.upload_to_storage",
            new_callable=AsyncMock,
        ) as mock_upload:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"docx bytes"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await run_builder_script(
                    url="https://example.com/script.docbuilder",
                    output_path="gs://bucket/out.docx",
                )

        assert result == {"success": True, "output_path": "gs://bucket/out.docx"}
        mock_upload.assert_called_once_with(b"docx bytes", "gs://bucket/out.docx")

    async def test_missing_script_and_url_returns_error(self):
        result = await run_builder_script()
        assert result == {"isError": True, "text": "Provide script or url"}

    async def test_script_to_url_value_error(self):
        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.script_to_url",
            new_callable=AsyncMock,
            side_effect=ValueError("DOCBUILDER_SCRIPT_GCS_PATH not set"),
        ):
            result = await run_builder_script("builder.CloseFile();")

        assert result == {"isError": True, "text": "DOCBUILDER_SCRIPT_GCS_PATH not set"}

    async def test_documentserver_http_error(self):
        import httpx

        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.script_to_url",
            new_callable=AsyncMock,
            return_value="https://hosted/script.docbuilder",
        ), patch(
            "aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client"
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(
                side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)
            )
            mock_get.return_value = mock_client

            result = await run_builder_script("builder.CloseFile();")

        assert result.get("isError") is True
        assert "403" in result.get("text", "")

    async def test_missing_file_url_returns_error(self):
        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.script_to_url",
            new_callable=AsyncMock,
            return_value="https://hosted/script.docbuilder",
        ), patch(
            "aiecs.tools.office_tool.core.builder_runtime.get_documentserver_client"
        ) as mock_get:
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value={})
            mock_get.return_value = mock_client

            result = await run_builder_script("builder.CloseFile();")

        assert result == {"isError": True, "text": "DocumentServer did not return fileUrl"}


class TestRunBuilderOnSource:
    """Test run_builder_on_source wraps edit scripts."""

    async def test_injects_open_save_close_and_delegates(self):
        captured_script = []

        async def capture_script(script, **kwargs):
            captured_script.append(script)
            return {"success": True, "output_path": kwargs.get("output_path")}

        with patch(
            "aiecs.tools.office_tool.core.builder_runtime.run_builder_script",
            side_effect=capture_script,
        ):
            result = await run_builder_on_source(
                "https://signed/source.docx",
                "docx",
                "oDoc.GetElement(0).SetText('Hi');",
                "gs://bucket/out.docx",
            )

        assert result == {"success": True, "output_path": "gs://bucket/out.docx"}
        script = captured_script[0]
        assert 'builder.OpenFile("https://signed/source.docx", "docx");' in script
        assert "oDoc.GetElement(0).SetText('Hi');" in script
        assert 'builder.SaveFile("docx", "output.docx");' in script
        assert "builder.CloseFile();" in script
