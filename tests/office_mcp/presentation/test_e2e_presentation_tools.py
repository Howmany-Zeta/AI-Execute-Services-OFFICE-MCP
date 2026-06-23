"""
E2E tests for Presentation vertical tools (PT-037–044 / Gate P-E2E).

Requires `.env.test` (loaded by tests/conftest.py):
- DOCUMENTSERVER_URL — DocumentServer healthcheck target
- DOCUMENTSERVER_JWT_SECRET — Builder / Conversion / Command APIs
- E2E_MCP_URL — MCP HTTP base (tools/call via _call_tool_via_mcp)
- E2E_MCP_PUBLIC_URL or MCP_PUBLIC_URL — DS-reachable URL for docbuilder scripts
- E2E_SOURCE_PATH — object-storage prefix (s3:// or gs://) for create/edit outputs
- E2E_TEMPLATE_PATH — optional; when .pptx/.odp/.ppt used for apply_template (PT-040)

Presentation E2E creates decks in-test under the E2E_SOURCE_PATH parent directory.
`options.allowed_layouts` uses fixtures/layouts_pptx.json / layouts_odp.json (ADR-016).

Cases: PT-037 create/read pptx; PT-038 edit re-read (ADR-041 add_slide fields); PT-039 merge;
PT-039b merge separator_slide (ADR-042); PT-040 template;
PT-041 odp round-trip; PT-042 legacy read_document coarse; PT-043 edit_document rejects pptx.

Module-level skipif when DocumentServer unreachable (ADR-021).
Per-test lazy skipif when pptx create, merge, odp CreateFile, or edit-on-source unsupported.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import (
    documentserver_reachable,
    mcp_reachable,
    presentation_edit_supported,
    presentation_merge_supported,
    presentation_odp_create_supported,
    presentation_pptx_create_supported,
)
from tests.office_mcp.test_e2e_office_tools import _call_tool_via_mcp

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.presentation,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]

_cfg = get_e2e_config()
FIXTURES = Path(__file__).parent / "fixtures"
PPTX_LAYOUTS: list[str] = json.loads((FIXTURES / "layouts_pptx.json").read_text())
ODP_LAYOUTS: list[str] = json.loads((FIXTURES / "layouts_odp.json").read_text())
_PRESENTATION_TEMPLATE_EXTS = (".pptx", ".odp", ".ppt")

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
requires_pptx_create = pytest.mark.skipif(
    lambda: not presentation_pptx_create_supported(),
    reason="DocumentServer Builder pptx CreateFile not supported on this installation.",
)
requires_merge = pytest.mark.skipif(
    lambda: not presentation_merge_supported(),
    reason="DocumentServer Builder presentation merge not supported on this installation.",
)
requires_edit = pytest.mark.skipif(
    lambda: not presentation_edit_supported(),
    reason="DocumentServer Builder presentation edit-on-source not supported on this installation.",
)
requires_odp = pytest.mark.skipif(
    lambda: not presentation_odp_create_supported(),
    reason="DocumentServer Builder odp CreateFile not supported on this installation.",
)

_CREATE_SLIDES = [
    {"layout": "Title Slide", "title": "E2E Create Title"},
    {
        "layout": "Title and Content",
        "title": "Content Slide",
        "bullets": ["Initial bullet one", "Initial bullet two"],
    },
    {"layout": "Blank"},
]

_EDITED_TITLE = "E2E-PRES-TITLE-EDITED"
_BULLET_A = "E2E-PRES-BULLET-A"
_BULLET_B = "E2E-PRES-BULLET-B"
_BULLET_C = "E2E-PRES-BULLET-C"
_ADD_SLIDE_TITLE = "E2E-PRES-ADD-TITLE"
_ADD_SLIDE_SUBTITLE = "E2E-PRES-ADD-SUBTITLE"
_ADD_SLIDE_ITEM_A = "E2E-PRES-ADD-ITEM-A"
_ADD_SLIDE_ITEM_B = "E2E-PRES-ADD-ITEM-B"
_ODP_EDITED_TITLE = "E2E-ODP-TITLE-EDITED"
_TEMPLATE_COMPANY = "Acme E2E Pres"
_TEMPLATE_SLIDE1_TITLE = "Quarterly Overview"
_MERGE_MARKER_A = "TOKEN-MERGE-PRES-A"
_MERGE_MARKER_B = "TOKEN-MERGE-PRES-B"
_COARSE_MARKER = "TOKEN-COARSE-PRES-042"
_EDIT_DOC_MARKER = "TOKEN-EDIT-DOC-PRES-043"

_MERGE_SLIDES_A = [
    {"layout": "Title Slide", "title": f"Merge deck A {_MERGE_MARKER_A}"},
    {"layout": "Blank"},
]
_MERGE_SLIDES_B = [
    {"layout": "Title Slide", "title": f"Merge deck B {_MERGE_MARKER_B}"},
]
_CREATE_ODP_SLIDES = [
    {"layout": "Title", "title": "ODP E2E Title"},
    {"layout": "Title and Content", "title": "ODP Section", "bullets": ["alpha", "beta"]},
]


def _unique_output_path(ext: str, label: str) -> str:
    base_dir = _cfg.source_path.rsplit("/", 1)[0]
    return f"{base_dir}/e2e-pres-{label}-{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"


def _slide_at(read: dict, index: int) -> dict:
    slides = read.get("slides") or read.get("units") or []
    for slide in slides:
        if slide.get("slide_index") == index:
            return slide
    if 0 <= index < len(slides):
        return slides[index]
    return {}


def _all_slides_text(read: dict) -> str:
    slides = read.get("slides") or read.get("units") or []
    return "\n".join(_slide_text(slide) for slide in slides)


def _slide_text(slide: dict) -> str:
    parts: list[str] = []
    if slide.get("title"):
        parts.append(str(slide["title"]))
    for shape in slide.get("shapes") or []:
        text = shape.get("text") or ""
        if text:
            parts.append(str(text))
    return "\n".join(parts)


async def _read_presentation_fine(source_path: str) -> dict:
    return await _call_tool_via_mcp(
        "office_read_presentation",
        {
            "source_path": source_path,
            "format": "structured",
            "options": {"read_mode": "fine"},
        },
    )


async def _create_presentation(
    label: str,
    slides: list[dict],
    *,
    ext: str,
    allowed_layouts: list[str],
) -> str:
    path = _unique_output_path(ext, label)
    result = await _call_tool_via_mcp(
        "office_create_presentation",
        {
            "slides": slides,
            "output_path": path,
            "options": {"allowed_layouts": allowed_layouts},
        },
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    assert result.get("output_path") == path
    return path


async def _create_three_slide_pptx(label: str) -> str:
    return await _create_presentation(
        label,
        _CREATE_SLIDES,
        ext="pptx",
        allowed_layouts=PPTX_LAYOUTS,
    )


async def _two_merge_sources() -> list[str]:
    return [
        await _create_presentation(
            "merge-a",
            _MERGE_SLIDES_A,
            ext="pptx",
            allowed_layouts=PPTX_LAYOUTS,
        ),
        await _create_presentation(
            "merge-b",
            _MERGE_SLIDES_B,
            ext="pptx",
            allowed_layouts=PPTX_LAYOUTS,
        ),
    ]


async def _presentation_template_path() -> str:
    """Use E2E_TEMPLATE_PATH when presentation; otherwise bootstrap placeholder deck."""
    tpl = _cfg.template_path.strip()
    if tpl.lower().endswith(_PRESENTATION_TEMPLATE_EXTS):
        return tpl
    return await _create_presentation(
        "template",
        [
            {"layout": "Title Slide", "title": "{{company_name}} Quarterly"},
            {
                "layout": "Title and Content",
                "title": "{{title}}",
                "bullets": ["Prepared for {{company_name}}"],
            },
        ],
        ext="pptx",
        allowed_layouts=PPTX_LAYOUTS,
    )


@requires_storage
@requires_jwt
@requires_mcp
@requires_pptx_create
async def test_e2e_create_read_presentation_pptx():
    """E2E: create pptx (3 slides) → fine read (PT-037)."""
    create_path = await _create_three_slide_pptx("create")

    read_result = await _read_presentation_fine(create_path)
    assert not read_result.get("isError"), read_result.get("text", read_result)
    assert read_result.get("category") == "presentation"
    assert read_result.get("read_mode") == "fine"
    assert read_result.get("slide_count") == 3
    assert read_result.get("unit_count") == 3
    layouts = read_result.get("layouts") or []
    assert isinstance(layouts, list)
    assert len(layouts) >= 1


@requires_storage
@requires_jwt
@requires_mcp
@requires_pptx_create
@requires_edit
async def test_e2e_edit_presentation_pptx():
    """E2E: create → fine read → edit (set_title, set_bullets, add_slide) → re-read (PT-038)."""
    create_path = await _create_three_slide_pptx("edit-src")
    edit_path = _unique_output_path("pptx", "edit-out")

    read1 = await _read_presentation_fine(create_path)
    assert not read1.get("isError"), read1.get("text", read1)
    assert read1.get("slide_count") == 3
    layouts = read1.get("layouts") or PPTX_LAYOUTS
    assert layouts, "fine read must return layouts[] for add_slide (ADR-016)"
    add_layout = "Title and Content" if "Title and Content" in layouts else layouts[-1]

    edit_result = await _call_tool_via_mcp(
        "office_edit_presentation",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {"op": "set_title", "slide_index": 0, "text": _EDITED_TITLE},
                {
                    "op": "set_bullets",
                    "slide_index": 1,
                    "items": [_BULLET_A, _BULLET_B, _BULLET_C],
                },
                {
                    "op": "add_slide",
                    "layout": add_layout,
                    "title": _ADD_SLIDE_TITLE,
                    "subtitle": _ADD_SLIDE_SUBTITLE,
                    "items": [_ADD_SLIDE_ITEM_A, _ADD_SLIDE_ITEM_B],
                },
            ],
            "options": {"allowed_layouts": layouts},
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path

    read2 = await _read_presentation_fine(edit_path)
    assert not read2.get("isError"), read2.get("text", read2)
    assert read2.get("read_mode") == "fine"
    assert read2.get("slide_count") == 4
    assert read2.get("unit_count") == 4

    slide0_text = _slide_text(_slide_at(read2, 0))
    assert _EDITED_TITLE in slide0_text

    slide1_text = _slide_text(_slide_at(read2, 1))
    assert _BULLET_A in slide1_text
    assert _BULLET_B in slide1_text
    assert _BULLET_C in slide1_text

    slides = read2.get("slides") or read2.get("units") or []
    assert len(slides) == 4
    new_slide = _slide_at(read2, 3)
    assert new_slide.get("layout") == add_layout
    new_slide_text = _slide_text(new_slide)
    assert _ADD_SLIDE_TITLE in new_slide_text
    assert _ADD_SLIDE_SUBTITLE in new_slide_text
    assert _ADD_SLIDE_ITEM_A in new_slide_text
    assert _ADD_SLIDE_ITEM_B in new_slide_text


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
async def test_e2e_merge_presentations():
    """E2E: merge two pptx decks → fine read asserts slide_count sum (PT-039)."""
    sources = await _two_merge_sources()
    merge_output = _unique_output_path("pptx", "merge")
    assert merge_output.endswith(".pptx")

    source_counts: list[int] = []
    for source in sources:
        read_src = await _read_presentation_fine(source)
        assert not read_src.get("isError"), read_src.get("text", read_src)
        source_counts.append(read_src.get("slide_count", 0))
    expected_total = sum(source_counts)
    assert expected_total >= 2

    merge_result = await _call_tool_via_mcp(
        "office_merge_presentations",
        {
            "source_paths": sources,
            "output_path": merge_output,
            "options": {"separator_slide": False},
        },
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("success") is True
    assert merge_result.get("output_path") == merge_output

    merged_read = await _read_presentation_fine(merge_output)
    assert not merged_read.get("isError"), merged_read.get("text", merged_read)
    assert merged_read.get("read_mode") == "fine"
    assert merged_read.get("slide_count") == expected_total
    assert merged_read.get("unit_count") == expected_total
    merged_text = _all_slides_text(merged_read)
    assert _MERGE_MARKER_A in merged_text
    assert _MERGE_MARKER_B in merged_text


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
async def test_e2e_merge_presentations_separator_slide():
    """E2E: merge with separator_slide=true + separator_layout (PT-039 / ADR-042)."""
    sources = await _two_merge_sources()
    merge_output = _unique_output_path("pptx", "merge-sep")

    source_counts: list[int] = []
    layouts: list[str] = PPTX_LAYOUTS
    for source in sources:
        read_src = await _read_presentation_fine(source)
        assert not read_src.get("isError"), read_src.get("text", read_src)
        source_counts.append(read_src.get("slide_count", 0))
        if read_src.get("layouts"):
            layouts = read_src["layouts"]
    expected_total = sum(source_counts) + (len(sources) - 1)
    assert expected_total >= 3

    separator_layout = "Section Header" if "Section Header" in layouts else layouts[0]

    merge_result = await _call_tool_via_mcp(
        "office_merge_presentations",
        {
            "source_paths": sources,
            "output_path": merge_output,
            "options": {
                "separator_slide": True,
                "separator_layout": separator_layout,
                "allowed_layouts": layouts,
            },
        },
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("success") is True
    assert merge_result.get("output_path") == merge_output

    merged_read = await _read_presentation_fine(merge_output)
    assert not merged_read.get("isError"), merged_read.get("text", merged_read)
    assert merged_read.get("read_mode") == "fine"
    assert merged_read.get("slide_count") == expected_total
    assert merged_read.get("unit_count") == expected_total
    merged_text = _all_slides_text(merged_read)
    assert _MERGE_MARKER_A in merged_text
    assert _MERGE_MARKER_B in merged_text


@requires_storage
@requires_jwt
@requires_mcp
@requires_pptx_create
@requires_edit
async def test_e2e_apply_template_presentation():
    """E2E: apply_template with {{company_name}} / slide_1_title; re-read verifies fill (PT-040)."""
    template_path = await _presentation_template_path()
    output_path = _unique_output_path("pptx", "template-filled")
    data = {
        "company_name": _TEMPLATE_COMPANY,
        "slide_1_title": _TEMPLATE_SLIDE1_TITLE,
    }

    apply_result = await _call_tool_via_mcp(
        "office_apply_template_presentation",
        {
            "template_path": template_path,
            "data": data,
            "output_path": output_path,
        },
    )
    assert not apply_result.get("isError"), apply_result.get("text", apply_result)
    assert apply_result.get("success") is True
    assert apply_result.get("output_path") == output_path

    read_result = await _read_presentation_fine(output_path)
    assert not read_result.get("isError"), read_result.get("text", read_result)
    all_text = _all_slides_text(read_result)
    assert _TEMPLATE_COMPANY in all_text
    assert _TEMPLATE_SLIDE1_TITLE in all_text
    assert "{{company_name}}" not in all_text
    assert "{{title}}" not in all_text


@requires_storage
@requires_jwt
@requires_mcp
@requires_odp
@requires_edit
async def test_e2e_odp_create_edit_roundtrip():
    """E2E: create odp → set_title edit → output remains .odp (PT-041 / ADR-016)."""
    create_path = _unique_output_path("odp", "create")
    edit_path = _unique_output_path("odp", "edit")
    assert create_path.endswith(".odp")
    assert edit_path.endswith(".odp")

    create_path = await _create_presentation(
        "odp-create",
        _CREATE_ODP_SLIDES,
        ext="odp",
        allowed_layouts=ODP_LAYOUTS,
    )

    read1 = await _read_presentation_fine(create_path)
    assert not read1.get("isError"), read1.get("text", read1)
    assert read1.get("slide_count") == 2

    edit_result = await _call_tool_via_mcp(
        "office_edit_presentation",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {"op": "set_title", "slide_index": 0, "text": _ODP_EDITED_TITLE},
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path
    assert edit_result.get("output_path", "").endswith(".odp")

    read2 = await _read_presentation_fine(edit_path)
    assert not read2.get("isError"), read2.get("text", read2)
    assert read2.get("read_mode") == "fine"
    assert _ODP_EDITED_TITLE in _slide_text(_slide_at(read2, 0))


async def _pptx_source_for_legacy_tests(label: str) -> str:
    """Minimal pptx on storage for legacy read/edit E2E (PT-042 / PT-043)."""
    return await _create_presentation(
        label,
        [{"layout": "Title Slide", "title": f"Legacy E2E {_COARSE_MARKER}"}],
        ext="pptx",
        allowed_layouts=PPTX_LAYOUTS,
    )


@requires_storage
@requires_jwt
@requires_mcp
@requires_pptx_create
async def test_e2e_read_document_pptx_coarse():
    """E2E: office_read_document pptx → txt/elements coarse — not read_presentation fine (PT-042)."""
    source_path = await _pptx_source_for_legacy_tests("read-doc-coarse")

    legacy = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": source_path, "format": "structured"},
    )
    assert not legacy.get("isError"), legacy.get("text", legacy)
    assert "elements" in legacy
    assert isinstance(legacy["elements"], list)
    assert legacy.get("conversion_output_type") == "txt"
    assert "slides" not in legacy
    assert "layouts" not in legacy
    assert legacy.get("category") != "presentation"
    assert legacy.get("read_mode") != "fine"
    legacy_text = " ".join(
        str(el.get("text", "")) for el in legacy["elements"] if isinstance(el, dict)
    )
    assert _COARSE_MARKER in legacy_text

    fine = await _read_presentation_fine(source_path)
    assert not fine.get("isError"), fine.get("text", fine)
    assert fine.get("read_mode") == "fine"
    assert fine.get("category") == "presentation"
    assert "slides" in fine or isinstance(fine.get("units"), list)
    assert "layouts" in fine


@requires_storage
@requires_jwt
@requires_mcp
@requires_pptx_create
async def test_presentation_edit_document_rejects_pptx():
    """E2E: office_edit_document on pptx must fail — Word oDoc API (PT-043 / PT-NA-02)."""
    source_path = await _create_presentation(
        "edit-doc-reject",
        [{"layout": "Title Slide", "title": f"Edit doc probe {_EDIT_DOC_MARKER}"}],
        ext="pptx",
        allowed_layouts=PPTX_LAYOUTS,
    )
    edit_output = _unique_output_path("pptx", "edit-doc-out")

    edit_result = await _call_tool_via_mcp(
        "office_edit_document",
        {
            "source_path": source_path,
            "output_path": edit_output,
            "edit_script": (
                'var doc = Api.GetDocument(); '
                'var p = doc.GetElement(0); '
                'if (p) { p.SetText("EDIT-DOC-SHOULD-NOT-APPLY"); }'
            ),
        },
    )
    assert edit_result.get("isError") is True or edit_result.get("success") is not True, (
        "office_edit_document must not succeed on pptx (Word API)"
    )
