"""
Tests for OpenAI format endpoint.

Requires live MCP server (E2E_MCP_URL / MCP_BASE_URL from `.env.test`).
Run: poetry run pytest tests/office_mcp/test_openai_endpoint.py -v -m integration
"""

import os

import httpx
import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import mcp_reachable

MCP_BASE_URL = get_e2e_config().mcp_url

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not mcp_reachable(), reason="MCP server not reachable at configured URL"),
]


def _openai_format_enabled() -> bool:
    return os.environ.get("MCP_ENABLE_OPENAI_FORMAT", "").strip().lower() in ("1", "true", "yes")


@pytest.mark.asyncio
async def test_openai_endpoint_disabled():
    """Test OpenAI endpoint returns 404 when disabled."""
    if _openai_format_enabled():
        pytest.skip("MCP_ENABLE_OPENAI_FORMAT is enabled; disabled-behavior test not applicable")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MCP_BASE_URL}/openai/v1/tools")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_openai_endpoint_enabled():
    """Test OpenAI endpoint when enabled (requires MCP_ENABLE_OPENAI_FORMAT=true)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{MCP_BASE_URL}/openai/v1/tools")
        if not _openai_format_enabled():
            assert response.status_code == 404
            return

        assert response.status_code == 200
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
