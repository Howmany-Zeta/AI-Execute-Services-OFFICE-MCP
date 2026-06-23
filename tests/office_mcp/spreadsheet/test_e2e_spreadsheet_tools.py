"""
E2E tests for Spreadsheet vertical tools.

Requires `.env.test` (loaded by tests/conftest.py):
- DOCUMENTSERVER_URL — DocumentServer healthcheck target
- DOCUMENTSERVER_JWT_SECRET — Builder / Conversion / Command APIs
- E2E_MCP_URL — MCP HTTP base (tools/call via _call_tool_via_mcp)
- E2E_MCP_PUBLIC_URL or MCP_PUBLIC_URL — DS-reachable URL for docbuilder scripts (optional)
- E2E_SOURCE_PATH — object-storage path (s3:// or gs://) for create/edit/read outputs
- E2E_SPREADSHEET_SOURCE_PATH — spreadsheet-specific primary path (falls back to E2E_SOURCE_PATH)
- E2E_SPREADSHEET_SOURCE_PATHS — spreadsheet merge / multi-source list (falls back to E2E_SOURCE_PATHS)
- E2E_SOURCE_PATHS — comma-separated paths for merge E2E (optional; tests may create sources)
- E2E_TEMPLATE_PATH — optional; xlsx/ods used for apply_template; docx bootstraps in-test
- E2E_SOURCE_PATH or E2E_SOURCE_PATHS entry ending in `.xls` — optional; required to run ST-053

Module-level lazy skipif when DocumentServer unreachable (ADR-021).
Per-test lazy skipif when GetSheetsCount fine read, ods CreateFile, merge, or edit-on-source
unsupported on this DocumentServer install (probes deferred until test run — not import).

Tests: ST-037 xlsx create/read/edit; ST-038 ods round-trip; ST-039 merge; ST-040 template;
ST-041 legacy read_document coarse; ST-053 .xls read (fine or coarse fallback).
"""

from __future__ import annotations

import uuid

import pytest

from aiecs.tools.office_tool.spreadsheet.parser.workbook import parse_a1
from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import (
    documentserver_reachable,
    mcp_reachable,
    spreadsheet_edit_supported,
    spreadsheet_fine_read_supported,
    spreadsheet_merge_builder_supported,
    spreadsheet_ods_builder_supported,
)
from tests.office_mcp.test_e2e_office_tools import _call_tool_via_mcp

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.spreadsheet,
    pytest.mark.e2e,
    pytest.mark.skipif(
        lambda: not documentserver_reachable(),
        reason="DocumentServer not reachable",
    ),
]

_cfg = get_e2e_config()

requires_jwt = pytest.mark.skipif(
    not _cfg.has_jwt,
    reason="DOCUMENTSERVER_JWT_SECRET required in .env.test for Builder/Conversion/Command APIs.",
)
requires_mcp = pytest.mark.skipif(
    lambda: not mcp_reachable(),
    reason="MCP server must be running at E2E_MCP_URL for proxy-mode storage E2E.",
)
requires_storage = pytest.mark.skipif(
    not _cfg.has_spreadsheet_source_path,
    reason="E2E_SPREADSHEET_SOURCE_PATH (or E2E_SOURCE_PATH) required in .env.test.",
)
requires_fine_read = pytest.mark.skipif(
    lambda: not spreadsheet_fine_read_supported(),
    reason="GetSheetsCount fine read not available on DocumentServer (ADR-021).",
)
requires_ods = pytest.mark.skipif(
    lambda: not spreadsheet_ods_builder_supported(),
    reason="DocumentServer Builder ods CreateFile not supported on this installation.",
)
requires_merge = pytest.mark.skipif(
    lambda: not spreadsheet_merge_builder_supported(),
    reason="DocumentServer Builder spreadsheet merge not supported on this installation.",
)
requires_edit = pytest.mark.skipif(
    lambda: not spreadsheet_edit_supported(),
    reason="DocumentServer Builder spreadsheet edit-on-source not supported on this installation.",
)

_SPREADSHEET_TEMPLATE_EXTS = (".xlsx", ".xls", ".ods")


