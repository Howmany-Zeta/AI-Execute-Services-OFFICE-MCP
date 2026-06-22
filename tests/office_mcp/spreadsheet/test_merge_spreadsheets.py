"""Tests for office_merge_spreadsheets."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.tools.merge import office_merge_spreadsheets

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_merge_spreadsheets_calls_builder():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.merge.resolve_fetch_url",
        new_callable=AsyncMock,
        return_value="https://signed/a.xlsx",
    ), patch(
        "aiecs.tools.office_tool.spreadsheet.tools.merge.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/merged.xlsx"},
    ) as mock_run:
        result = await office_merge_spreadsheets(
            source_paths=["gs://b/a.xlsx", "gs://b/b.xlsx"],
            output_path="gs://b/merged.xlsx",
        )
    assert result.get("success") is True
    script = mock_run.call_args[0][0]
    assert "GetSheetsCount" in script
