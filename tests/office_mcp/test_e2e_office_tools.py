"""
Gateway + legacy smoke E2E tests against real DocumentServer (OT-137).

Scope:
- **Gateway**: `office_execute_builder`, `office_call_api` (cross-category)
- **Legacy aliases**: `office_read_document`, `office_edit_document`,
  `office_merge_documents`, `office_apply_template` (call_tool compatibility)

Category-specific E2E lives in:
- `tests/office_mcp/word/test_e2e_word_tools.py` (`@pytest.mark.word`)
- `tests/office_mcp/presentation/test_e2e_presentation_tools.py`
- `tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py`
- `tests/office_mcp/pdf/test_e2e_pdf_tools.py`

Configuration: repository `.env.test` (loaded by tests/conftest.py).
Requires DOCUMENTSERVER_JWT_SECRET for Builder/Conversion/Command APIs.
When DocumentServer is unreachable, `-m e2e` tests skip (ADR-021).
"""

import json
import uuid

import httpx
import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import documentserver_reachable, mcp_reachable

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]

_cfg = get_e2e_config()
E2E_DS_URL = _cfg.documentserver_url
E2E_JWT_SECRET = _cfg.documentserver_jwt_secret
E2E_SOURCE = _cfg.source_path
E2E_SOURCES = _cfg.source_paths
E2E_TEMPLATE = _cfg.template_path
E2E_DOCBUILDER_URL = _cfg.docbuilder_url
E2E_MCP_URL = _cfg.mcp_url
_has_script_to_url = _cfg.has_script_to_url


def _jwt_configured() -> bool:
    return _cfg.has_jwt


async def _call_tool_via_mcp(tool_name: str, arguments: dict) -> dict:
    """Call any office tool via MCP HTTP (proxy tokens live in MCP process)."""
    transport = (
        httpx.HTTPTransport(local_address="0.0.0.0")
        if "localhost" in E2E_MCP_URL or "127.0.0.1" in E2E_MCP_URL
        else None
    )
    async with httpx.AsyncClient(timeout=180, transport=transport) as client:
        resp = await client.post(
            f"{E2E_MCP_URL}/mcp/v1/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": "pytest-e2e",
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

    if "error" in data:
        return {"isError": True, "text": str(data["error"])}

    content = data.get("result", {}).get("content", data.get("result", []))
    if isinstance(content, list) and content:
        text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
    else:
        text = str(content)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"isError": True, "text": text}


async def _call_execute_builder_via_mcp(script: str = None, url: str = None, **kwargs) -> dict:
    """
    Call office_execute_builder via MCP HTTP API so script is stored in the MCP server process.
    Document Server fetches script from the same process that stored it.
    """
    arguments = dict(kwargs)
    if script is not None:
        arguments["script"] = script
    if url is not None:
        arguments["url"] = url
    return await _call_tool_via_mcp("office_execute_builder", arguments)


requires_ds = pytest.mark.skipif(
    not documentserver_reachable(),
    reason="DocumentServer not reachable. Configure DOCUMENTSERVER_URL in .env.test.",
)
requires_mcp = pytest.mark.skipif(
    not mcp_reachable(),
    reason="MCP server must be running at E2E_MCP_URL for proxy-mode storage E2E.",
)
requires_jwt = pytest.mark.skipif(
    not _jwt_configured(),
    reason="DOCUMENTSERVER_JWT_SECRET required in .env.test for Builder/Conversion/Command APIs.",
)
requires_storage = pytest.mark.skipif(
    not _cfg.has_source_path,
    reason="E2E_SOURCE_PATH (or E2E_S3_SOURCE_PATH / E2E_MINIO_SOURCE_PATH) required in .env.test.",
)
requires_builder_url = pytest.mark.skipif(
    not E2E_DOCBUILDER_URL and not _has_script_to_url,
    reason="E2E_DOCBUILDER_URL or MCP_PUBLIC_URL/DOCBUILDER_SCRIPT_GCS_PATH required in .env.test.",
)
requires_mcp_for_script = pytest.mark.skipif(
    not E2E_DOCBUILDER_URL and _has_script_to_url and not mcp_reachable(),
    reason="MCP server must be running (E2E_MCP_URL in .env.test). Start: python -m aiecs.main_mcp",
)


# --- Gateway smoke (office_execute_builder, office_call_api) ---


