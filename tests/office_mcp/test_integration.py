"""
Integration tests for MCP server endpoints.

Note: These tests require FastMCP to be available.
"""

import pytest

from tests.office_mcp.conftest import MCP_TEST_HEADERS as _MCP_HEADERS
from tests.office_mcp.conftest import parse_mcp_response


class TestMCPEndpoints:
    """Integration tests for MCP HTTP endpoints."""

    def test_health_endpoint(self, client):
        """Test readiness/deep health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == "1.0.0"
        assert data.get("probe") == "readiness"
        assert data.get("tool_count") == 23
        assert data.get("canonical_count") == 23
        assert data.get("registered_handler_count") == 27

    def test_health_live_endpoint(self, client):
        """Pure liveness: no Document Server / Redis probing."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "alive"
        assert data.get("probe") == "liveness"
        assert data.get("server_type") == "office_mcp"

    def test_health_probe_matches_health(self, client):
        """Deep check alias parity with GET /health."""
        r1 = client.get("/health")
        r2 = client.get("/health/probe")
        assert r1.status_code == r2.status_code == 200
        assert r1.json() == r2.json()

    def test_mcp_endpoint_invalid_json(self, client):
        """Test MCP endpoint with invalid JSON."""
        response = client.post(
            "/mcp/v1/",
            content="invalid json",
            headers=_MCP_HEADERS,
        )
        assert response.status_code in (400, 406)
        if response.status_code == 400:
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == -32700  # Parse error

    def test_mcp_endpoint_missing_method(self, client):
        """Test MCP endpoint with missing method."""
        response = client.post(
            "/mcp/v1/",
            json={"jsonrpc": "2.0", "id": "test"},
            headers=_MCP_HEADERS,
        )
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            data = parse_mcp_response(response)
            assert "error" in data
        else:
            data = response.json()
            assert "error" in data

    def test_mcp_endpoint_initialize(self, client):
        """Test initialize endpoint."""
        response = client.post(
            "/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
                "id": "test-123",
            },
            headers=_MCP_HEADERS,
        )
        assert response.status_code == 200
        data = parse_mcp_response(response)
        assert "result" in data
        assert "capabilities" in data["result"]
        assert "serverInfo" in data["result"]

    def test_mcp_endpoint_tools_list(self, client):
        """Test tools/list endpoint returns twenty-three canonical tools (M6 FINAL, ADR-024)."""
        response = client.post(
            "/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "test-123",
            },
            headers=_MCP_HEADERS,
        )
        assert response.status_code == 200
        data = parse_mcp_response(response)
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        tools = data["result"].get("tools", [])
        names = {t.get("name") for t in tools}
        assert len(tools) == 23
        assert "office_read_pdf" in names
        assert "office_read_document" not in names

    def test_mcp_endpoint_tools_call_missing_params(self, client):
        """Test tools/call with missing parameters."""
        response = client.post(
            "/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": "test-123",
            },
            headers=_MCP_HEADERS,
        )
        assert response.status_code == 200
        data = parse_mcp_response(response)
        assert "error" in data

    def test_mcp_endpoint_unknown_method(self, client):
        """Test MCP endpoint with unknown method."""
        response = client.post(
            "/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": "test-123",
            },
            headers=_MCP_HEADERS,
        )
        assert response.status_code == 200
        data = parse_mcp_response(response)
        assert "error" in data
