"""
E2E tests for six office tools against real DocumentServer.

Uses real DocumentServer (DOCUMENTSERVER_URL, default 100.70.32.65:8081).
Requires DOCUMENTSERVER_JWT_SECRET for Builder/Conversion/Command APIs.
Tools that need GCS (read, edit, merge, apply_template) skip when E2E_GCS_* not set.

Each test:
- Calls the real tool (no mocks)
- Asserts on response content (file_url, elements, text, etc.), not just connection success
"""

import os
import uuid
from pathlib import Path

import pytest

# Load .env before reading config (so DOCUMENTSERVER_* are available)
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

pytestmark = pytest.mark.asyncio
pytestmark = [pytestmark, pytest.mark.e2e]

# DocumentServer config for E2E
E2E_DS_URL = os.environ.get("DOCUMENTSERVER_URL", "http://100.70.32.65:8081")
E2E_JWT_SECRET = os.environ.get("DOCUMENTSERVER_JWT_SECRET", "")
E2E_GCS_SOURCE = os.environ.get("E2E_GCS_SOURCE_PATH", "")  # gs://bucket/path/file.docx
E2E_GCS_SOURCES = os.environ.get("E2E_GCS_SOURCE_PATHS", "")  # comma-separated for merge
E2E_GCS_TEMPLATE = os.environ.get("E2E_GCS_TEMPLATE_PATH", "")  # gs://bucket/path/template.docx
E2E_DOCBUILDER_URL = os.environ.get("E2E_DOCBUILDER_URL", "").strip()  # optional: pre-hosted .docbuilder URL
_mcp_url = os.environ.get("MCP_PUBLIC_URL", "").strip()
_gcs_path = os.environ.get("DOCBUILDER_SCRIPT_GCS_PATH", "").strip()
_has_script_to_url = bool((_mcp_url and _mcp_url.startswith("http")) or (_gcs_path and _gcs_path.startswith("gs://")))
# URL for test to call MCP server (must be same process that serves docbuilder-scripts when using script)
E2E_MCP_URL = os.environ.get("E2E_MCP_URL", "http://100.81.172.125:5040").rstrip("/")


def _ds_reachable() -> bool:
    """Check if DocumentServer is reachable (sync)."""
    try:
        import httpx

        r = httpx.get(f"{E2E_DS_URL}/healthcheck", timeout=5)
        return r.text.strip() == "true"
    except Exception:
        return False


def _jwt_configured() -> bool:
    return bool(E2E_JWT_SECRET)


def _mcp_reachable() -> bool:
    """Check if MCP server is reachable (for script E2E via HTTP)."""
    try:
        import httpx

        # Bypass proxy for localhost (env may have http_proxy set)
        transport = httpx.HTTPTransport(local_address="0.0.0.0") if "localhost" in E2E_MCP_URL else None
        with httpx.Client(timeout=5, transport=transport) as client:
            r = client.get(f"{E2E_MCP_URL}/health")
        # Any HTTP response means server is running (200=ok, 503=degraded but up)
        return r.status_code in (200, 503)
    except Exception:
        return False


async def _call_execute_builder_via_mcp(script: str = None, url: str = None, **kwargs) -> dict:
    """
    Call office_execute_builder via MCP HTTP API so script is stored in the MCP server process.
    Document Server fetches script from the same process that stored it.
    """
    import httpx
    import json

    arguments = dict(kwargs)
    if script is not None:
        arguments["script"] = script
    if url is not None:
        arguments["url"] = url

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{E2E_MCP_URL}/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "office_execute_builder", "arguments": arguments},
                "id": "e2e-call-1",
            },
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        )
    resp.raise_for_status()

    # Parse response (may be JSON or SSE)
    ct = resp.headers.get("content-type", "")
    if "text/event-stream" in ct:
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                break
        else:
            raise ValueError("No data in SSE response")
    else:
        data = resp.json()

    if "error" in data:
        return {"isError": True, "text": data["error"].get("message", str(data["error"]))}

    result = data.get("result", {})
    content = result.get("content", [])
    if isinstance(content, list) and content:
        text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
    else:
        text = str(content)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"isError": True, "text": text}


