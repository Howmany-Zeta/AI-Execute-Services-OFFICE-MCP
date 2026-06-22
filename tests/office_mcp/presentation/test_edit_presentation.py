"""Tests for office_edit_presentation."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.edit import office_edit_presentation

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_edit_presentation_uses_get_presentation():
    with patch(
        "aiecs.tools.office_tool.presentation.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.presentation.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pptx"},
    ) as mock_run:
        result = await office_edit_presentation(
            source_path="gs://b/deck.pptx",
            output_path="gs://b/out.pptx",
            operations=[{"op": "set_title", "slide_index": 0, "text": "New Title"}],
        )
    assert result.get("success") is True
    mock_run.assert_called_once()
    body = mock_run.call_args[0][2]
    assert "GetPresentation" in body
    assert "New Title" in body
