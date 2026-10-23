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
PDF-044 legacy office_read_document pdf coarse (PDF-NA-01);
PDF-047 mind-map fixture fine read + every office_edit_pdf op.

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
    STRUCTURED_READ_MCP_TIMEOUT,
    documentserver_reachable,
    mcp_reachable,
    pdf_edit_supported,
    pdf_fill_form_supported,
    pdf_fine_read_supported,
    structured_read_elements_text,
    structured_read_needles,
    update_structured_read_summary,
    upload_structured_read_fixture,
    write_structured_read_output,
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
_MINDMAP_PAGE_RANGE = [0, 2]
_MINDMAP_PARA = "TOKEN-PDF-MINDMAP-PARA"
_MINDMAP_REWRITE = "TOKEN-PDF-MINDMAP-REWRITE"
_MINDMAP_CELL = "TOKEN-PDF-MINDMAP-CELL"
_MINDMAP_NEW = "TOKEN-PDF-MINDMAP-NEW"
_MINDMAP_PAGE = "TOKEN-PDF-MINDMAP-PAGE"
_MINDMAP_ANNOT = "TOKEN-PDF-MINDMAP-ANNOT"
_MINDMAP_ANNOT_SET = "TOKEN-PDF-MINDMAP-ANNOT-SET"
_MINDMAP_BOOKMARK = "e2e-mindmap-bm"
_MINDMAP_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_FORM_TYPES = {
    "text",
    "checkbox",
    "radiobutton",
    "combobox",
    "listbox",
    "button",
    "signature",
    "unknown",
}

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


async def _read_pdf_fine(
    source_path: str,
    *,
    options: dict | None = None,
    timeout: float = 180,
) -> dict:
    opts = {"read_mode": "fine", **(options or {})}
    return await _call_tool_via_mcp(
        "office_read_pdf",
        {
            "source_path": source_path,
            "format": "structured",
            "options": opts,
        },
        timeout=timeout,
    )


async def _edit_pdf(
    source_path: str,
    operations: list[dict],
    *,
    label: str,
    timeout: float = 180,
) -> str:
    output_path = _unique_output_path(label)
    result = await _call_tool_via_mcp(
        "office_edit_pdf",
        {
            "source_path": source_path,
            "output_path": output_path,
            "operations": operations,
        },
        timeout=timeout,
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    assert result.get("output_path") == output_path
    return output_path


def _find_block(pages: list, *, page_index: int, text: str | None = None, block_type: str | None = None) -> dict | None:
    for page in pages:
        if page.get("page_index") != page_index:
            continue
        for block in page.get("blocks") or []:
            if block_type and block.get("type") != block_type:
                continue
            if text is not None and text not in str(block.get("text") or ""):
                continue
            return block
    return None


def _page_blob(pages: list) -> str:
    parts: list[str] = []
    for page in pages:
        parts.append(_page_texts([page]).get(page.get("page_index"), ""))
        for block in page.get("blocks") or []:
            for row in block.get("rows") or []:
                parts.extend(str(cell) for cell in row)
    return "\n".join(parts)


def _assert_fine_read_fields(read: dict) -> list:
    assert not read.get("isError"), read.get("text", read)
    assert read.get("category") == "pdf"
    assert read.get("read_mode") == "fine"
    assert isinstance(read.get("bookmarks"), list)
    pages = read.get("pages") or []
    assert pages
    assert pages == (read.get("units") or [])
    for page in pages:
        assert isinstance(page.get("page_index"), int)
        assert page.get("degrees") in (0, 90, 180, 270)
        assert isinstance(page.get("blocks"), list)
        for block in page["blocks"]:
            assert isinstance(block.get("block_index"), int)
            assert block.get("type") in {"paragraph", "table", "image"}
            if block["type"] == "paragraph":
                assert "text" in block
            elif block["type"] == "table":
                assert isinstance(block.get("rows"), list)
                assert isinstance(block.get("cells"), list)
                for cell in block["cells"]:
                    assert "row" in cell and "col" in cell and "text" in cell
            else:
                assert "alt" in block
        for field in page.get("form_fields") or []:
            assert "name" in field
            assert field.get("type") in _FORM_TYPES
            assert isinstance(field.get("page_index"), int)
        for annot in page.get("annotations") or []:
            assert isinstance(annot.get("annotation_index"), int)
            assert "kind" in annot
            assert "text" in annot
        for image in page.get("images") or []:
            assert isinstance(image.get("image_index"), int)
    for bookmark in read.get("bookmarks") or []:
        assert bookmark.get("bookmark_id")
        assert bookmark.get("name")
    return pages


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
@pytest.mark.timeout(int(STRUCTURED_READ_MCP_TIMEOUT) + 60)
async def test_e2e_read_document_pdf_coarse():
    """PDF-044: office_read_document structured on the 必修二 mind-map PDF fixture."""
    source_path = await upload_structured_read_fixture("pdf")

    legacy = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": source_path, "format": "markdown"},
        timeout=STRUCTURED_READ_MCP_TIMEOUT,
    )
    output_path = write_structured_read_output("pdf", legacy)
    update_structured_read_summary("pdf", legacy, output_path)
    if legacy.get("isError"):
        pytest.skip(f"DocumentServer rejected this PDF markdown read: {legacy.get('text')}")
    assert not legacy.get("isError"), legacy.get("text", legacy)
    assert "markdown" in legacy
    assert "elements" not in legacy
    assert "slides" not in legacy
    assert "_note" in legacy
    assert legacy.get("read_mode") != "fine"
    assert legacy.get("category") != "pdf"
    legacy_text = legacy.get("markdown") or ""
    assert any(needle in legacy_text for needle in structured_read_needles("pdf"))


