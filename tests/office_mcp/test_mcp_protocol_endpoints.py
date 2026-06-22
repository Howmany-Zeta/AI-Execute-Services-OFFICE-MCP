"""
Integration tests for MCP protocol endpoints with FastMCP.

Requires a live MCP server at E2E_MCP_URL / MCP_BASE_URL (from `.env.test`).
Run: poetry run pytest tests/office_mcp/test_mcp_protocol_endpoints.py -v -m integration
"""

import json

import httpx
import pytest

from tests.office_mcp.e2e_support import mcp_protocol_url, mcp_reachable

try:
    from fastmcp import FastMCP  # noqa: F401

    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not FASTMCP_AVAILABLE, reason="FastMCP not available"),
    pytest.mark.skipif(not mcp_reachable(), reason="MCP server not reachable at configured URL"),
]


@pytest.fixture
def test_server_url():
    """MCP JSON-RPC URL from `.env.test` (same host as /health probe)."""
    return mcp_protocol_url()


def _parse_jsonrpc_response(response: httpx.Response) -> dict:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                return json.loads(line[6:])
        raise AssertionError("SSE response contained no JSON data line")
    return response.json()


@pytest.mark.asyncio
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
        result = _parse_jsonrpc_response(response)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == "test-1"
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) > 0


@pytest.mark.asyncio
async def test_tools_call_endpoint(test_server_url):
    """Test tools/call endpoint executes tools correctly."""
    async with httpx.AsyncClient(timeout=30.0) as client:
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

        list_result = _parse_jsonrpc_response(list_response)
        tools = list_result["result"]["tools"]
        assert len(tools) > 0

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
        call_result = _parse_jsonrpc_response(call_response)

        assert call_result["jsonrpc"] == "2.0"
        assert call_result["id"] == "test-call"
        assert "result" in call_result or "error" in call_result
