"""
Unit tests for office_tool_adapter.

Tests list_tools, list_tools_openai_format, call_tool routing.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch

from aiecs.mcp.office_tool_adapter import OfficeToolAdapter

M6_CANONICAL = 23

CANONICAL_TOOL_NAMES = {
    "office_execute_builder",
    "office_call_api",
    "office_read_word",
    "office_create_word",
    "office_edit_word",
    "office_merge_word",
    "office_apply_template_word",
    "office_edit_word_script",
    "office_read_presentation",
    "office_create_presentation",
    "office_edit_presentation",
    "office_merge_presentations",
    "office_apply_template_presentation",
    "office_read_spreadsheet",
    "office_create_spreadsheet",
    "office_edit_spreadsheet",
    "office_merge_spreadsheets",
    "office_apply_template_spreadsheet",
    "office_read_pdf",
    "office_create_pdf",
    "office_edit_pdf",
    "office_merge_pdfs",
    "office_fill_pdf_form",
}

LEGACY_TOOL_NAMES = {
    "office_read_document",
    "office_edit_document",
    "office_merge_documents",
    "office_apply_template",
}


class TestOfficeToolAdapter:
    """Test OfficeToolAdapter."""

    def test_list_tools_returns_twenty_three_canonical_tools(self):
        """list_tools returns twenty-three canonical office tools (M6 FINAL, ADR-024)."""
        adapter = OfficeToolAdapter()
        tools = adapter.list_tools()
        assert len(tools) == M6_CANONICAL
        names = {t["name"] for t in tools}
        assert names == CANONICAL_TOOL_NAMES
        assert names.isdisjoint(LEGACY_TOOL_NAMES)

    def test_list_tools_matches_registry(self):
        """Adapter list_tools matches registry.collect_office_tools (OT-138 FINAL)."""
        from aiecs.tools.office_tool.registry import collect_office_tools

        adapter = OfficeToolAdapter()
        adapter_names = {t["name"] for t in adapter.list_tools()}
        registry_names = {t["name"] for t in collect_office_tools()}
        assert adapter_names == registry_names
        assert len(adapter_names) == M6_CANONICAL

    def test_list_tools_openai_format(self):
        """list_tools_openai_format returns OpenAI format for canonical tools."""
        adapter = OfficeToolAdapter()
        tools = adapter.list_tools_openai_format()
        assert len(tools) == M6_CANONICAL
        for t in tools:
            assert t.get("type") == "function"
            assert "function" in t
            assert "name" in t["function"]
            assert "parameters" in t["function"]
        openai_names = {t["function"]["name"] for t in tools}
        assert openai_names.isdisjoint(LEGACY_TOOL_NAMES)

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
        with patch(
            "aiecs.mcp.office_tool_adapter.get_handlers",
            return_value={"office_execute_builder": mock},
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
        with patch(
            "aiecs.mcp.office_tool_adapter.get_handlers",
            return_value={"office_call_api": mock},
        ):
            result = await adapter.call_tool(
                "office_call_api",
                {"action": "info", "params": {"key": "doc-key"}},
            )
        assert "isError" not in result
        mock.assert_called_once_with(action="info", params={"key": "doc-key"})

    @pytest.mark.asyncio
    async def test_call_tool_legacy_still_routed(self):
        """Legacy tools remain callable via get_handlers (ADR-024)."""
        adapter = OfficeToolAdapter()
        mock = AsyncMock(return_value={"success": True})
        with patch(
            "aiecs.mcp.office_tool_adapter.get_handlers",
            return_value={"office_read_document": mock},
        ):
            result = await adapter.call_tool(
                "office_read_document",
                {"source_path": "gs://b/doc.docx"},
            )
        assert "isError" not in result
        mock.assert_called_once()
