"""
Integration tests for MCP server endpoints.

Note: These tests require FastMCP to be available.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    pytest.importorskip("fastmcp")
    from aiecs.main_mcp import app

    with TestClient(app) as test_client:
        yield test_client


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
            "/mcp/v1",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700  # Parse error

    def test_mcp_endpoint_missing_method(self, client):
        """Test MCP endpoint with missing method."""
        response = client.post(
            "/mcp/v1",
            json={"jsonrpc": "2.0", "id": "test"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_mcp_endpoint_initialize(self, client):
        """Test initialize endpoint."""
        response = client.post(
            "/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "test-123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "capabilities" in data["result"]
        assert "serverInfo" in data["result"]

    def test_mcp_endpoint_tools_list(self, client):
        """Test tools/list endpoint."""
        response = client.post(
            "/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "test-123"
            }
        )
        # May return error if providers not initialized, but should be valid JSON-RPC
        assert response.status_code in [200, 500]
        data = response.json()
        assert "jsonrpc" in data
        assert data["jsonrpc"] == "2.0"

    def test_mcp_endpoint_tools_call_missing_params(self, client):
        """Test tools/call with missing parameters."""
        response = client.post(
            "/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": "test-123"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602  # Invalid params

    def test_mcp_endpoint_unknown_method(self, client):
        """Test MCP endpoint with unknown method."""
        response = client.post(
            "/mcp/v1",
            json={
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": "test-123"
            }
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found
