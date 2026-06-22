"""
E2E tests for Word vertical tools.

Requires `.env.test` (loaded by tests/conftest.py):
- DOCUMENTSERVER_URL — DocumentServer healthcheck target
- DOCUMENTSERVER_JWT_SECRET — Builder / Conversion / Command APIs
- E2E_MCP_URL — MCP HTTP base (tools/call via _call_tool_via_mcp)
- E2E_MCP_PUBLIC_URL or MCP_PUBLIC_URL — DS-reachable URL for docbuilder scripts
- E2E_SOURCE_PATH — object-storage prefix (s3:// or gs://) for create/edit outputs
- E2E_TEMPLATE_PATH — optional; required for apply_template legacy E2E

Module-level skipif when DocumentServer unreachable (ADR-021).
Per-test skipif when odt CreateFile or multi-doc merge unsupported on this DS install.
"""

from __future__ import annotations

import uuid

import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import (
    documentserver_reachable,
    mcp_reachable,
    word_merge_builder_supported,
    word_odt_builder_supported,
)
from tests.office_mcp.test_e2e_office_tools import _call_tool_via_mcp

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.word,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]

_cfg = get_e2e_config()

requires_jwt = pytest.mark.skipif(
    not _cfg.has_jwt,
    reason="DOCUMENTSERVER_JWT_SECRET required in .env.test for Builder/Conversion/Command APIs.",
)
requires_mcp = pytest.mark.skipif(
    not mcp_reachable(),
    reason="MCP server must be running at E2E_MCP_URL for proxy-mode storage E2E.",
)
requires_storage = pytest.mark.skipif(
    not _cfg.has_source_path,
    reason="E2E_SOURCE_PATH (object storage) required in .env.test.",
)
requires_odt = pytest.mark.skipif(
    not word_odt_builder_supported(),
    reason="DocumentServer Builder odt CreateFile not supported on this installation.",
)
requires_merge = pytest.mark.skipif(
    not word_merge_builder_supported(),
    reason="DocumentServer Builder multi-document merge not supported on this installation.",
)
requires_template = pytest.mark.skipif(
    not _cfg.has_template_path,
    reason="E2E_TEMPLATE_PATH required in .env.test for apply_template E2E.",
)

_CREATE_SECTIONS = [
    {"type": "heading1", "text": "E2E Test Report"},
    {"type": "paragraph", "text": "Initial paragraph for e2e testing."},
    {"type": "heading2", "text": "Details"},
    {"type": "paragraph", "text": "Second paragraph with marker TOKEN-E2E-001."},
]

_SEARCH_MARKER = "TOKEN-E2E-001"
_REPLACE_MARKER = "TOKEN-E2E-REPLACED"


def _unique_output_path(ext: str, label: str) -> str:
    base_dir = _cfg.source_path.rsplit("/", 1)[0]
    return f"{base_dir}/e2e-{label}-{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"


def _blocks_text(result: dict) -> str:
    blocks = result.get("blocks") or result.get("units") or []
    return "\n".join(str(b.get("text", "")) for b in blocks)


async def _read_word_fine(source_path: str) -> dict:
    return await _call_tool_via_mcp(
        "office_read_word",
        {
            "source_path": source_path,
            "format": "structured",
            "options": {"read_mode": "fine"},
        },
    )


