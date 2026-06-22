"""
E2E test: office_read_document against real MinIO + DocumentServer.

Configuration: repository `.env.test` (E2E_MINIO_SOURCE_PATH / E2E_S3_SOURCE_PATH, E2E_MCP_URL).
Skipped when env vars or MCP health check fail.
"""

import json

import httpx
import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import mcp_reachable

_cfg = get_e2e_config()
E2E_MINIO_SOURCE = _cfg.minio_source_path
E2E_MCP_URL = _cfg.mcp_url

requires_minio_e2e = pytest.mark.skipif(
    not E2E_MINIO_SOURCE.startswith("s3://") or not mcp_reachable(),
    reason="E2E_MINIO_SOURCE_PATH (s3://) and reachable E2E_MCP_URL required in .env.test.",
)


@pytest.mark.e2e
@pytest.mark.asyncio
@requires_minio_e2e
async def test_e2e_minio_office_read_document():
    """Real MinIO s3:// path -> MCP proxy -> DocumentServer Conversion API."""
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{E2E_MCP_URL}/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "office_read_document",
                    "arguments": {
                        "source_path": E2E_MINIO_SOURCE,
                        "format": "structured",
                    },
                },
                "id": "pytest-e2e-minio",
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
    resp.raise_for_status()

    if "data: " in resp.text:
        data = next(
            json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")
        )
    else:
        data = resp.json()

    assert "error" not in data, data.get("error")
    content = data["result"]["content"]
    result = json.loads(content[0]["text"])

    assert not result.get("isError"), result.get("text")
    assert result["source_path"] == E2E_MINIO_SOURCE
    assert result["source_path_format"] == "s3://bucket/path/to/file.ext"
    assert "elements" in result
    assert result["word_count"] > 0
