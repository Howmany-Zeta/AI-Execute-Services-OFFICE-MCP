"""
Tests for provider metadata endpoints.

Office MCP server does not expose /providers (FastMCP tool provider only).
"""

import pytest

pytestmark = pytest.mark.skip(reason="Office MCP has no /providers endpoint")


def test_list_providers_endpoint(client):
    """Test GET /providers endpoint returns all providers."""
    response = client.get("/providers")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "providers" in data
    assert "count" in data
    assert isinstance(data["providers"], list)
    assert data["count"] == len(data["providers"])
    assert data["count"] > 0
    
    # Check first provider structure
    if data["providers"]:
        provider = data["providers"][0]
        assert "name" in provider
        assert "description" in provider
        assert "operations" in provider
        assert "health" in provider


def test_get_provider_endpoint(client):
    """Test GET /providers/{provider_name} endpoint returns provider metadata."""
    # First get list to find a valid provider
    list_response = client.get("/providers")
    assert list_response.status_code == 200
    providers = list_response.json()["providers"]
    
    if not providers:
        pytest.skip("No providers available for testing")
    
    provider_name = providers[0]["name"]
    
    # Get specific provider
    response = client.get(f"/providers/{provider_name}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == provider_name
    assert "description" in data
    assert "operations" in data
    assert isinstance(data["operations"], list)
    
    # Check operations have schemas
    if data["operations"]:
        operation = data["operations"][0]
        assert "name" in operation
        assert "schema" in operation


def test_get_provider_endpoint_not_found(client):
    """Test GET /providers/{provider_name} returns 404 for non-existent provider."""
    response = client.get("/providers/nonexistent_provider_xyz")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_provider_operations_include_schemas(client):
    """Test that provider operations include schema information."""
    # Get a provider with operations
    list_response = client.get("/providers")
    providers = list_response.json()["providers"]
    
    # Find a provider with operations
    provider_with_ops = None
    for provider in providers:
        if provider.get("operations") and len(provider["operations"]) > 0:
            provider_with_ops = provider
            break
    
    if not provider_with_ops:
        pytest.skip("No provider with operations available")
    
    provider_name = provider_with_ops["name"]
    
    # Get detailed metadata
    response = client.get(f"/providers/{provider_name}")
    assert response.status_code == 200
    data = response.json()
    
    # Check operations have schemas
    assert len(data["operations"]) > 0
    for operation in data["operations"]:
        assert "name" in operation
        # Schema may be None if unavailable, but should be present
        assert "schema" in operation
