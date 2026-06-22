"""
Unit tests for office_call_api tool.

Tests action routing (convert -> Conversion, forcesave/info -> Command),
params validation, API response passthrough (mocked).
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch

from aiecs.tools.office_tool import office_call_api, OFFICE_CALL_API_TOOL


class TestOfficeCallApiToolDefinition:
    """Test tool definition."""

    def test_tool_has_required_schema(self):
        """inputSchema has action, params required."""
        schema = OFFICE_CALL_API_TOOL["inputSchema"]
        assert set(schema["required"]) == {"action", "params"}
        assert schema["properties"]["action"]["enum"] == ["convert", "forcesave", "info"]

    def test_description_has_params_examples(self):
        """Description includes convert, forcesave, info params examples."""
        desc = OFFICE_CALL_API_TOOL["description"]
        assert "convert" in desc
        assert "forcesave" in desc
        assert "info" in desc
        assert "url" in desc
        assert "key" in desc


class TestOfficeCallApi:
    """Test office_call_api execution."""

    @pytest.mark.asyncio
    async def test_missing_action_returns_error(self):
        """Empty action returns error."""
        result = await office_call_api("", {"key": "x"})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self):
        """Invalid action returns error."""
        result = await office_call_api("unknown", {"key": "x"})
        assert result.get("isError") is True
        assert "convert" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_params_not_dict_returns_error(self):
        """params must be dict."""
        result = await office_call_api("info", "not-a-dict")
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_convert_missing_params_returns_error(self):
        """convert requires url, filetype, outputtype, key."""
        result = await office_call_api("convert", {"key": "k"})
        assert result.get("isError") is True
        assert "url" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_forcesave_missing_key_returns_error(self):
        """forcesave requires params.key."""
        result = await office_call_api("forcesave", {})
        assert result.get("isError") is True
        assert "key" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_info_missing_key_returns_error(self):
        """info requires params.key."""
        result = await office_call_api("info", {})
        assert result.get("isError") is True

    @pytest.mark.asyncio
    async def test_convert_calls_conversion_api(self):
        """convert routes to Conversion API, returns response."""
        mock_result = {"endConvert": True, "fileUrl": "http://out.pdf", "fileType": "pdf"}

        with patch("aiecs.tools.office_tool.gateway.call_api.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.convert = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            result = await office_call_api(
                "convert",
                {
                    "url": "https://signed/file.docx",
                    "filetype": "docx",
                    "outputtype": "pdf",
                    "key": "unique-key",
                },
            )

        assert "isError" not in result
        assert result.get("fileUrl") == "http://out.pdf"
        mock_client.convert.assert_called_once()
        call_params = mock_client.convert.call_args[0][0]
        assert call_params["url"] == "https://signed/file.docx"
        assert call_params["filetype"] == "docx"
        assert call_params["outputtype"] == "pdf"
        assert call_params["key"] == "unique-key"

    @pytest.mark.asyncio
    async def test_forcesave_calls_command_api(self):
        """forcesave routes to Command API with c=forcesave."""
        mock_result = {"error": 0, "key": "doc-key"}

        with patch("aiecs.tools.office_tool.gateway.call_api.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.command = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            result = await office_call_api("forcesave", {"key": "doc-key"})

        assert "isError" not in result
        assert result.get("error") == 0
        mock_client.command.assert_called_once_with({"c": "forcesave", "key": "doc-key"})

    @pytest.mark.asyncio
    async def test_info_calls_command_api(self):
        """info routes to Command API with c=info."""
        mock_result = {"error": 0, "key": "doc-key"}

        with patch("aiecs.tools.office_tool.gateway.call_api.get_documentserver_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.command = AsyncMock(return_value=mock_result)
            mock_get.return_value = mock_client

            result = await office_call_api("info", {"key": "doc-key"})

        assert "isError" not in result
        mock_client.command.assert_called_once_with({"c": "info", "key": "doc-key"})
