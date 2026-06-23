"""Tests for office_edit_spreadsheet."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.tools.edit import office_edit_spreadsheet

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_edit_spreadsheet_set_cell_a1():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.xlsx"},
    ) as mock_run:
        result = await office_edit_spreadsheet(
            source_path="gs://b/book.xlsx",
            output_path="gs://b/out.xlsx",
            operations=[{"op": "set_cell", "sheet_index": 0, "cell": "B3", "value": 99}],
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "B3" in body
    assert "GetDocument" not in body


@pytest.mark.asyncio
async def test_edit_spreadsheet_uses_get_sheet():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_edit_spreadsheet(
            source_path="gs://b/book.xlsx",
            output_path="gs://b/out.xlsx",
            operations=[{"op": "set_cell", "sheet_index": 0, "cell": "A1", "value": "x"}],
        )
    body = mock_run.call_args[0][2]
    assert "GetSheet" in body or "GetActiveSheet" in body


@pytest.mark.asyncio
async def test_edit_spreadsheet_insert_rows_values():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.spreadsheet.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.xlsx"},
    ) as mock_run:
        result = await office_edit_spreadsheet(
            source_path="gs://b/book.xlsx",
            output_path="gs://b/out.xlsx",
            operations=[
                {
                    "op": "insert_rows",
                    "sheet_index": 0,
                    "at_row": 5,
                    "count": 2,
                    "values": [["a", "b"], ["c", "d"]],
                }
            ],
        )
    assert not result.get("isError"), result.get("text", result)
    body = mock_run.call_args[0][2]
    assert "InsertRows" in body
    assert "SetValue" in body
    assert "GetRangeByNumber" in body


@pytest.mark.asyncio
async def test_edit_spreadsheet_rejects_non_spreadsheet_output():
    result = await office_edit_spreadsheet(
        source_path="gs://b/book.xlsx",
        output_path="gs://b/out.pdf",
        operations=[{"op": "set_cell", "sheet_index": 0, "cell": "A1", "value": "x"}],
    )
    assert result.get("isError") is True
    assert "spreadsheet" in result.get("text", "").lower()
