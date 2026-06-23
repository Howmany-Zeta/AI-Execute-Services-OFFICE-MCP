"""Tests for office_read_spreadsheet."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.tools.read import (
    TOOL_DEF,
    TOOL_NAME,
    office_read_spreadsheet,
)

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"


class TestReadSpreadsheetTool:
    def test_tool_exports(self):
        assert TOOL_NAME == "office_read_spreadsheet"
        assert "[Spreadsheet]" in TOOL_DEF["description"]

    async def test_fine_read_success(self):
        sidecar = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_spreadsheet(
                source_path="gs://b/book.xlsx",
                format="structured",
            )

        assert result.get("success") is True
        assert result.get("category") == "spreadsheet"
        assert result.get("sheets") == result.get("units")
        assert len(result.get("units", [])) == 2
        summary = result["units"][0]
        assert summary.get("headers") == summary["rows"][0]

    async def test_fine_read_include_formulas_sidecar(self):
        sidecar = {
            "sheets": [
                {
                    "sheet_index": 0,
                    "name": "Data",
                    "rows": [["=SUM(A1:A2)", 10]],
                    "used_range": "A1:B1",
                    "row_count": 1,
                    "col_count": 2,
                }
            ]
        }
        with patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ) as mock_sidecar:
            result = await office_read_spreadsheet(
                source_path="gs://b/book.xlsx",
                format="structured",
                options={"include_formulas": True},
            )
        assert mock_sidecar.call_args[0][3].count("GetFormula") >= 1
        assert not result.get("isError"), result.get("text", result)
        assert result["units"][0]["rows"][0][0] == "=SUM(A1:A2)"

    async def test_fine_read_range_filter(self):
        sidecar = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_spreadsheet(
                source_path="gs://b/book.xlsx",
                format="structured",
                options={"range": "A1:B2"},
            )
        assert not result.get("isError"), result.get("text", result)
        summary = result["units"][0]
        assert summary["rows"] == [["Product", "Units"], ["Widget A", 120]]
        assert summary["headers"] == ["Product", "Units"]
        assert summary["used_range"] == "A1:B2"

    async def test_fine_read_outline_range_updates_used_range(self):
        sidecar = json.loads((FIXTURES / "workbook_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_spreadsheet(
                source_path="gs://b/book.xlsx",
                format="outline",
                options={"range": "A1:B1"},
            )
        assert result.get("units")[0]["used_range"] == "A1:B1"

    async def test_coarse_read_success(self):
        with patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/book.xlsx", "xlsx", "gs://b/book.xlsx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.spreadsheet.tools.read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=("A,B\n1,2", None),
        ):
            result = await office_read_spreadsheet(
                source_path="gs://b/book.xlsx",
                format="structured",
                options={"read_mode": "coarse"},
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "coarse"

    async def test_missing_source_error(self):
        result = await office_read_spreadsheet()
        assert result.get("isError") is True
