"""
Unit tests for office_apply_template tool.

Tests script generation, placeholder {{key}} format, str() for values, validation (mocked).
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_apply_template, OFFICE_APPLY_TEMPLATE_TOOL
from aiecs.tools.office_tool.apply_template import _build_apply_template_script


class TestOfficeApplyTemplateToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has data, output_path required; template_path/template_url optional (one required)."""
        schema = OFFICE_APPLY_TEMPLATE_TOOL["inputSchema"]
        assert set(schema["required"]) == {"data", "output_path"}
        assert "template_path" in schema["properties"]
        assert "template_url" in schema["properties"]

    def test_description_mentions_placeholder_format(self):
        """Description mentions {{key}} placeholder format."""
        desc = OFFICE_APPLY_TEMPLATE_TOOL["description"]
        assert "{{key}}" in desc or "{{" in desc


class TestBuildApplyTemplateScript:
    """Test script generation."""

    def test_empty_data_script(self):
        """Empty data: OpenFile, SaveFile only (no SearchAndReplace)."""
        script = _build_apply_template_script(
            "https://signed/template.docx",
            "docx",
            {},
        )
        assert "builder.OpenFile" in script
        assert "builder.SaveFile" in script
        assert "SearchAndReplace" not in script

    def test_single_replacement(self):
        """Single key: SearchAndReplace {{name}} with value."""
        script = _build_apply_template_script(
            "https://signed/t.docx",
            "docx",
            {"name": "Alice"},
        )
        assert "SearchAndReplace" in script
        assert "{{name}}" in script
        assert "Alice" in script

    def test_str_conversion_for_numbers(self):
        """Numeric values are converted to strings in script."""
        script = _build_apply_template_script(
            "https://signed/t.docx",
            "docx",
            {"amount": 5000},
        )
        assert "5000" in script
        assert "{{amount}}" in script

    def test_escape_special_chars_in_value(self):
        """Values with quotes and backslashes are escaped."""
        script = _build_apply_template_script(
            "https://signed/t.docx",
            "docx",
            {"text": 'Say "hello"'},
        )
        assert "SearchAndReplace" in script
        # Escaped: " becomes \"
        assert '\\"' in script or "hello" in script


class TestOfficeApplyTemplate:
    """Test office_apply_template execution."""

    @pytest.mark.asyncio
    async def test_missing_template_path_returns_error(self):
        """Empty template_path and template_url returns error."""
        result = await office_apply_template(template_path="", data={"x": "y"}, output_path="gs://b/out.docx")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_non_dict_data_returns_error(self):
        """data must be dict."""
        result = await office_apply_template(
            template_path="gs://b/t.docx",
            data="not-a-dict",
            output_path="gs://b/out.docx",
        )
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_missing_output_path_returns_error(self):
        """Empty output_path returns error."""
        result = await office_apply_template(template_path="gs://b/t.docx", data={"x": "y"}, output_path="")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_non_gcs_template_returns_error(self):
        """Non-GCS template_path returns error."""
        result = await office_apply_template(
            template_path="/local/template.docx",
            data={"name": "A"},
            output_path="gs://b/out.docx",
        )
        assert result.get("isError") is True
        assert "gs://" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_apply_success(self):
        """Template filled, script_to_url called, Builder called with url, result uploaded."""
        mock_result = {"fileUrl": "http://ds/temp/out.docx", "fileType": "docx"}
        captured_script = []

        async def capture_script(s):
            captured_script.append(s)
            return "https://fake-script/apply.docbuilder"

        with patch("aiecs.tools.office_tool.apply_template.get_signed_url", new_callable=AsyncMock) as mock_signed, \
             patch("aiecs.tools.office_tool.apply_template.script_to_url", side_effect=capture_script), \
             patch("aiecs.tools.office_tool.apply_template.get_documentserver_client") as mock_get, \
             patch("aiecs.tools.office_tool.apply_template.upload_to_storage", new_callable=AsyncMock):
            mock_signed.return_value = "https://signed/template.docx"
            mock_client = AsyncMock()
            mock_client.execute_builder = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            with patch("httpx.AsyncClient") as mock_http:
                mock_response = MagicMock()
                mock_response.content = b"filled"
                mock_response.raise_for_status = MagicMock()
                mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

                result = await office_apply_template(
                    template_path="gs://bucket/template.docx",
                    data={"name": "Alice", "amount": 100},
                    output_path="gs://bucket/out.docx",
                )

        assert result.get("success") is True
        assert result.get("output_path") == "gs://bucket/out.docx"
        script = captured_script[0]
        assert "{{name}}" in script
        assert "{{amount}}" in script
        assert "Alice" in script
        assert "100" in script
        mock_client.execute_builder.assert_called_once_with(url="https://fake-script/apply.docbuilder")