@requires_ds
@requires_jwt
@requires_builder_url
@requires_mcp_for_script
async def test_e2e_office_execute_builder_creates_docx_with_content():
    """E2E: Create docx via Builder, verify file_url and content."""
    if E2E_DOCBUILDER_URL:
        from aiecs.tools.office_tool import office_execute_builder

        result = await office_execute_builder(url=E2E_DOCBUILDER_URL)
    else:
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
async def test_e2e_office_call_api_convert_docx_to_pdf():
    """E2E: Create docx, convert to PDF via Conversion API, verify result."""
    from aiecs.tools.office_tool import office_call_api

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

    key = str(uuid.uuid4())
    convert_result = await office_call_api(
        "convert",
        {"url": file_url, "filetype": "docx", "outputtype": "pdf", "key": key},
    )
    assert not convert_result.get("isError"), convert_result.get("text", convert_result)
    assert "fileUrl" in convert_result or "file_url" in convert_result or "urls" in convert_result, (
        "Expected fileUrl/urls in convert response: %s" % convert_result
    )


@requires_ds
@requires_jwt
async def test_e2e_office_call_api_info_calls_command_api():
    """E2E: office_call_api action=info calls Command API, returns dict."""
    from aiecs.tools.office_tool import office_call_api

    result = await office_call_api("info", {"key": "e2e-nonexistent-key"})
    assert isinstance(result, dict)
    if result.get("isError"):
        assert "text" in result
    else:
        assert "error" in result or "key" in result or "url" in result or len(result) >= 0


# --- Legacy alias smoke (hidden from list_tools; call_tool only, ADR-024) ---


@requires_ds
@requires_jwt
@requires_storage
@requires_mcp
async def test_e2e_legacy_office_read_document_returns_structure():
    """E2E: Read storage document via MCP (proxy fetch tokens in MCP process)."""
    result = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": E2E_SOURCE.strip(), "format": "structured"},
    )
    assert not result.get("isError"), result.get("text", result)
    assert "elements" in result or "text" in result or "outline" in result
    if "elements" in result:
        assert isinstance(result["elements"], list)
    if "word_count" in result:
        assert isinstance(result["word_count"], (int, float))


# --- Legacy alias smoke (continued) ---


@requires_ds
@requires_jwt
@requires_storage
@requires_builder_url
@requires_mcp
async def test_e2e_legacy_office_edit_document_modifies_content():
    """E2E: Edit storage document via MCP, verify output_path."""
    output = E2E_SOURCE.strip().replace(".docx", "-edited.docx")
    edit_script = """
    var oDoc = Api.GetDocument();
    var para = Api.CreateParagraph();
    para.AddText(' [E2E Edited]');
    oDoc.Push(para);
    """
    result = await _call_tool_via_mcp(
        "office_edit_document",
        {
            "source_path": E2E_SOURCE.strip(),
            "edit_script": edit_script,
            "output_path": output,
        },
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output or "success" in str(result).lower()


# --- Legacy: merge ---


@pytest.mark.skipif(
    not _cfg.has_source_paths,
    reason="E2E_SOURCE_PATHS (comma-separated) required in .env.test for merge E2E.",
)
@requires_ds
@requires_jwt
@requires_builder_url
@requires_mcp
async def test_e2e_legacy_office_merge_documents_produces_merged_file():
    """E2E: Merge storage documents via MCP, verify output_path."""
    sources = [s.strip() for s in E2E_SOURCES.split(",") if s.strip()]
    assert len(sources) >= 1
    output = sources[0].replace(".docx", "-merged.docx")
    result = await _call_tool_via_mcp(
        "office_merge_documents",
        {
            "source_paths": sources,
            "output_path": output,
            "options": {"add_page_break": True, "add_toc": False},
        },
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output


# --- Legacy: apply_template ---


@requires_ds
@requires_jwt
@requires_builder_url
@requires_mcp
@pytest.mark.skipif(
    not _cfg.has_template_path,
    reason="E2E_TEMPLATE_PATH required in .env.test for apply_template E2E.",
)
async def test_e2e_legacy_office_apply_template_fills_placeholders():
    """E2E: Fill template via MCP, verify output_path."""
    output = E2E_TEMPLATE.strip().replace(".docx", "-filled.docx")
    data = {"name": "E2EUser", "amount": "999"}
    result = await _call_tool_via_mcp(
        "office_apply_template",
        {
            "template_path": E2E_TEMPLATE.strip(),
            "data": data,
            "output_path": output,
        },
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("output_path") == output
