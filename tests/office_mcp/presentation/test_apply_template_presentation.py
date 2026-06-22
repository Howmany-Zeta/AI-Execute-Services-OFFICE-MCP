"""Tests for office_apply_template_presentation."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.template import office_apply_template_presentation

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_apply_template_replaces_placeholders():
    with patch(
        "aiecs.tools.office_tool.presentation.tools.template.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/t.pptx", "pptx", "gs://b/t.pptx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.presentation.tools.template.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pptx"},
    ) as mock_run:
        result = await office_apply_template_presentation(
            template_path="gs://b/t.pptx",
            data={"company_name": "Acme Corp", "slide_1_title": "Welcome"},
            output_path="gs://b/out.pptx",
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "GetPresentation" in body
    assert "company_name" in body
    assert "slide_1_title" in body or "Welcome" in body
