"""Tests for office_fill_pdf_form (ADR-019)."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.pdf.tools.fill_form import office_fill_pdf_form

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_fill_form_setvalue_per_field():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.fill_form.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/form.pdf", "pdf", "gs://b/form.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.fill_form.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pdf"},
    ) as mock_run:
        result = await office_fill_pdf_form(
            source_path="gs://b/form.pdf",
            data={"company_name": "Acme Corp"},
            output_path="gs://b/out.pdf",
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "GetFormFieldByName" in body
    assert "SetValue" in body
    assert "company_name" in body


@pytest.mark.asyncio
async def test_no_apply_template_pdf_tool():
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aiecs.tools.office_tool.pdf.tools.apply_template")
