"""
Integration tests for MCP protocol endpoints with FastMCP.

Tests tools/list and tools/call endpoints through FastMCP.
"""

import pytest
import httpx
import asyncio
from typing import Dict, Any

from tests.office_mcp.e2e_support import mcp_reachable

try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False

pytestmark = [
    pytest.mark.skipif(not FASTMCP_AVAILABLE, reason="FastMCP not available"),
    pytest.mark.skipif(not mcp_reachable(), reason="MCP server not reachable at configured URL"),
]


@pytest.fixture
def test_server_url():
    """Get test server URL."""
    return "http://localhost:5055/mcp/v1/"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tools_list_endpoint(test_server_url):
    """Test tools/list endpoint returns tools correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            test_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "test-1",
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        
        assert response.status_code == 200
        
        # Parse SSE response if needed
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            # Parse SSE format
            text = response.text
            result = None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    import json
                    json_str = line[6:]
                    try:
                        result = json.loads(json_str)
                        break
                    except json.JSONDecodeError:
                        continue
        else:
            result = response.json()
        
        assert result is not None
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == "test-1"
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tools_call_endpoint(test_server_url):
    """Test tools/call endpoint executes tools correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First get list of tools
        list_response = await client.post(
            test_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "test-list",
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        
        # Parse tools list
        list_result = None
        if "text/event-stream" in list_response.headers.get("content-type", ""):
            for line in list_response.text.split("\n"):
                if line.startswith("data: "):
                    import json
                    list_result = json.loads(line[6:])
                    break
        else:
            list_result = list_response.json()
        
        tools = list_result["result"]["tools"]
        assert len(tools) > 0
        
        # Try to call a tool (may fail if tool requires specific params, but should get proper response)
        call_response = await client.post(
            test_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tools[0]["name"],
                    "arguments": {},
                },
                "id": "test-call",
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        
        assert call_response.status_code == 200
        
        # Parse response
        call_result = None
        if "text/event-stream" in call_response.headers.get("content-type", ""):
            for line in call_response.text.split("\n"):
                if line.startswith("data: "):
                    import json
                    call_result = json.loads(line[6:])
                    break
        else:
            call_result = call_response.json()
        
        assert call_result is not None
        assert call_result["jsonrpc"] == "2.0"
        assert call_result["id"] == "test-call"
        # Result may be success or error (depending on tool requirements)
        assert "result" in call_result or "error" in call_result
