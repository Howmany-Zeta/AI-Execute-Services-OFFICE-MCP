"""
Unit tests for OpenAI function calling format conversion.
"""

import pytest
from aiecs.mcp.openai_adapter import (
    convert_mcp_to_openai_format,
    convert_mcp_tools_to_openai_format,
)


def test_convert_mcp_to_openai_format_basic():
    """Test basic MCP to OpenAI format conversion."""
    mcp_tool = {
        "name": "test_tool",
        "description": "Test tool description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1"
                }
            },
            "required": ["param1"]
        }
    }
    
    openai_tool = convert_mcp_to_openai_format(mcp_tool)
    
    assert openai_tool["type"] == "function"
    assert "function" in openai_tool
    assert openai_tool["function"]["name"] == "test_tool"
    assert openai_tool["function"]["description"] == "Test tool description"
    assert openai_tool["function"]["parameters"] == mcp_tool["inputSchema"]


def test_convert_mcp_to_openai_format_minimal():
    """Test conversion with minimal tool definition."""
    mcp_tool = {
        "name": "minimal_tool",
        "description": "",
        "inputSchema": {}
    }
    
    openai_tool = convert_mcp_to_openai_format(mcp_tool)
    
    assert openai_tool["type"] == "function"
    assert openai_tool["function"]["name"] == "minimal_tool"
    assert openai_tool["function"]["description"] == ""
    assert openai_tool["function"]["parameters"]["type"] == "object"


def test_convert_mcp_to_openai_format_missing_fields():
    """Test conversion handles missing optional fields."""
    mcp_tool = {
        "name": "tool_no_description",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
    
    openai_tool = convert_mcp_to_openai_format(mcp_tool)
    
    assert openai_tool["function"]["name"] == "tool_no_description"
    assert openai_tool["function"]["description"] == ""


def test_convert_mcp_to_openai_format_invalid_schema():
    """Test conversion handles invalid inputSchema."""
    mcp_tool = {
        "name": "tool_invalid_schema",
        "description": "Tool with invalid schema",
        "inputSchema": "not a dict"
    }
    
    # Should create default schema
    openai_tool = convert_mcp_to_openai_format(mcp_tool)
    
    assert openai_tool["function"]["parameters"]["type"] == "object"
    assert "properties" in openai_tool["function"]["parameters"]


def test_convert_mcp_to_openai_format_missing_name():
    """Test conversion raises error for missing name."""
    mcp_tool = {
        "description": "Tool without name"
    }
    
    with pytest.raises(ValueError, match="name"):
        convert_mcp_to_openai_format(mcp_tool)


def test_convert_mcp_tools_to_openai_format():
    """Test batch conversion of multiple tools."""
    mcp_tools = [
        {
            "name": "tool1",
            "description": "Tool 1",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "tool2",
            "description": "Tool 2",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "tool3",
            "description": "Tool 3",
            "inputSchema": {"type": "object", "properties": {}}
        }
    ]
    
    openai_tools = convert_mcp_tools_to_openai_format(mcp_tools)
    
    assert len(openai_tools) == 3
    assert openai_tools[0]["function"]["name"] == "tool1"
    assert openai_tools[1]["function"]["name"] == "tool2"
    assert openai_tools[2]["function"]["name"] == "tool3"


def test_convert_mcp_tools_to_openai_format_skips_invalid():
    """Test that tools with missing name are skipped."""
    mcp_tools = [
        {
            "name": "valid_tool",
            "description": "Valid tool",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            # Missing name - should raise ValueError and be skipped
            "description": "Invalid tool"
        }
    ]
    
    openai_tools = convert_mcp_tools_to_openai_format(mcp_tools)
    
    # Invalid tool should be skipped
    assert len(openai_tools) == 1
    assert openai_tools[0]["function"]["name"] == "valid_tool"


def test_convert_mcp_to_openai_format_preserves_schema_properties():
    """Test that all JSON Schema properties are preserved."""
    mcp_tool = {
        "name": "complex_tool",
        "description": "Complex tool",
        "inputSchema": {
            "type": "object",
            "properties": {
                "string_param": {
                    "type": "string",
                    "description": "String parameter",
                    "enum": ["option1", "option2"]
                },
                "number_param": {
                    "type": "number",
                    "description": "Number parameter",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["string_param"],
            "additionalProperties": False
        }
    }
    
    openai_tool = convert_mcp_to_openai_format(mcp_tool)
    params = openai_tool["function"]["parameters"]
    
    # Verify all properties are preserved
    assert params["type"] == "object"
    assert "string_param" in params["properties"]
    assert params["properties"]["string_param"]["enum"] == ["option1", "option2"]
    assert "number_param" in params["properties"]
    assert params["properties"]["number_param"]["minimum"] == 0
    assert params["required"] == ["string_param"]
    assert params["additionalProperties"] is False


def test_office_adapter_openai_format_twenty_three_canonical():
    """OfficeToolAdapter exposes twenty-three canonical tools in OpenAI format (M6 FINAL, OT-138)."""
    from aiecs.mcp.office_tool_adapter import OfficeToolAdapter

    adapter = OfficeToolAdapter()
    openai_tools = adapter.list_tools_openai_format()
    assert len(openai_tools) == 23
    names = {t["function"]["name"] for t in openai_tools}
    assert "office_read_pdf" in names
    assert "office_read_document" not in names
