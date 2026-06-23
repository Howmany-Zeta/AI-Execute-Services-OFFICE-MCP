"""Tests for office_create_spreadsheet."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.tools.create import TOOL_DEF, office_create_spreadsheet

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_spreadsheet_calls_builder():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.xlsx"},
    ) as mock_run:
        result = await office_create_spreadsheet(
            sheets=[{"name": "Data", "rows": [["A", "B"], ["1", "2"]]}],
            output_path="gs://b/out.xlsx",
        )
    assert result.get("success") is True
    script = mock_run.call_args[0][0]
    assert "CreateFile" in script
    assert "Data" in script


@pytest.mark.asyncio
async def test_create_spreadsheet_no_get_document():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_spreadsheet(
            sheets=[{"name": "S1", "rows": [["x"]]}],
            output_path="gs://b/out.xlsx",
        )
    script = mock_run.call_args[0][0]
    assert "GetDocument" not in script
    assert "GetActiveSheet" in script


def test_create_tool_def_schema_from_pydantic():
    schema = TOOL_DEF["inputSchema"]
    assert schema["type"] == "object"
    sheets = schema["properties"]["sheets"]
    assert sheets["minItems"] == 1
    item_props = sheets["items"]["$ref"]
    defs = schema["$defs"]
    sheet_def = defs[item_props.split("/")[-1]]
    assert "header_row" in sheet_def["properties"]
    assert sheet_def["properties"]["name"]["minLength"] == 1
