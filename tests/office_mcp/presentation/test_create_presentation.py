"""Tests for office_create_presentation."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.create import office_create_presentation

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_presentation_calls_builder():
    with patch(
        "aiecs.tools.office_tool.presentation.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pptx"},
    ) as mock_run:
        result = await office_create_presentation(
            slides=[{"layout": "Title Slide", "title": "Hello"}],
            output_path="gs://b/out.pptx",
        )
    assert result.get("success") is True
    mock_run.assert_called_once()
    script = mock_run.call_args[0][0]
    assert "GetPresentation" in script
    assert "Title Slide" in script
    assert "Hello" in script
