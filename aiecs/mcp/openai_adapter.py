"""
OpenAI Function Calling Format Adapter

Converts MCP tool definitions to OpenAI function calling format.
This enables compatibility with OpenAI Chat Completions API and OpenAI-compatible clients.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def convert_mcp_to_openai_format(mcp_tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an MCP tool definition to OpenAI function calling format.
    
    OpenAI function calling format:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "Tool description",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
    
    MCP tool format:
    {
        "name": "tool_name",
        "description": "Tool description",
        "inputSchema": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
    
    Args:
        mcp_tool: MCP tool definition with name, description, inputSchema
    
    Returns:
        OpenAI function calling format tool definition
    
    Raises:
        ValueError: If tool definition is invalid
    """
    # Validate required fields
    if not isinstance(mcp_tool, dict):
        raise ValueError("Tool definition must be a dictionary")
    
    tool_name = mcp_tool.get("name")
    if not tool_name or not isinstance(tool_name, str):
        raise ValueError("Tool definition must have a 'name' field (string)")
    
    description = mcp_tool.get("description", "")
    if not isinstance(description, str):
        description = str(description) if description else ""
    
    # Get input schema (MCP format) and use it as parameters (OpenAI format)
    input_schema = mcp_tool.get("inputSchema", {})
    
    # Ensure input_schema is a valid JSON Schema object
    if not isinstance(input_schema, dict):
        # If inputSchema is missing or invalid, create a minimal schema
        input_schema = {"type": "object", "properties": {}, "required": []}
    else:
        # Ensure it has required fields for JSON Schema
        if "type" not in input_schema:
            input_schema["type"] = "object"
        if "properties" not in input_schema:
            input_schema["properties"] = {}
        if "required" not in input_schema:
            input_schema["required"] = []
    
    # Build OpenAI function calling format
    openai_tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": input_schema,  # MCP inputSchema is already in JSON Schema format
        },
    }
    
    return openai_tool


def convert_mcp_tools_to_openai_format(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert a list of MCP tool definitions to OpenAI function calling format.
    
    Args:
        mcp_tools: List of MCP tool definitions
    
    Returns:
        List of OpenAI function calling format tool definitions
    
    Note:
        Tools that fail conversion are logged and skipped.
    """
    openai_tools = []
    
    for mcp_tool in mcp_tools:
        try:
            openai_tool = convert_mcp_to_openai_format(mcp_tool)
            openai_tools.append(openai_tool)
        except ValueError as e:
            tool_name = mcp_tool.get("name", "unknown")
            logger.warning(f"Failed to convert tool '{tool_name}' to OpenAI format: {e}")
            continue
        except Exception as e:
            tool_name = mcp_tool.get("name", "unknown")
            logger.error(f"Unexpected error converting tool '{tool_name}' to OpenAI format: {e}", exc_info=True)
            continue
    
    logger.info(f"Converted {len(openai_tools)}/{len(mcp_tools)} tools to OpenAI format")
    return openai_tools
