"""Tests for office_merge_presentations."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.merge import office_merge_presentations

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_merge_presentations_calls_builder():
    with patch(
        "aiecs.tools.office_tool.presentation.tools.merge.resolve_fetch_url",
        new_callable=AsyncMock,
        return_value="https://signed/a.pptx",
    ), patch(
        "aiecs.tools.office_tool.presentation.tools.merge.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/merged.pptx"},
    ) as mock_run:
        result = await office_merge_presentations(
            source_paths=["gs://b/a.pptx", "gs://b/b.pptx"],
            output_path="gs://b/merged.pptx",
        )
    assert result.get("success") is True
    script = mock_run.call_args[0][0]
    assert "GetPresentation" in script
    assert "SlidesToJSON" in script
