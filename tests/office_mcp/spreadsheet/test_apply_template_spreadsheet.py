"""Tests for office_apply_template_spreadsheet."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.tools.template import office_apply_template_spreadsheet

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_apply_template_explicit_address():
    with patch(
        "aiecs.tools.office_tool.spreadsheet.tools.template.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/t.xlsx", "xlsx", "gs://b/t.xlsx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.spreadsheet.tools.template.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.xlsx"},
    ) as mock_run:
        result = await office_apply_template_spreadsheet(
            template_path="gs://b/t.xlsx",
            data={"Summary!B2": 1000, "company_name": "Acme"},
            output_path="gs://b/out.xlsx",
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "Summary" in body
    assert "B2" in body
    assert "company_name" in body or "Acme" in body