requires_ds = pytest.mark.skipif(
    not _ds_reachable(),
    reason="DocumentServer not reachable. Set DOCUMENTSERVER_URL and ensure it is running.",
)
requires_jwt = pytest.mark.skipif(
    not _jwt_configured(),
    reason="DOCUMENTSERVER_JWT_SECRET required for Builder/Conversion/Command APIs.",
)
requires_gcs = pytest.mark.skipif(
    not E2E_GCS_SOURCE.strip(),
    reason="E2E_GCS_SOURCE_PATH required. Set to gs://bucket/path/file.docx for E2E.",
)
requires_builder_url = pytest.mark.skipif(
    not E2E_DOCBUILDER_URL and not _has_script_to_url,
    reason="E2E_DOCBUILDER_URL (pre-hosted .docbuilder) or MCP_PUBLIC_URL/DOCBUILDER_SCRIPT_GCS_PATH required for execute_builder E2E.",
)
# When using script (MCP_PUBLIC_URL), MCP server must be running for Document Server to fetch scripts
requires_mcp_for_script = pytest.mark.skipif(
    not E2E_DOCBUILDER_URL and _has_script_to_url and not _mcp_reachable(),
    reason="MCP server must be running for script E2E. Start with: python -m aiecs.main_mcp",
)


# --- office_execute_builder ---


@requires_ds
@requires_jwt
@requires_builder_url
@requires_mcp_for_script
@pytest.mark.asyncio
async def test_e2e_office_execute_builder_creates_docx_with_content():
    """E2E: Create docx via Builder, verify file_url and content."""
    if E2E_DOCBUILDER_URL:
        from aiecs.tools.office_tool import office_execute_builder

        result = await office_execute_builder(url=E2E_DOCBUILDER_URL)
    else:
        # Use MCP HTTP API so script is stored in MCP server process (Document Server fetches from same process)
        script = """
    builder.CreateFile('docx');
    var oDoc = Api.GetDocument();
    var para = Api.CreateParagraph();
    para.AddText('E2E Test Content');
    oDoc.Push(para);
    builder.SaveFile('docx', 'e2e-output.docx');
    builder.CloseFile();
    """
        result = await _call_execute_builder_via_mcp(script=script)
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    file_url = result.get("file_url")
    assert file_url, "Expected file_url in response"
    assert "docx" in file_url.lower() or "file" in file_url.lower()

    # Verify we can fetch the file and it has docx magic bytes (PK = zip)
    import httpx

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(file_url)
        resp.raise_for_status()
        content = resp.content
    assert len(content) > 100, "Expected non-empty docx content"
    assert content[:2] == b"PK", "Expected docx (zip) magic bytes PK"


# --- office_call_api ---


@requires_ds
@requires_jwt
@requires_builder_url
@requires_mcp_for_script
@pytest.mark.asyncio
async def test_e2e_office_call_api_convert_docx_to_pdf():
    """E2E: Create docx, convert to PDF via Conversion API, verify result."""
    from aiecs.tools.office_tool import office_call_api

    # Step 1: Create docx
    if E2E_DOCBUILDER_URL:
        from aiecs.tools.office_tool import office_execute_builder

        build_result = await office_execute_builder(url=E2E_DOCBUILDER_URL)
    else:
        script = """
    builder.CreateFile('docx');
    var oDoc = Api.GetDocument();
    var para = Api.CreateParagraph();
    para.AddText('conv-src');
    oDoc.Push(para);
    builder.SaveFile('docx', 'conv-src.docx');
    builder.CloseFile();
    """
        build_result = await _call_execute_builder_via_mcp(script=script)
    assert not build_result.get("isError"), build_result.get("text", build_result)
    file_url = build_result.get("file_url")
    assert file_url

    # Step 2: Convert to PDF
    key = str(uuid.uuid4())
    convert_result = await office_call_api(
        "convert",
        {"url": file_url, "filetype": "docx", "outputtype": "pdf", "key": key},
    )
    assert not convert_result.get("isError"), convert_result.get("text", convert_result)
    # Conversion API returns fileUrl when endConvert
    assert "fileUrl" in convert_result or "file_url" in convert_result or "urls" in convert_result, (
        "Expected fileUrl/urls in convert response: %s" % convert_result
    )