def _resolve_xls_source_path() -> str:
    """Return first configured `.xls` path from spreadsheet E2E source env vars."""
    primary = _cfg.spreadsheet_source_path.strip()
    if primary.lower().endswith(".xls"):
        return primary
    for part in _cfg.spreadsheet_source_paths.replace(";", ",").split(","):
        candidate = part.strip()
        if candidate.lower().endswith(".xls"):
            return candidate
    return ""


_XLS_SOURCE_PATH = _resolve_xls_source_path()

requires_xls_fixture = pytest.mark.skipif(
    not _XLS_SOURCE_PATH,
    reason="E2E_SPREADSHEET_SOURCE_PATH or E2E_SPREADSHEET_SOURCE_PATHS must include a .xls file for xls read E2E (ST-053).",
)

_CREATE_SHEETS = [
    {"name": "Summary", "rows": [["Product", "Qty"], ["Widget", "TOKEN-E2E-SHEET1"]]},
    {"name": "Data", "rows": [["TOKEN-E2E-SHEET2", "B"], ["1", "2"]]},
]

_CELL_MARKER = "TOKEN-E2E-SHEET1"
_CELL_REPLACED = "TOKEN-E2E-EDITED-CELL"
_RANGE_MARKER = "TOKEN-E2E-SHEET2"
_RANGE_REPLACED = "TOKEN-E2E-RANGE-A"


def _unique_output_path(ext: str, label: str) -> str:
    base_dir = _cfg.spreadsheet_source_path.rsplit("/", 1)[0]
    return f"{base_dir}/e2e-{label}-{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"


def _sheet_by_name(result: dict, name: str) -> dict | None:
    sheets = result.get("sheets") or result.get("units") or []
    for sheet in sheets:
        if sheet.get("name") == name:
            return sheet
    return None


def _rows_text(sheet: dict) -> str:
    rows = sheet.get("rows") or []
    return "\n".join(",".join(str(cell) for cell in row) for row in rows)


def _cell_value(sheet: dict, cell: str) -> str | int | float | None:
    row_idx, col_idx = parse_a1(cell)
    rows = sheet.get("rows") or []
    if row_idx >= len(rows) or col_idx >= len(rows[row_idx]):
        return None
    return rows[row_idx][col_idx]


def _sheet_names(result: dict) -> list[str]:
    sheets = result.get("sheets") or result.get("units") or []
    return [str(s.get("name", "")) for s in sheets]


async def _read_spreadsheet_fine(source_path: str) -> dict:
    return await _call_tool_via_mcp(
        "office_read_spreadsheet",
        {
            "source_path": source_path,
            "format": "structured",
            "options": {"read_mode": "fine"},
        },
    )


async def _read_spreadsheet_coarse(source_path: str) -> dict:
    return await _call_tool_via_mcp(
        "office_read_spreadsheet",
        {
            "source_path": source_path,
            "format": "structured",
            "options": {"read_mode": "coarse"},
        },
    )


async def _create_workbook(label: str, sheets: list[dict]) -> str:
    path = _unique_output_path("xlsx", label)
    result = await _call_tool_via_mcp(
        "office_create_spreadsheet",
        {"sheets": sheets, "output_path": path},
    )
    assert not result.get("isError"), result.get("text", result)
    assert result.get("success") is True
    assert result.get("output_path") == path
    return path


async def _two_merge_sources_with_collision() -> tuple[list[str], list[str]]:
    """Two workbooks each with sheet 'Summary' — exercises rename_conflicts _2 suffix (ST-048)."""
    marker_a = "TOKEN-MERGE-COLLISION-A"
    marker_b = "TOKEN-MERGE-COLLISION-B"
    source_a = await _create_workbook(
        "merge-collision-a",
        [{"name": "Summary", "rows": [["Marker"], [marker_a]]}],
    )
    source_b = await _create_workbook(
        "merge-collision-b",
        [{"name": "Summary", "rows": [["Marker"], [marker_b]]}],
    )
    return [source_a, source_b], [marker_a, marker_b]


