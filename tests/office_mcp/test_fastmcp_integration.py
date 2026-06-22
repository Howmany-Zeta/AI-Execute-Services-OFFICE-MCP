"""
Unit tests for FastMCP integration.

Tests FastMCP server integration, tool registration, and execution.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="FastMCP not available")

if FASTMCP_AVAILABLE:
    from aiecs.mcp.fastmcp_integration import (
        ToolProvider,
        APISourceProvider,
        create_fastmcp_server,
    )


@pytest.fixture
def mock_tool_adapter():
    """Create a mock tool adapter."""
    adapter = Mock()
    adapter.list_tools.return_value = [
        {
            "name": "office_execute_builder",
            "description": "Execute Builder script",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "Builder JS script"},
                    "output_path": {"type": "string", "description": "Optional output path"},
                },
                "required": ["script"],
            },
        }
    ]
    adapter.call_tool = AsyncMock(return_value={
        "type": "text",
        "text": "Test result",
        "isError": False,
    })
    return adapter


@pytest.mark.asyncio
async def test_tool_provider_list_tools(mock_tool_adapter):
    """Test ToolProvider lists tools correctly."""
    provider = ToolProvider(mock_tool_adapter)
    tools = await provider._list_tools()
    assert len(tools) == 1
    assert tools[0].name == "office_execute_builder"


@pytest.mark.asyncio
async def test_tool_provider_get_tool(mock_tool_adapter):
    """Test ToolProvider gets specific tool."""
    provider = ToolProvider(mock_tool_adapter)
    tool = await provider._get_tool("office_execute_builder")
    assert tool is not None
    assert tool.name == "office_execute_builder"
    tool = await provider._get_tool("non_existent")
    assert tool is None


@pytest.mark.asyncio
async def test_tool_provider_tool_execution(mock_tool_adapter):
    """Test tool execution through ToolProvider."""
    provider = ToolProvider(mock_tool_adapter)
    tools = await provider._list_tools()
    tool = tools[0]
    result = await tool.run({"script": "builder.CreateFile('docx');"})
    assert result is not None
    assert hasattr(result, "content")
    mock_tool_adapter.call_tool.assert_called_once_with(
        "office_execute_builder", {"script": "builder.CreateFile('docx');"}
    )


def test_create_fastmcp_server(mock_tool_adapter):
    """Test FastMCP server creation with adapter."""
    server = create_fastmcp_server(tool_adapter=mock_tool_adapter)
    assert server is not None
    assert isinstance(server, FastMCP)


def test_create_fastmcp_server_default():
    """Test FastMCP server creation with default OfficeToolAdapter."""
    from aiecs.mcp.office_tool_adapter import OfficeToolAdapter

    server = create_fastmcp_server()
    assert server is not None
    assert isinstance(server, FastMCP)

    adapter = OfficeToolAdapter()
    tools = adapter.list_tools()
    assert len(tools) == 23
    names = {t["name"] for t in tools}
    assert "office_read_pdf" in names
    assert "office_read_document" not in names
