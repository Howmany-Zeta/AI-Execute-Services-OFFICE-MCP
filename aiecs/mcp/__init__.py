"""
MCP (Model Context Protocol) Server Module

This module provides MCP server implementation using FastMCP SDK.
Exposes office document tools as MCP tools (placeholder until section 9).
"""

from aiecs.mcp.base_tool_minimal import MinimalBaseTool

from aiecs.mcp.placeholder_adapter import PlaceholderToolAdapter

from aiecs.mcp.config import MCPServerConfig, get_server_config
from aiecs.mcp.security import (
    sanitize_error_message,
    validate_request_size,
    sanitize_input,
    validate_jsonrpc_params,
    redact_sensitive_data,
)

# FastMCP integration (only if available)
try:
    from aiecs.mcp.fastmcp_integration import (
        APISourceProvider,
        create_fastmcp_server,
    )
    FASTMCP_INTEGRATION_AVAILABLE = True
except ImportError:
    FASTMCP_INTEGRATION_AVAILABLE = False
    APISourceProvider = None
    create_fastmcp_server = None

# OpenAI format support
from aiecs.mcp.openai_adapter import (
    convert_mcp_to_openai_format,
    convert_mcp_tools_to_openai_format,
)

__all__ = [
    # Core adapters
    "MinimalBaseTool",
    "PlaceholderToolAdapter",
    # Configuration
    "MCPServerConfig",
    "get_server_config",
    # Security utilities
    "sanitize_error_message",
    "validate_request_size",
    "sanitize_input",
    "validate_jsonrpc_params",
    "redact_sensitive_data",
    # FastMCP integration (conditional)
    # Note: APISourceProvider and create_fastmcp_server may be None if FastMCP is not installed
    # OpenAI format support
    "convert_mcp_to_openai_format",
    "convert_mcp_tools_to_openai_format",
]
