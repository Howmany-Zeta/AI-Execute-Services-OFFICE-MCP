"""
Unit tests for office_tool_adapter.

Tests list_tools, list_tools_openai_format, call_tool routing.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch

from aiecs.mcp.office_tool_adapter import OfficeToolAdapter, OFFICE_TOOLS


class TestOfficeToolAdapter:
    """Test OfficeToolAdapter."""

    def test_list_tools_returns_six_tools(self):
        """list_tools returns six office tools."""
        adapter = OfficeToolAdapter()
        tools = adapter.list_tools()
        assert len(tools) == 6
        names = {t["name"] for t in tools}
        assert names == {
            "office_execute_builder",
            "office_edit_document",
            "office_read_document",
            "office_merge_documents",
            "office_apply_template",
            "office_call_api",
        }

    def test_list_tools_openai_format(self):
        """list_tools_openai_format returns OpenAI format."""
        adapter = OfficeToolAdapter()
        tools = adapter.list_tools_openai_format()
        assert len(tools) == 6
        for t in tools:
            assert t.get("type") == "function"
            assert "function" in t
            assert "name" in t["function"]
            assert "parameters" in t["function"]

    @pytest.mark.asyncio
    async def test_call_tool_unknown_returns_error(self):
        """Unknown tool returns error."""
        adapter = OfficeToolAdapter()
        result = await adapter.call_tool("unknown_tool", {})
        assert result.get("isError") is True
        assert "Unknown" in result.get("text", "")

    @pytest.mark.asyncio
    async def test_call_tool_office_execute_builder(self):
        """call_tool routes to office_execute_builder."""
        adapter = OfficeToolAdapter()
        mock = AsyncMock(return_value={"success": True, "file_url": "http://x"})
        with patch.dict(
            "aiecs.mcp.office_tool_adapter._TOOL_HANDLERS",
            {"office_execute_builder": (mock, None)},
            clear=False,
        ):
            result = await adapter.call_tool(
                "office_execute_builder",
                {"script": "builder.CreateFile('docx');"},
            )
        assert "isError" not in result
        assert result.get("file_url") == "http://x"
        mock.assert_called_once_with(script="builder.CreateFile('docx');")

    @pytest.mark.asyncio
    async def test_call_tool_office_call_api(self):
        """call_tool routes to office_call_api."""
        adapter = OfficeToolAdapter()
        mock = AsyncMock(return_value={"error": 0, "key": "k"})
        with patch.dict(
            "aiecs.mcp.office_tool_adapter._TOOL_HANDLERS",
            {"office_call_api": (mock, None)},
            clear=False,
        ):
            result = await adapter.call_tool(
                "office_call_api",
                {"action": "info", "params": {"key": "doc-key"}},
            )
        assert "isError" not in result
        mock.assert_called_once_with(action="info", params={"key": "doc-key"})
