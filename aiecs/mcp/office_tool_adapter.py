"""
Office tool adapter for MCP server.

Adapts six office tools to MCP: list_tools(), call_tool(), list_tools_openai_format().
"""

import logging
from typing import Any, Dict, List

from aiecs.mcp.openai_adapter import convert_mcp_tools_to_openai_format
from aiecs.tools.office_tool import (
    office_execute_builder,
    office_edit_document,
    office_read_document,
    office_merge_documents,
    office_apply_template,
    office_call_api,
    OFFICE_EXECUTE_BUILDER_TOOL,
    OFFICE_EDIT_DOCUMENT_TOOL,
    OFFICE_READ_DOCUMENT_TOOL,
    OFFICE_MERGE_DOCUMENTS_TOOL,
    OFFICE_APPLY_TEMPLATE_TOOL,
    OFFICE_CALL_API_TOOL,
)

logger = logging.getLogger(__name__)

OFFICE_TOOLS = [
    OFFICE_EXECUTE_BUILDER_TOOL,
    OFFICE_EDIT_DOCUMENT_TOOL,
    OFFICE_READ_DOCUMENT_TOOL,
    OFFICE_MERGE_DOCUMENTS_TOOL,
    OFFICE_APPLY_TEMPLATE_TOOL,
    OFFICE_CALL_API_TOOL,
]

# Map tool name -> (async_func, arg_mapping)
# arg_mapping: MCP argument name -> func kwarg name (or None if same)
_TOOL_HANDLERS: Dict[str, tuple] = {
    "office_execute_builder": (office_execute_builder, None),
    "office_edit_document": (office_edit_document, None),
    "office_read_document": (office_read_document, None),
    "office_merge_documents": (office_merge_documents, None),
    "office_apply_template": (office_apply_template, None),
    "office_call_api": (office_call_api, None),
}


class OfficeToolAdapter:
    """
    MCP adapter for six office document tools.

    Implements list_tools(), call_tool(), list_tools_openai_format().
    """

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions for all six office tools."""
        return [dict(t) for t in OFFICE_TOOLS]

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
        if name not in _TOOL_HANDLERS:
            return {"isError": True, "text": f"Unknown tool: {name}"}

        handler, _ = _TOOL_HANDLERS[name]
        args = dict(arguments) if arguments else {}

        try:
            result = handler(**args)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except TypeError as e:
            logger.warning(f"Tool {name} call failed (wrong args): {e}")
            return {"isError": True, "text": f"Invalid arguments: {e}"}
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return {"isError": True, "text": str(e)}