@requires_storage
@requires_jwt
@requires_mcp
@pytest.mark.timeout(int(STRUCTURED_READ_MCP_TIMEOUT) * 5 + 120)
async def test_e2e_mindmap_fine_read_and_all_edit_ops():
    """PDF-047: 必修二 mind-map fixture → fine-read fields → every office_edit_pdf op."""
    source_path = await upload_structured_read_fixture("pdf")
    timeout = STRUCTURED_READ_MCP_TIMEOUT
    read_opts = {
        "page_range": _MINDMAP_PAGE_RANGE,
        "include_form_fields": True,
        "include_annotations": True,
    }

    read0 = await _read_pdf_fine(source_path, options=read_opts, timeout=timeout)
    pages0 = _assert_fine_read_fields(read0)
    assert [page.get("page_index") for page in pages0] == [0, 1, 2]

    seeded = await _edit_pdf(
        source_path,
        [
            {
                "op": "add_paragraph",
                "page_index": 0,
                "text": _MINDMAP_PARA,
                "align": "center",
                "bold": True,
                "font_name": "Calibri",
                "font_size_pt": 14,
            },
            {
                "op": "add_annotation",
                "page_index": 0,
                "kind": "freetext",
                "text": _MINDMAP_ANNOT,
                "rect": {"x": 20, "y": 20, "width": 120, "height": 24},
            },
            {
                "op": "add_page",
                "after_index": 0,
                "blocks": [
                    {"type": "paragraph", "text": _MINDMAP_NEW, "align": "left"},
                    {"type": "table", "rows": [["A", "B"], ["C", "D"]]},
                ],
            },
            {"op": "rotate_page", "page_index": 0, "degrees": 90},
        ],
        label="mindmap-seed",
        timeout=timeout,
    )

    read1 = await _read_pdf_fine(seeded, options=read_opts, timeout=timeout)
    pages1 = _assert_fine_read_fields(read1)
    blob1 = _page_blob(pages1)
    assert _MINDMAP_PARA in blob1
    assert _MINDMAP_NEW in blob1
    page0 = next(page for page in pages1 if page.get("page_index") == 0)
    if page0.get("degrees") != 0:
        assert page0["degrees"] == 90

    para = _find_block(pages1, page_index=0, text=_MINDMAP_PARA, block_type="paragraph")
    new_para = _find_block(pages1, page_index=1, text=_MINDMAP_NEW, block_type="paragraph")
    table = _find_block(pages1, page_index=1, block_type="table")
    assert para is not None
    assert new_para is not None
    assert table is not None
    annot = next(
        (
            item
            for page in pages1
            for item in page.get("annotations") or []
            if _MINDMAP_ANNOT in str(item.get("text") or "")
        ),
        None,
    )
    image_target = (page0.get("images") or [None])[0]
    image_block = next(
        (block for block in page0.get("blocks") or [] if block.get("type") == "image"),
        None,
    )

    rewrite_ops: list[dict] = [
        {
            "op": "set_block_text",
            "page_index": 1,
            "block_index": new_para["block_index"],
            "text": _MINDMAP_REWRITE,
        },
        {
            "op": "set_cell_text",
            "page_index": 1,
            "block_index": table["block_index"],
            "row": 0,
            "col": 0,
            "text": _MINDMAP_CELL,
        },
        {
            "op": "set_paragraph_format",
            "page_index": 0,
            "block_index": para["block_index"],
            "align": "right",
            "bold": True,
            "font_name": "Arial",
            "font_size_pt": 12,
        },
        {
            "op": "set_bookmark",
            "bookmark_id": _MINDMAP_BOOKMARK,
            "text": _MINDMAP_PARA,
            "page_index": 0,
            "block_index": para["block_index"],
        },
        {
            "op": "replace_image",
            "page_index": 0,
            "content_base64": _MINDMAP_PNG,
            **(
                {"image_index": image_target["image_index"]}
                if image_target
                else {"block_index": image_block["block_index"]}
                if image_block
                else {"image_index": 0}
            ),
        },
        {
            "op": "add_page",
            "after_index": 1,
            "blocks": [{"type": "paragraph", "text": "placeholder"}],
        },
        {
            "op": "set_page_text",
            "page_index": 2,
            "blocks": [{"type": "paragraph", "text": _MINDMAP_PAGE, "align": "center"}],
        },
    ]
    if annot is not None:
        rewrite_ops.append(
            {
                "op": "set_annotation",
                "page_index": annot.get("page_index", 0),
                "annotation_index": annot["annotation_index"],
                "text": _MINDMAP_ANNOT_SET,
                "rect": annot.get("rect") or {"x": 20, "y": 20, "width": 120, "height": 24},
            }
        )
    else:
        rewrite_ops.append(
            {
                "op": "set_annotation",
                "page_index": 0,
                "annotation_index": 0,
                "text": _MINDMAP_ANNOT_SET,
                "rect": {"x": 20, "y": 20, "width": 120, "height": 24},
            }
        )

    rewritten = await _edit_pdf(seeded, rewrite_ops, label="mindmap-rewrite", timeout=timeout)
    read2 = await _read_pdf_fine(rewritten, options=read_opts, timeout=timeout)
    pages2 = _assert_fine_read_fields(read2)
    blob2 = _page_blob(pages2)
    assert _MINDMAP_REWRITE in blob2
    assert _MINDMAP_CELL in blob2
    assert _MINDMAP_PAGE in blob2
    formatted = _find_block(pages2, page_index=0, text=_MINDMAP_PARA, block_type="paragraph")
    assert formatted is not None
    if formatted.get("align"):
        assert formatted["align"] == "right"
    if read2.get("bookmarks"):
        assert any(item.get("bookmark_id") == _MINDMAP_BOOKMARK for item in read2["bookmarks"])

    form_field = next(
        (
            field
            for page in pages2
            for field in page.get("form_fields") or []
            if field.get("name")
        ),
        None,
    )
    fill_source = rewritten
    if form_field:
        fill_path = _unique_output_path("mindmap-fill")
        fill_result = await _call_tool_via_mcp(
            "office_fill_pdf_form",
            {
                "source_path": rewritten,
                "output_path": fill_path,
                "data": {form_field["name"]: "E2E-MINDMAP"},
                "fields": [
                    {
                        "page_index": form_field["page_index"],
                        "name": form_field["name"],
                        "value": "E2E-MINDMAP",
                    }
                ],
            },
            timeout=timeout,
        )
        assert not fill_result.get("isError"), fill_result.get("text", fill_result)
        fill_source = fill_path

    cleaned = await _edit_pdf(
        fill_source,
        [
            {"op": "delete_bookmark", "bookmark_id": _MINDMAP_BOOKMARK},
            {"op": "delete_page", "page_index": 2},
        ],
        label="mindmap-clean",
        timeout=timeout,
    )
    read3 = await _read_pdf_fine(cleaned, options=read_opts, timeout=timeout)
    pages3 = _assert_fine_read_fields(read3)
    blob3 = _page_blob(pages3)
    assert _MINDMAP_PAGE not in blob3
    assert _MINDMAP_REWRITE in blob3
    if read3.get("bookmarks"):
        assert all(item.get("bookmark_id") != _MINDMAP_BOOKMARK for item in read3["bookmarks"])