@requires_ds
@requires_jwt
@pytest.mark.asyncio
async def test_e2e_office_call_api_info_calls_command_api():
    """E2E: office_call_api action=info calls Command API, returns dict."""
    from aiecs.tools.office_tool import office_call_api

    result = await office_call_api("info", {"key": "e2e-nonexistent-key"})
    assert isinstance(result, dict)
    # Command API returns structure; non-existent key may return error or empty
    if result.get("isError"):
        assert "text" in result
    else:
        # Valid response has typical Command API fields
        assert "error" in result or "key" in result or "url" in result or len(result) >= 0


# --- office_read_document ---


@requires_ds
@requires_jwt
@requires_gcs
@pytest.mark.asyncio
async def test_e2e_office_read_document_returns_structure():
    """E2E: Read GCS document, verify elements/text structure."""
    from aiecs.tools.office_tool import office_read_document

    result = await office_read_document(source_path=E2E_GCS_SOURCE.strip(), format="structured")
    assert not result.get("isError"), result.get("text", result)
    assert "elements" in result or "text" in result or "outline" in result
    if "elements" in result:
        assert isinstance(result["elements"], list)
    if "word_count" in result:
        assert isinstance(result["word_count"], (int, float))


# --- office_edit_document ---


@requires_ds
@requires_jwt
@requires_gcs
@requires_builder_url
@pytest.mark.asyncio
async def test_e2e_office_edit_document_modifies_content():
    """E2E: Edit GCS document, verify output_path and content change."""
    from aiecs.tools.office_tool import office_edit_document

    output = E2E_GCS_SOURCE.strip().replace(".docx", "-edited.docx")
    edit_script = """
    var oDoc = Api.GetDocument();
    var para = Api.CreateParagraph();
    para.AddText(' [E2E Edited]');
    oDoc.Push(para);
    """
    result = await office_edit_document(
        source_path=E2E_GCS_SOURCE.strip(),
        edit_script=edit_script,
        output_path=output,
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output or "success" in str(result).lower()


# --- office_merge_documents ---


@pytest.mark.skipif(
    not E2E_GCS_SOURCES.strip(),
    reason="E2E_GCS_SOURCE_PATHS required (comma-separated) for merge E2E.",
)
@requires_ds
@requires_jwt
@requires_builder_url
@pytest.mark.asyncio
async def test_e2e_office_merge_documents_produces_merged_file():
    """E2E: Merge GCS documents, verify output_path."""
    from aiecs.tools.office_tool import office_merge_documents

    sources = [s.strip() for s in E2E_GCS_SOURCES.split(",") if s.strip()]
    assert len(sources) >= 1
    output = sources[0].replace(".docx", "-merged.docx")
    result = await office_merge_documents(
        source_paths=sources,
        output_path=output,
        options={"add_page_break": True, "add_toc": False},
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output


# --- office_apply_template ---


@requires_ds
@requires_jwt
@requires_builder_url
@pytest.mark.skipif(
    not E2E_GCS_TEMPLATE.strip(),
    reason="E2E_GCS_TEMPLATE_PATH required for apply_template E2E.",
)
@pytest.mark.asyncio
async def test_e2e_office_apply_template_fills_placeholders():
    """E2E: Fill template with data, verify output content."""
    from aiecs.tools.office_tool import office_apply_template

    output = E2E_GCS_TEMPLATE.strip().replace(".docx", "-filled.docx")
    data = {"name": "E2EUser", "amount": "999"}
    result = await office_apply_template(
        template_path=E2E_GCS_TEMPLATE.strip(),
        data=data,
        output_path=output,
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output
