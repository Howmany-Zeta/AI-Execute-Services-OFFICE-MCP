"""
FastMCP Integration Module

Provides FastMCP server integration with tool adapters.
Supports tool adapters with list_tools() and call_tool().
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Sequence

try:
    from fastmcp import FastMCP
    from fastmcp.tools.tool import Tool, ToolResult
    from fastmcp.server.providers import Provider
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    FastMCP = None
    Tool = None
    ToolResult = None
    Provider = None

logger = logging.getLogger(__name__)


# Only define ToolProvider if FastMCP is available
if FASTMCP_AVAILABLE and Provider is not None:
    class ToolProvider(Provider):
        """
        FastMCP Provider that dynamically provides tools from a tool adapter.
        
        Works with any adapter implementing list_tools() and call_tool().
        Supports both sync and async call_tool.
        """
        
        def __init__(self, tool_adapter: Any):
            """
            Initialize the provider.
            
            Args:
                tool_adapter: Adapter with list_tools() and call_tool()
            """
            super().__init__()
            self.tool_adapter = tool_adapter
            self._tools_cache: Optional[List[Tool]] = None
        
        async def _list_tools(self) -> Sequence[Tool]:
            """
            List all tools from the adapter.
            
            Returns:
                Sequence of Tool instances
            """
            if self._tools_cache is not None:
                return self._tools_cache
            
            # Get MCP tool definitions from adapter
            mcp_tools = self.tool_adapter.list_tools()
            
            # Convert MCP tools to FastMCP Tool instances
            fastmcp_tools = []
            for mcp_tool in mcp_tools:
                try:
                    tool = self._create_tool_from_mcp_tool(mcp_tool)
                    fastmcp_tools.append(tool)
                except Exception as e:
                    logger.warning(f"Failed to create FastMCP tool from {mcp_tool.get('name', 'unknown')}: {e}")
                    continue
            
            self._tools_cache = fastmcp_tools
            logger.info(f"Provider created {len(fastmcp_tools)} FastMCP tools from {len(mcp_tools)} MCP tools")
            return fastmcp_tools
        
        async def _get_tool(self, name: str, version=None) -> Optional[Tool]:
            """
            Get a specific tool by name.
            
            Args:
                name: Tool name
                version: Optional version spec (not used, kept for compatibility with FastMCP Provider interface)
            
            Returns:
                Tool instance or None if not found
            """
            logger.debug(f"APISourceProvider._get_tool called with name: {name}, version: {version}")
            tools = await self._list_tools()
            logger.debug(f"APISourceProvider._get_tool: listed {len(tools)} tools")
            for tool in tools:
                if tool.name == name:
                    logger.debug(f"APISourceProvider._get_tool: found tool {name}")
                    return tool

            # ADR-024: legacy handlers are callable via tools/call but not in list_tools
            from aiecs.tools.office_tool.registry import LEGACY_MODULES, get_handlers
            import importlib

            if name not in get_handlers():
                logger.warning(f"APISourceProvider._get_tool: tool '{name}' not found in {len(tools)} tools")
                if tools:
                    sample_names = [t.name for t in tools[:10]]
                    logger.debug(f"APISourceProvider._get_tool: sample tool names: {sample_names}")
                return None

            listed = {t["name"] for t in self.tool_adapter.list_tools()}
            if name in listed:
                return None

            for mod_path in LEGACY_MODULES:
                mod = importlib.import_module(mod_path)
                for alias_name, _, tool_def in mod.LEGACY_ALIASES:
                    if alias_name == name:
                        logger.debug(f"APISourceProvider._get_tool: legacy alias {name}")
                        return self._create_tool_from_mcp_tool(tool_def)

            return None
        
        def _create_tool_from_mcp_tool(self, mcp_tool: Dict[str, Any]) -> Tool:
            """
            Create a FastMCP Tool from an MCP tool definition.
            
            Args:
                mcp_tool: MCP tool definition with name, description, inputSchema
            
            Returns:
                Tool instance
            """
            if not FASTMCP_AVAILABLE or Tool is None or ToolResult is None:
                raise ImportError("FastMCP is not available")
            
            tool_name = mcp_tool["name"]
            description = mcp_tool.get("description", "")
            input_schema = mcp_tool.get("inputSchema", {})
            
            # Create Tool directly with parameters from inputSchema
            # FastMCP Tool.parameters expects a dict with JSON Schema format
            # MCP inputSchema is already in JSON Schema format, so we can use it directly
            parameters = input_schema if input_schema else {"type": "object", "properties": {}, "required": []}
            
            # Create a custom Tool subclass that implements run() method
            # This avoids the **kwargs limitation of from_function()
            class AdapterTool(Tool):
                """Custom Tool that executes via tool adapter (sync or async call_tool)."""
                
                def __init__(self, name: str, description: str, parameters: Dict[str, Any], tool_adapter: Any):
                    super().__init__(
                        name=name,
                        description=description,
                        parameters=parameters,
                    )
                    self._tool_adapter = tool_adapter
                    self._tool_name = name
                
                async def run(self, arguments: Dict[str, Any]) -> ToolResult:
                    """Execute tool via adapter (supports async call_tool)."""
                    logger.debug(f"AdapterTool.run called for {self._tool_name} with arguments: {arguments}")
                    try:
                        result = self._tool_adapter.call_tool(self._tool_name, arguments)
                        if asyncio.iscoroutine(result):
                            result = await result
                        logger.debug(f"AdapterTool.run: tool call successful for {self._tool_name}")
                        
                        # Convert MCP response to ToolResult
                        if isinstance(result, dict):
                            if result.get("isError", False):
                                error_text = result.get("text", "Tool execution failed")
                                if not error_text or error_text.strip() in ("{}", "''"):
                                    error_text = "Tool execution failed (no details available)"
                                logger.warning(f"AdapterTool.run: tool {self._tool_name} returned error: {error_text}")
                                return ToolResult(
                                    content=json.dumps({"isError": True, "text": error_text}, ensure_ascii=False)
                                )
                            else:
                                # Return JSON for dict results (most office tools)
                                text_content = json.dumps(result, ensure_ascii=False)
                                return ToolResult(content=text_content)
                        else:
                            return ToolResult(content=str(result))
                    except Exception as e:
                        logger.error(f"Error executing tool {self._tool_name}: {e}", exc_info=True)
                        raise
            
            # Create and return the custom tool
            return AdapterTool(
                name=tool_name,
                description=description,
                parameters=parameters,
                tool_adapter=self.tool_adapter,
            )
        
        def clear_cache(self):
            """Clear the tools cache to force re-discovery."""
            self._tools_cache = None

    # Backward compatibility alias
    APISourceProvider = ToolProvider
else:
    class ToolProvider:
        """Placeholder when FastMCP is not available."""
        pass
    APISourceProvider = ToolProvider


def create_fastmcp_server(
    tool_adapter: Optional[Any] = None,
    name: str = "Office MCP Server",
) -> Optional[FastMCP]:
    """
    Create a FastMCP server instance with tool adapter integration.
    
    Args:
        tool_adapter: Tool adapter with list_tools() and call_tool(). Defaults to PlaceholderToolAdapter.
        name: Server name
    
    Returns:
        FastMCP server instance, or None if FastMCP is not available
    """
    if not FASTMCP_AVAILABLE:
        logger.warning("FastMCP is not available. Install with: pip install 'fastmcp>=3.0.0b1'")
        return None
    
    if tool_adapter is None:
        from aiecs.mcp.office_tool_adapter import OfficeToolAdapter
        tool_adapter = OfficeToolAdapter()
    
    mcp = FastMCP(name)
    tool_provider = ToolProvider(tool_adapter)
    mcp.add_provider(tool_provider)
    
    # Discover tools to log how many we have
    mcp_tools = tool_adapter.list_tools()
    logger.info(f"FastMCP server will expose {len(mcp_tools)} tools via Provider")
    
    return mcp