async def _create_small_docx(label: str, text: str) -> str:
    path = _unique_output_path("docx", label)
    result = await _call_tool_via_mcp(
        "office_create_word",
        {"sections": [{"type": "paragraph", "text": text}], "output_path": path},
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    return path


async def _two_merge_sources() -> list[str]:
    """Two distinct docx sources — always create fresh docs to avoid duplicate-path merge failures."""
    return [
        await _create_small_docx("merge-a", "Merge source A TOKEN-MERGE-A"),
        await _create_small_docx("merge-b", "Merge source B TOKEN-MERGE-B"),
    ]


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_create_read_edit_word_docx():
    """E2E: create docx → fine read → search_replace edit → re-read (WT-037)."""
    create_path = _unique_output_path("docx", "create")
    edit_path = _unique_output_path("docx", "edit")

    create_result = await _call_tool_via_mcp(
        "office_create_word",
        {"sections": _CREATE_SECTIONS, "output_path": create_path},
    )
    assert not create_result.get("isError"), create_result.get("text", create_result)
    assert create_result.get("success") is True
    assert create_result.get("output_path") == create_path

    read1 = await _read_word_fine(create_path)
    assert not read1.get("isError"), read1.get("text", read1)
    assert read1.get("category") == "word"
    assert read1.get("read_mode") == "fine"
    assert read1.get("unit_count", 0) >= 1
    assert isinstance(read1.get("blocks"), list)
    assert _SEARCH_MARKER in _blocks_text(read1)

    edit_result = await _call_tool_via_mcp(
        "office_edit_word",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {
                    "op": "search_replace",
                    "search_string": _SEARCH_MARKER,
                    "replace_string": _REPLACE_MARKER,
                }
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path

    read2 = await _read_word_fine(edit_path)
    assert not read2.get("isError"), read2.get("text", read2)
    assert read2.get("unit_count", 0) >= 1
    text2 = _blocks_text(read2)
    assert _REPLACE_MARKER in text2
    assert _SEARCH_MARKER not in text2


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
@requires_odt
async def test_e2e_merge_word_odt():
    """E2E: merge two docx sources → output .odt (WT-039)."""
    sources = await _two_merge_sources()
    output_path = _unique_output_path("odt", "merge")
    assert output_path.endswith(".odt")

    merge_result = await _call_tool_via_mcp(
        "office_merge_word",
        {
            "source_paths": sources,
            "output_path": output_path,
            "options": {"add_page_break": True, "add_toc": False},
        },
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("success") is True
    assert merge_result.get("output_path") == output_path

    read_result = await _call_tool_via_mcp(
        "office_read_word",
        {
            "source_path": output_path,
            "format": "text",
            "options": {"read_mode": "coarse"},
        },
    )
    assert not read_result.get("isError"), read_result.get("text", read_result)
    assert read_result.get("read_mode") == "coarse"
    assert "TOKEN-MERGE" in (read_result.get("text") or "")


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
async def test_e2e_legacy_merge_documents_docx():
    """E2E: legacy office_merge_documents via MCP (WT-040)."""
    sources = await _two_merge_sources()
    merge_output = _unique_output_path("docx", "legacy-merge")
    merge_result = await _call_tool_via_mcp(
        "office_merge_documents",
        {
            "source_paths": sources,
            "output_path": merge_output,
            "options": {"add_page_break": True, "add_toc": False},
        },
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("output_path") == merge_output


@requires_storage
@requires_jwt
@requires_mcp
@requires_template
async def test_e2e_legacy_apply_template():
    """E2E: legacy office_apply_template via MCP (WT-040)."""
    template_output = _unique_output_path("docx", "legacy-template")
    apply_result = await _call_tool_via_mcp(
        "office_apply_template",
        {
            "template_path": _cfg.template_path.strip(),
            "data": {"name": "E2EUser", "amount": "999"},
            "output_path": template_output,
        },
    )
    assert not apply_result.get("isError"), apply_result.get("text", apply_result)
    assert apply_result.get("output_path") == template_output


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_legacy_edit_document_search():
    """E2E: legacy office_edit_document with Search() targeting (WT-040)."""
    edit_source = await _create_small_docx("legacy-edit-src", "Find TOKEN-LEGACY-EDIT here.")
    edit_output = _unique_output_path("docx", "legacy-edit")
    edit_script = """
var oDoc = Api.GetDocument();
var search = oDoc.Search("TOKEN-LEGACY-EDIT");
if (search && search.length > 0) {
  search[0].AddText(" [LEGACY-EDITED]");
}
"""
    edit_result = await _call_tool_via_mcp(
        "office_edit_document",
        {
            "source_path": edit_source,
            "edit_script": edit_script,
            "output_path": edit_output,
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("output_path") == edit_output

    read_back = await _call_tool_via_mcp(
        "office_read_word",
        {"source_path": edit_output, "format": "text", "options": {"read_mode": "coarse"}},
    )
    assert not read_back.get("isError"), read_back.get("text", read_back)
    assert "LEGACY-EDITED" in (read_back.get("text") or "")


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_read_document_docx_coarse():
    """E2E: office_read_document coarse/html on docx — not read_word fine (WT-041)."""
    source_path = await _create_small_docx("read-doc-coarse", "Coarse read sample TOKEN-COARSE-041.")
    legacy = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": source_path, "format": "structured"},
    )
    assert not legacy.get("isError"), legacy.get("text", legacy)
    assert "elements" in legacy
    assert isinstance(legacy["elements"], list)
    assert legacy.get("conversion_output_type") == "html"
    assert "blocks" not in legacy
    assert legacy.get("category") != "word"
    assert legacy.get("read_mode") != "fine"

    fine = await _read_word_fine(source_path)
    assert not fine.get("isError"), fine.get("text", fine)
    assert fine.get("read_mode") == "fine"
    assert "blocks" in fine
    assert fine.get("conversion_output_type") == "builder_json"


@requires_storage
@requires_jwt
@requires_mcp
@requires_odt
async def test_e2e_odt_create_edit_roundtrip():
    """E2E: create odt → edit → output remains .odt (WT-038)."""
    create_path = _unique_output_path("odt", "odt-create")
    edit_path = _unique_output_path("odt", "odt-edit")
    assert create_path.endswith(".odt")
    assert edit_path.endswith(".odt")

    create_result = await _call_tool_via_mcp(
        "office_create_word",
        {"sections": _CREATE_SECTIONS, "output_path": create_path},
    )
    assert not create_result.get("isError"), create_result.get("text", create_result)
    assert create_result.get("success") is True
    assert create_result.get("output_path") == create_path

    read1 = await _read_word_fine(create_path)
    assert not read1.get("isError"), read1.get("text", read1)
    assert read1.get("unit_count", 0) >= 1
    assert _SEARCH_MARKER in _blocks_text(read1)

    edit_result = await _call_tool_via_mcp(
        "office_edit_word",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {
                    "op": "search_replace",
                    "search_string": _SEARCH_MARKER,
                    "replace_string": _REPLACE_MARKER,
                }
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path
    assert edit_result.get("output_path", "").endswith(".odt")

    read2 = await _read_word_fine(edit_path)
    assert not read2.get("isError"), read2.get("text", read2)
    assert read2.get("source_path", edit_path).endswith(".odt")
    assert _REPLACE_MARKER in _blocks_text(read2)
