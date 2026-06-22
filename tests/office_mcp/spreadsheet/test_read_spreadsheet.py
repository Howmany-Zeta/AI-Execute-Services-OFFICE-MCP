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
