"""
Placeholder tool adapter for MCP server.

Legacy placeholder; office_tool_adapter is now the default.
Exposes empty tools so the server can start.
"""

from typing import Any, Dict, List


class PlaceholderToolAdapter:
    """
    Minimal adapter with no tools. Replaced by OfficeToolAdapter in section 9.
    """

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return empty tool list."""
        return []

    def list_tools_openai_format(self) -> List[Dict[str, Any]]:
        """Return empty OpenAI-format tool list."""
        return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return error - no tools implemented yet."""
        return {
            "isError": True,
            "text": "Tool adapter not yet implemented. Run section 9 to add office_tool_adapter.",
        }