async def _spreadsheet_template_path() -> str:
    """Use E2E_TEMPLATE_PATH when spreadsheet; otherwise bootstrap Summary template."""
    tpl = _cfg.template_path.strip()
    if tpl.lower().endswith(_SPREADSHEET_TEMPLATE_EXTS):
        return tpl
    return await _create_workbook(
        "template",
        [
            {
                "name": "Summary",
                "rows": [
                    ["Metric", "Value"],
                    ["{{company_name}}", "TBD"],
                ],
            },
        ],
    )


@requires_storage
@requires_jwt
@requires_mcp
@requires_fine_read
async def test_e2e_create_read_edit_spreadsheet_xlsx():
    """E2E: create xlsx (2 sheets) → fine read → set_cell + set_range edit → re-read (ST-037)."""
    create_path = _unique_output_path("xlsx", "create")
    edit_path = _unique_output_path("xlsx", "edit")

    create_result = await _call_tool_via_mcp(
        "office_create_spreadsheet",
        {"sheets": _CREATE_SHEETS, "output_path": create_path},
    )
    assert not create_result.get("isError"), create_result.get("text", create_result)
    assert create_result.get("success") is True
    assert create_result.get("output_path") == create_path

    read1 = await _read_spreadsheet_fine(create_path)
    assert not read1.get("isError"), read1.get("text", read1)
    assert read1.get("category") == "spreadsheet"
    assert read1.get("read_mode") == "fine"
    assert read1.get("unit_count") == 2
    summary1 = _sheet_by_name(read1, "Summary")
    data1 = _sheet_by_name(read1, "Data")
    assert summary1 is not None and data1 is not None
    assert _CELL_MARKER in _rows_text(summary1)
    assert _RANGE_MARKER in _rows_text(data1)

    edit_result = await _call_tool_via_mcp(
        "office_edit_spreadsheet",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {
                    "op": "set_cell",
                    "sheet_name": "Summary",
                    "cell": "B2",
                    "value": _CELL_REPLACED,
                },
                {
                    "op": "set_range",
                    "sheet_name": "Data",
                    "range": "A1:B1",
                    "values": [[_RANGE_REPLACED, "B"]],
                },
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path

    read2 = await _read_spreadsheet_fine(edit_path)
    assert not read2.get("isError"), read2.get("text", read2)
    assert read2.get("unit_count") == 2
    summary2 = _sheet_by_name(read2, "Summary")
    data2 = _sheet_by_name(read2, "Data")
    assert summary2 is not None and data2 is not None
    summary_text = _rows_text(summary2)
    data_text = _rows_text(data2)
    assert _CELL_REPLACED in summary_text
    assert _CELL_MARKER not in summary_text
    assert _RANGE_REPLACED in data_text
    assert _RANGE_MARKER not in data_text

    add_sheet_path = _unique_output_path("xlsx", "add-sheet")
    add_sheet_result = await _call_tool_via_mcp(
        "office_edit_spreadsheet",
        {
            "source_path": edit_path,
            "output_path": add_sheet_path,
            "operations": [{"op": "add_sheet", "name": "Notes"}],
        },
    )
    assert not add_sheet_result.get("isError"), add_sheet_result.get("text", add_sheet_result)
    assert add_sheet_result.get("success") is True

    read_add = await _read_spreadsheet_fine(add_sheet_path)
    assert not read_add.get("isError"), read_add.get("text", read_add)
    assert read_add.get("unit_count") == 3
    assert _sheet_by_name(read_add, "Notes") is not None

    copy_path = _unique_output_path("xlsx", "copy")
    copy_result = await _call_tool_via_mcp(
        "office_edit_spreadsheet",
        {
            "source_path": add_sheet_path,
            "output_path": copy_path,
            "operations": [
                {
                    "op": "copy_sheet",
                    "sheet_name": "Summary",
                    "new_name": "Summary Copy",
                },
            ],
        },
    )
    assert not copy_result.get("isError"), copy_result.get("text", copy_result)
    assert copy_result.get("success") is True

    read3 = await _read_spreadsheet_fine(copy_path)
    assert not read3.get("isError"), read3.get("text", read3)
    assert read3.get("unit_count") == 4
    assert _sheet_by_name(read3, "Summary Copy") is not None
    assert _sheet_by_name(read3, "Notes") is not None
    copy_sheet = _sheet_by_name(read3, "Summary Copy")
    assert copy_sheet is not None
    assert _CELL_REPLACED in _rows_text(copy_sheet)


@requires_storage
@requires_jwt
@requires_mcp
@requires_ods
async def test_e2e_ods_create_edit_roundtrip_spreadsheet():
    """E2E: create ods → edit → output remains .ods (ST-038)."""
    create_path = _unique_output_path("ods", "create")
    edit_path = _unique_output_path("ods", "edit")
    assert create_path.endswith(".ods")
    assert edit_path.endswith(".ods")

    create_result = await _call_tool_via_mcp(
        "office_create_spreadsheet",
        {
            "sheets": [{"name": "Sheet1", "rows": [["Label", "Value"], ["E2E-ODS", "1"]]}],
            "output_path": create_path,
        },
    )
    assert not create_result.get("isError"), create_result.get("text", create_result)
    assert create_result.get("success") is True
    assert create_result.get("output_path") == create_path

    edit_result = await _call_tool_via_mcp(
        "office_edit_spreadsheet",
        {
            "source_path": create_path,
            "output_path": edit_path,
            "operations": [
                {
                    "op": "set_cell",
                    "sheet_name": "Sheet1",
                    "cell": "B2",
                    "value": "99",
                },
            ],
        },
    )
    assert not edit_result.get("isError"), edit_result.get("text", edit_result)
    assert edit_result.get("success") is True
    assert edit_result.get("output_path") == edit_path
    assert edit_result.get("output_path", "").endswith(".ods")

    if spreadsheet_fine_read_supported():
        read_result = await _read_spreadsheet_fine(edit_path)
        assert not read_result.get("isError"), read_result.get("text", read_result)
        sheet1 = _sheet_by_name(read_result, "Sheet1")
        assert sheet1 is not None
        assert "99" in _rows_text(sheet1)


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
@requires_fine_read
async def test_e2e_merge_spreadsheets():
    """E2E: merge two xlsx with colliding sheet names → Summary + Summary_2 (ST-039, ST-048)."""
    sources, markers = await _two_merge_sources_with_collision()
    merge_output = _unique_output_path("xlsx", "merge")
    assert merge_output.endswith(".xlsx")

    merge_result = await _call_tool_via_mcp(
        "office_merge_spreadsheets",
        {
            "source_paths": sources,
            "output_path": merge_output,
            "options": {"rename_conflicts": True},
        },
    )
    assert not merge_result.get("isError"), merge_result.get("text", merge_result)
    assert merge_result.get("success") is True
    assert merge_result.get("output_path") == merge_output

    merged_read = await _read_spreadsheet_fine(merge_output)
    assert not merged_read.get("isError"), merged_read.get("text", merged_read)
    assert merged_read.get("read_mode") == "fine"
    assert merged_read.get("unit_count") == 2
    names = _sheet_names(merged_read)
    assert "Summary" in names
    assert "Summary_2" in names

    summary = _sheet_by_name(merged_read, "Summary")
    summary_2 = _sheet_by_name(merged_read, "Summary_2")
    assert summary is not None and summary_2 is not None
    summary_text = _rows_text(summary)
    summary_2_text = _rows_text(summary_2)
    assert markers[0] in summary_text
    assert markers[1] in summary_2_text
    assert markers[0] not in summary_2_text
    assert markers[1] not in summary_text


@requires_storage
@requires_jwt
@requires_mcp
@requires_merge
async def test_e2e_merge_rename_conflicts_false_is_error():
    """E2E: merge colliding sheet names with rename_conflicts=false → {isError} (ST-048)."""
    source_a = await _create_workbook(
        "merge-false-a",
        [{"name": "Summary", "rows": [["TOKEN-MERGE-FALSE-A"]]}],
    )
    source_b = await _create_workbook(
        "merge-false-b",
        [{"name": "Summary", "rows": [["TOKEN-MERGE-FALSE-B"]]}],
    )
    merge_output = _unique_output_path("xlsx", "merge-false")

    merge_result = await _call_tool_via_mcp(
        "office_merge_spreadsheets",
        {
            "source_paths": [source_a, source_b],
            "output_path": merge_output,
            "options": {"rename_conflicts": False},
        },
    )
    assert merge_result.get("isError") is True
    text = merge_result.get("text", "")
    assert "conflict" in text.lower() or "Sheet name" in text


@requires_storage
@requires_jwt
@requires_mcp
@requires_edit
@requires_fine_read
async def test_e2e_apply_template_spreadsheet():
    """E2E: Summary!B2 explicit + {{company_name}} placeholder; re-read verifies fill (ST-040)."""
    template_path = await _spreadsheet_template_path()
    output_path = _unique_output_path("xlsx", "template-filled")
    data = {"Summary!B2": 125000, "company_name": "Acme E2E"}

    apply_result = await _call_tool_via_mcp(
        "office_apply_template_spreadsheet",
        {
            "template_path": template_path,
            "data": data,
            "output_path": output_path,
        },
    )
    assert not apply_result.get("isError"), apply_result.get("text", apply_result)
    assert apply_result.get("success") is True
    assert apply_result.get("output_path") == output_path

    read_result = await _read_spreadsheet_fine(output_path)
    assert not read_result.get("isError"), read_result.get("text", read_result)
    summary = _sheet_by_name(read_result, "Summary")
    assert summary is not None
    summary_text = _rows_text(summary)
    b2 = _cell_value(summary, "B2")
    a2 = _cell_value(summary, "A2")
    assert b2 == 125000 or str(b2) == "125000"
    assert a2 == "Acme E2E" or "Acme E2E" in str(a2)
    assert "{{company_name}}" not in summary_text
    assert "Acme E2E" not in str(b2)


@requires_storage
@requires_jwt
@requires_mcp
async def test_e2e_read_document_xlsx_coarse():
    """E2E: office_read_document xlsx → csv/elements coarse — not read_spreadsheet fine (ST-041)."""
    marker = "TOKEN-COARSE-041"
    source_path = await _create_workbook(
        "read-doc-coarse",
        [
            {"name": "Summary", "rows": [["Label", "Value"], ["Marker", marker]]},
            {"name": "Extra", "rows": [["Marker", marker]]},
        ],
    )

    legacy = await _call_tool_via_mcp(
        "office_read_document",
        {"source_path": source_path, "format": "structured"},
    )
    assert not legacy.get("isError"), legacy.get("text", legacy)
    assert "elements" in legacy
    assert isinstance(legacy["elements"], list)
    assert legacy.get("conversion_output_type") == "csv"
    assert "sheets" not in legacy
    assert legacy.get("category") != "spreadsheet"
    assert legacy.get("read_mode") != "fine"
    legacy_text = " ".join(
        str(el.get("text", "")) for el in legacy["elements"] if isinstance(el, dict)
    )
    assert marker in legacy_text

    if spreadsheet_fine_read_supported():
        fine = await _read_spreadsheet_fine(source_path)
        assert not fine.get("isError"), fine.get("text", fine)
        assert fine.get("read_mode") == "fine"
        assert fine.get("category") == "spreadsheet"
        assert "sheets" in fine
        assert fine.get("unit_count", 0) >= 2
        assert legacy.get("unit_count") != fine.get("unit_count")


@requires_storage
@requires_jwt
@requires_mcp
@requires_xls_fixture
async def test_e2e_read_spreadsheet_xls():
    """E2E: read legacy .xls — fine when GetSheetsCount available, else coarse (ST-053)."""
    source_path = _XLS_SOURCE_PATH
    assert source_path.lower().endswith(".xls")

    if spreadsheet_fine_read_supported():
        result = await _read_spreadsheet_fine(source_path)
        assert not result.get("isError"), result.get("text", result)
        assert result.get("success") is True
        assert result.get("category") == "spreadsheet"
        assert result.get("read_mode") == "fine"
        units = result.get("sheets") or result.get("units") or []
        assert isinstance(units, list)
        assert result.get("unit_count", len(units)) >= 1
    else:
        result = await _read_spreadsheet_coarse(source_path)
        assert not result.get("isError"), result.get("text", result)
        assert result.get("success") is True
        assert result.get("category") == "spreadsheet"
        assert result.get("read_mode") == "coarse"
        assert result.get("_note")
        units = result.get("sheets") or result.get("units") or []
        assert isinstance(units, list)
        assert result.get("unit_count", len(units)) >= 1
