"""
Tests for OpenAI format endpoint.

Requires live MCP server at MCP_BASE_URL (default http://localhost:5040).
Run: python -m aiecs.main_mcp
"""

import os
import pytest
import httpx
from typing import Dict, Any

MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:5040")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_openai_endpoint_disabled():
    """Test OpenAI endpoint returns 404 when disabled."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MCP_BASE_URL}/openai/v1/tools")
        # Should return 404 when disabled (default)
        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_openai_endpoint_enabled():
    """Test OpenAI endpoint when enabled (requires MCP_ENABLE_OPENAI_FORMAT=true)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MCP_BASE_URL}/openai/v1/tools")
        # If enabled, should return 200 with tools
        # If disabled (default), should return 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "tools" in data
            assert isinstance(data["tools"], list)
            if len(data["tools"]) > 0:
                tool = data["tools"][0]
                assert tool["type"] == "function"
                assert "function" in tool
                assert "name" in tool["function"]
                assert "description" in tool["function"]
                assert "parameters" in tool["function"]
