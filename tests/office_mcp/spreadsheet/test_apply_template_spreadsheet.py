"""Tests for office_apply_template_spreadsheet."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.spreadsheet.builder.template import build_template_script
from aiecs.tools.office_tool.spreadsheet.tools.template import office_apply_template_spreadsheet

pytestmark = pytest.mark.asyncio


def test_build_template_explicit_wins_dedup():
    script = build_template_script(
        {"Summary!B2": 1000, "product_name": "Acme"},
        file_ext="xlsx",
    )
    assert "consumed" in script
    assert 'GetRange("B2")' in script
    assert "SetValue(1000)" in script
    assert "SetValue('1000')" not in script
    assert 'if (!consumed["product_name"])' in script
    assert '{{product_name}}' not in script.split('if (!consumed["product_name"])')[0]


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


@pytest.mark.asyncio
async def test_apply_template_rejects_non_spreadsheet_output():
    result = await office_apply_template_spreadsheet(
        template_path="gs://b/t.xlsx",
        data={"Summary!B2": 1000},
        output_path="gs://b/out.pdf",
    )
    assert result.get("isError") is True
    assert "spreadsheet" in result.get("text", "").lower()
