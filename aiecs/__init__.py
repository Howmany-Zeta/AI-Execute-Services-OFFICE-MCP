"""
MCP Server - Office Tools

A standalone MCP (Model Context Protocol) server that exposes office document
tools as MCP tools via JSON-RPC 2.0 over HTTP.
"""

__version__ = "1.0.0"
__author__ = "MCP Server Team"
__email__ = "iretbl@gmail.com"

# MCP Server components
from .mcp import (
    PlaceholderToolAdapter,
    MCPServerConfig,
    get_server_config,
    # FastMCP integration
    create_fastmcp_server,
    # OpenAI format support
    convert_mcp_to_openai_format,
    convert_mcp_tools_to_openai_format,
)

# Minimal base tool (for tools that need executor initialization)
from .mcp.base_tool_minimal import MinimalBaseTool

# Tool executor (needed for caching and metrics)
from .tools.tool_executor import ToolExecutor, get_executor

__all__ = [
    # MCP Server core adapters
    "PlaceholderToolAdapter",
    # Configuration
    "MCPServerConfig",
    "get_server_config",
    # FastMCP integration
    "create_fastmcp_server",
    # OpenAI format support
    "convert_mcp_to_openai_format",
    "convert_mcp_tools_to_openai_format",
    # Base tool
    "MinimalBaseTool",
    # Tool executor
    "ToolExecutor",
    "get_executor",
    # Metadata
    "__version__",
    "__author__",
    "__email__",
]
