"""
E2E test: office_read_document against real MinIO + DocumentServer.

Requires:
- Running aiecs-office-mcp with MINIO_* and DOCUMENTSERVER_* configured
- E2E_MINIO_SOURCE_PATH=s3://bucket/path/file.docx
- E2E_MCP_URL (default http://127.0.0.1:5040)

Skipped when env vars or MCP health check fail.
"""

import json
import os

import httpx
import pytest

E2E_MINIO_SOURCE = os.environ.get("E2E_MINIO_SOURCE_PATH", "").strip()
E2E_MCP_URL = os.environ.get("E2E_MCP_URL", "http://127.0.0.1:5040").rstrip("/")


def _mcp_reachable() -> bool:
    try:
        r = httpx.get(f"{E2E_MCP_URL}/health/live", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


requires_minio_e2e = pytest.mark.skipif(
    not E2E_MINIO_SOURCE.startswith("s3://") or not _mcp_reachable(),
    reason="E2E_MINIO_SOURCE_PATH (s3://) and reachable E2E_MCP_URL required.",
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
            json.loads(line[6:])
            for line in resp.text.split("\n")
            if line.startswith("data: ")
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
