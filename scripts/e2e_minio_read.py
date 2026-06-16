#!/usr/bin/env python3
"""
E2E: office_read_document from real MinIO s3:// via running MCP server.

Must call through MCP HTTP API so /storage-objects tokens are registered in the
server process (in-memory store). Direct import in a separate process will 404.

Usage (inside aiecs-office-mcp container):
  E2E_MINIO_SOURCE_PATH=s3://chatbot-use/path/to/file.docx \
  E2E_MCP_URL=http://127.0.0.1:5040 \
  python scripts/e2e_minio_read.py
"""

import asyncio
import json
import os
import sys


async def main() -> int:
    source = os.environ.get("E2E_MINIO_SOURCE_PATH", "").strip()
    if not source.startswith("s3://"):
        print("E2E_MINIO_SOURCE_PATH must be s3:// URI", file=sys.stderr)
        return 1

    mcp_url = os.environ.get("E2E_MCP_URL", "http://127.0.0.1:5040").rstrip("/")
    fixture_out = os.environ.get("E2E_MINIO_FIXTURE_OUT", "")

    import httpx

    print("=== E2E via MCP HTTP ===")
    print("source_path", source)
    print("mcp_url", mcp_url)

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{mcp_url}/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "office_read_document",
                    "arguments": {"source_path": source, "format": "structured"},
                },
                "id": "e2e-minio-read",
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
    resp.raise_for_status()

    if "data: " in resp.text:
        data = None
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                break
        if data is None:
            print("No SSE data in MCP response", file=sys.stderr)
            return 1
    else:
        data = resp.json()

    if "error" in data:
        print("MCP error:", data["error"], file=sys.stderr)
        return 1

    content = data.get("result", {}).get("content", [])
    if not content:
        print("Empty MCP result", file=sys.stderr)
        return 1

    text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
    result = json.loads(text)
    if result.get("isError"):
        print("READ_FAILED:", result.get("text"), file=sys.stderr)
        return 1

    summary = {
        "source_path": result.get("source_path"),
        "source_path_format": result.get("source_path_format"),
        "accepted_source_path_formats": result.get("accepted_source_path_formats"),
        "title": result.get("title"),
        "word_count": result.get("word_count"),
        "page_count": result.get("page_count"),
        "elements_count": len(result.get("elements", [])),
        "elements_sample": result.get("elements", [])[:3],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if fixture_out:
        with open(fixture_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"fixture_saved {fixture_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
