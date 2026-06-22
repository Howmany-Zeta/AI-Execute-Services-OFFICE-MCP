"""
Office tool adapter for MCP server.

Adapts office tools to MCP via registry: list_tools(), call_tool(), list_tools_openai_format().
"""

import logging
from typing import Any, Dict, List

from aiecs.mcp.openai_adapter import convert_mcp_tools_to_openai_format
from aiecs.mcp.security import sanitize_error_message
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers

logger = logging.getLogger(__name__)


class OfficeToolAdapter:
    """
    MCP adapter for office document tools.

    Implements list_tools(), call_tool(), list_tools_openai_format().
    """

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return canonical MCP tool definitions (legacy excluded, ADR-024)."""
        return collect_office_tools()

    def list_tools_openai_format(self) -> List[Dict[str, Any]]:
        """Return tools in OpenAI function calling format."""
        return convert_mcp_tools_to_openai_format(self.list_tools())

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute office tool by name with given arguments.

        Args:
            name: Tool name (e.g. office_execute_builder)
            arguments: Dict of arguments (from MCP/OpenAI format)

        Returns:
            Tool result dict. Success: {"success": True, ...} or API response.
            Error: {"isError": True, "text": str}
        """
        handlers = get_handlers()
        if name not in handlers:
            return err(f"Unknown tool: {name}")

        handler = handlers[name]
        args = dict(arguments) if arguments else {}

        try:
            result = handler(**args)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except TypeError as e:
            logger.warning(f"Tool {name} call failed (wrong args): {e}")
            return {"isError": True, "text": sanitize_error_message(f"Invalid arguments: {e}")}
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return {"isError": True, "text": sanitize_error_message(str(e))}
