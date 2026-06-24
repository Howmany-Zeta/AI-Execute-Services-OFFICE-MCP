"""
E2E tests for PDF vertical tools (PDF-037–044 / Gate P-E2E).

Requires `.env.test` (loaded by tests/conftest.py):
- DOCUMENTSERVER_URL — DocumentServer healthcheck target
- DOCUMENTSERVER_JWT_SECRET — Builder / Conversion / Command APIs
- E2E_MCP_URL — MCP HTTP base (tools/call via _call_tool_via_mcp)
- E2E_MCP_PUBLIC_URL or MCP_PUBLIC_URL — DS-reachable URL for docbuilder scripts
- E2E_SOURCE_PATH — object-storage prefix (s3:// or gs://) for create/edit outputs
- E2E_PDF_ACROFORM_SOURCE_PATH — optional pre-uploaded acroform pdf (else fixture uploaded in-test)

PDF E2E creates *.pdf under the E2E_SOURCE_PATH parent directory (uuid paths).
create_mode: default native when probe_ds_capabilities().pdf_native_create; else via_docx (ADR-021).

Module-level skipif when DocumentServer unreachable (ADR-021).
Per-test lazy skipif when PDF Builder fine read or edit-on-source unsupported (ADR-021).

Cases: PDF-037 create/read; PDF-038 edit; PDF-039 merge builder; PDF-040 merge conversion (ADR-018);
PDF-041 fill_pdf_form acroform (company_name); PDF-042 create_mode=native; PDF-043 create_mode=via_docx;
PDF-044 legacy office_read_document pdf coarse (PDF-NA-01).

No unconditional placeholder or manual skip calls in test bodies; module may skip when
DocumentServer unreachable or ADR-021 capability probes fail.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import (
    documentserver_reachable,
    mcp_reachable,
    pdf_edit_supported,
    pdf_fill_form_supported,
    pdf_fine_read_supported,
)
from tests.office_mcp.probe_ds_capabilities import clear_probe_cache, probe_ds_capabilities
from tests.office_mcp.test_e2e_office_tools import _call_tool_via_mcp

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.pdf,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]

_cfg = get_e2e_config()
FIXTURES = Path(__file__).parent / "fixtures"
ACROFORM_FIXTURE = FIXTURES / "acroform_template.pdf"

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
requires_pdf_fine_read = pytest.mark.skipif(
    lambda: not pdf_fine_read_supported(),
    reason="PDF Builder fine read (OpenFile sidecar) not supported on this DocumentServer (ADR-021).",
)
requires_pdf_edit = pytest.mark.skipif(
    lambda: not pdf_edit_supported(),
    reason="PDF Builder edit-on-source not supported on this DocumentServer.",
)
requires_pdf_fill = pytest.mark.skipif(
    lambda: not pdf_fill_form_supported(),
    reason="PDF AcroForm fill (office_fill_pdf_form) not supported on this DocumentServer.",
)

_PAGE_ONE_MARKER = "TOKEN-PDF-E2E-P1"
_PAGE_TWO_MARKER = "TOKEN-PDF-E2E-P2"
_EDIT_MARKER = "TOKEN-PDF-E2E-EDIT"
_MERGE_MARKER_A = "TOKEN-PDF-MERGE-A"
_MERGE_MARKER_B = "TOKEN-PDF-MERGE-B"
_FILL_COMPANY = "Acme E2E PDF"
_NATIVE_MARKER = "TOKEN-PDF-NATIVE"
_VIA_DOCX_MARKER = "TOKEN-PDF-VIA-DOCX"
_COARSE_MARKER = "TOKEN-PDF-COARSE-044"

_CREATE_PAGES = [
    {"blocks": [{"type": "paragraph", "text": f"Page one {_PAGE_ONE_MARKER}"}]},
    {"blocks": [{"type": "paragraph", "text": f"Page two {_PAGE_TWO_MARKER}"}]},
]
_NATIVE_ONE_PAGE = [{"blocks": [{"type": "paragraph", "text": f"Native create {_NATIVE_MARKER}"}]}]
_VIA_DOCX_PAGES = [
    {"blocks": [{"type": "paragraph", "text": f"Via docx page one {_VIA_DOCX_MARKER}"}]},
    {"blocks": [{"type": "paragraph", "text": "Via docx page two"}]},
]


async def _pdf_native_available() -> bool:
    url = os.environ.get("DOCUMENTSERVER_URL", "").strip()
    if not url:
        return False
    clear_probe_cache()
    caps = await probe_ds_capabilities(url)
    return caps.pdf_native_create


async def _create_mode_options() -> dict:
    if await _pdf_native_available():
        return {}
    return {"create_mode": "via_docx"}


def _unique_output_path(label: str) -> str:
    base_dir = _cfg.source_path.rsplit("/", 1)[0]
    return f"{base_dir}/e2e-pdf-{label}-{uuid.uuid4().hex[:12]}.pdf"


def _page_texts(pages: list) -> dict[int, str]:
    out: dict[int, str] = {}
    for page in pages:
        idx = page.get("page_index")
        blocks = page.get("blocks") or []
        out[idx] = "\n".join(str(b.get("text", "")) for b in blocks)
    return out


def _assert_two_page_fine_read(read: dict) -> dict[int, str]:
    assert not read.get("isError"), read.get("text", read)
    assert read.get("category") == "pdf"
    assert read.get("read_mode") == "fine"
    assert read.get("page_count") == 2
    assert read.get("unit_count") == 2
    pages = read.get("pages") or []
    units = read.get("units") or []
    assert pages == units
    indices = sorted(p.get("page_index") for p in pages)
    assert indices == [0, 1]
    return _page_texts(pages)


async def _read_pdf_fine(source_path: str) -> dict:
    return await _call_tool_via_mcp(
        "office_read_pdf",
        {
            "source_path": source_path,
            "format": "structured",
            "options": {"read_mode": "fine"},
        },
    )


async def _create_pdf(label: str, pages: list[dict]) -> str:
    path = _unique_output_path(label)
    create_args: dict = {"pages": pages, "output_path": path}
    options = await _create_mode_options()
    if options:
        create_args["options"] = options
    result = await _call_tool_via_mcp("office_create_pdf", create_args)
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    assert result.get("output_path") == path
    return path


async def _create_pdf_explicit(label: str, pages: list[dict], *, create_mode: str) -> str:
    path = _unique_output_path(label)
    result = await _call_tool_via_mcp(
        "office_create_pdf",
        {
            "pages": pages,
            "output_path": path,
            "options": {"create_mode": create_mode},
        },
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    assert result.get("output_path") == path
    return path


async def _create_two_page_pdf(label: str) -> str:
    return await _create_pdf(label, _CREATE_PAGES)


async def _create_one_page_pdf(label: str, marker: str) -> str:
    pages = [{"blocks": [{"type": "paragraph", "text": f"Merge page {marker}"}]}]
    return await _create_pdf(label, pages)


async def _two_merge_pdf_sources() -> list[str]:
    return [
        await _create_one_page_pdf("merge-a", _MERGE_MARKER_A),
        await _create_one_page_pdf("merge-b", _MERGE_MARKER_B),
    ]


async def _upload_bytes_to_s3(storage_path: str, content: bytes, *, content_type: str) -> None:
    """Upload fixture bytes to s3:// via project venv (pytest may lack boto3)."""
    import asyncio

    repo_root = Path(__file__).resolve().parents[3]
    venv_python = repo_root / ".venv" / "bin" / "python"
    if not venv_python.is_file():
        pytest.skip("Project .venv/python required to upload acroform fixture to s3://")

    tmp_path = repo_root / ".tmp-acroform-upload.bin"
    tmp_path.write_bytes(content)
    script = f"""
import asyncio
from pathlib import Path
from tests.env_test import load_env_test
from aiecs.tools.office_tool.core.storage import upload_to_storage

load_env_test()

async def main() -> None:
    data = Path({str(tmp_path)!r}).read_bytes()
    await upload_to_storage(data, {storage_path!r})

asyncio.run(main())
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            str(venv_python),
            "-c",
            script,
            cwd=str(repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() or "acroform fixture upload failed")
    finally:
        tmp_path.unlink(missing_ok=True)


async def _acroform_source_path() -> str:
    configured = os.environ.get("E2E_PDF_ACROFORM_SOURCE_PATH", "").strip()
    if configured:
        return configured
    storage_path = _unique_output_path("acroform-src")
    await _upload_bytes_to_s3(
        storage_path,
        ACROFORM_FIXTURE.read_bytes(),
        content_type="application/pdf",
    )
    return storage_path


def _form_field_value(read: dict, field_name: str) -> str | None:
    for page in read.get("pages") or read.get("units") or []:
        for field in page.get("form_fields") or []:
            if field.get("name") == field_name:
                return field.get("value")
    return None


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_fine_read
async def test_e2e_create_read_pdf_two_pages():
    """PDF-037: office_create_pdf 2 pages → office_read_pdf fine."""
    path = await _create_two_page_pdf("read-two")
    read = await _read_pdf_fine(path)
    texts = _assert_two_page_fine_read(read)
    assert _PAGE_ONE_MARKER in texts[0]
    assert _PAGE_TWO_MARKER in texts[1]


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_edit
async def test_e2e_edit_pdf_add_paragraph():
    """PDF-038: office_edit_pdf add_paragraph → re-read fine."""
    source_path = await _create_two_page_pdf("edit-src")
    read1 = await _read_pdf_fine(source_path)
    texts1 = _assert_two_page_fine_read(read1)
    assert _PAGE_ONE_MARKER in texts1[0]

    target_page = 0
    edit_path = _unique_output_path("edit-out")
    edit_result = await _call_tool_via_mcp(
        "office_edit_pdf",
        {
            "source_path": source_path,
            "output_path": edit_path,
            "operations": [
                {
                    "op": "add_paragraph",
                    "page_index": target_page,
                    "text": f"Added paragraph {_EDIT_MARKER}",
                }
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path

    read2 = await _read_pdf_fine(edit_path)
    texts2 = _assert_two_page_fine_read(read2)
    assert _EDIT_MARKER in texts2[target_page]
    assert _PAGE_ONE_MARKER in texts2[0]
    assert _PAGE_TWO_MARKER in texts2[1]


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_fine_read
async def test_e2e_merge_pdfs_builder():
    """PDF-039: merge two 1-page PDFs (builder default) → fine read page_count==2."""
    sources = await _two_merge_pdf_sources()
    merge_output = _unique_output_path("merge-builder")

    merge_result = await _call_tool_via_mcp(
        "office_merge_pdfs",
        {"source_paths": sources, "output_path": merge_output},
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("success") is True
    assert merge_result.get("output_path") == merge_output

    read = await _read_pdf_fine(merge_output)
    texts = _assert_two_page_fine_read(read)
    assert _MERGE_MARKER_A in texts[0]
    assert _MERGE_MARKER_B in texts[1]


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_merge_pdfs_conversion():
    """
    PDF-040: explicit options.engine=conversion (ADR-018).

    Conversion merge may succeed or return {isError} on some DocumentServer installs
    (Conversion API url2 merge limitation). No silent builder fallback — engine
    stays conversion only.
    """
    sources = await _two_merge_pdf_sources()
    merge_output = _unique_output_path("merge-conversion")

    merge_result = await _call_tool_via_mcp(
        "office_merge_pdfs",
        {
            "source_paths": sources,
            "output_path": merge_output,
            "options": {"engine": "conversion"},
        },
    )

    if merge_result.get("isError") or not merge_result.get("success"):
        assert merge_result.get("isError") or merge_result.get("text")
        return

    assert merge_result.get("output_path") == merge_output
    if pdf_fine_read_supported():
        read = await _read_pdf_fine(merge_output)
        assert read.get("page_count") == 2
        assert read.get("unit_count") == 2


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_fill
async def test_e2e_fill_pdf_form_acroform():
    """PDF-041: fill acroform company_name → re-read fine form_fields when supported."""
    source_path = await _acroform_source_path()
    output_path = _unique_output_path("fill-out")

    fill_result = await _call_tool_via_mcp(
        "office_fill_pdf_form",
        {
            "source_path": source_path,
            "data": {"company_name": _FILL_COMPANY},
            "output_path": output_path,
        },
    )
    assert not fill_result.get("isError"), fill_result.get("text", fill_result)
    assert fill_result.get("success") is True
    assert fill_result.get("output_path") == output_path

    if pdf_fine_read_supported():
        read = await _read_pdf_fine(output_path)
        assert not read.get("isError"), read.get("text", read)
        assert read.get("read_mode") == "fine"
        assert _form_field_value(read, "company_name") == _FILL_COMPANY


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_fine_read
async def test_e2e_create_pdf_native():
    """PDF-042: create_mode=native when probe allows → fine read (ADR-021)."""
    if not await _pdf_native_available():
        pytest.skip("PDF native API not available (ADR-021)")

    path = await _create_pdf_explicit("native", _NATIVE_ONE_PAGE, create_mode="native")
    read = await _read_pdf_fine(path)
    assert not read.get("isError"), read.get("text", read)
    assert read.get("read_mode") == "fine"
    assert read.get("page_count", 0) >= 1
    assert read.get("unit_count", 0) >= 1
    texts = _page_texts(read.get("pages") or [])
    assert _NATIVE_MARKER in texts.get(0, "")


@requires_storage
@requires_jwt
@requires_mcp
@requires_pdf_fine_read
async def test_e2e_create_pdf_via_docx():
    """PDF-043: explicit create_mode=via_docx → fine read (ADR-017; no auto fallback)."""
    path = await _create_pdf_explicit("via-docx", _VIA_DOCX_PAGES, create_mode="via_docx")
    read = await _read_pdf_fine(path)
    texts = _assert_two_page_fine_read(read)
    assert _VIA_DOCX_MARKER in texts[0]


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_read_document_pdf_coarse():
    """PDF-044: legacy office_read_document pdf→txt — not read_pdf fine (PDF-NA-01)."""
    source_path = await _create_one_page_pdf("read-doc-coarse", _COARSE_MARKER)

    legacy = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": source_path, "format": "structured"},
    )
    assert not legacy.get("isError"), legacy.get("text", legacy)
    assert "elements" in legacy
    assert isinstance(legacy["elements"], list)
    assert legacy.get("conversion_output_type") == "txt"
    assert "pages" not in legacy
    assert legacy.get("read_mode") != "fine"
    assert legacy.get("category") != "pdf"
    legacy_text = " ".join(
        str(el.get("text", "")) for el in legacy["elements"] if isinstance(el, dict)
    )
    assert _COARSE_MARKER in legacy_text

    if pdf_fine_read_supported():
        fine = await _read_pdf_fine(source_path)
        assert not fine.get("isError"), fine.get("text", fine)
        assert fine.get("read_mode") == "fine"
        assert fine.get("category") == "pdf"
        assert "pages" in fine or isinstance(fine.get("units"), list)
        assert fine.get("conversion_output_type") == "builder_json"
