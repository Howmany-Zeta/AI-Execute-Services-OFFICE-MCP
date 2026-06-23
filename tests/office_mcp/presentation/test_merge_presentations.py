"""Tests for office_merge_presentations."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.merge import office_merge_presentations

pytestmark = pytest.mark.asyncio

PPTX_LAYOUTS = ["Title Slide", "Title and Content", "Section Header", "Two Content", "Blank"]


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
    assert 'AddSlide("Blank")' not in script


@pytest.mark.asyncio
async def test_merge_with_separator_layout_in_script():
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
            options={
                "separator_slide": True,
                "separator_layout": "Section Header",
                "allowed_layouts": PPTX_LAYOUTS,
            },
        )
    assert result.get("success") is True
    script = mock_run.call_args[0][0]
    assert 'AddSlide("Section Header")' in script
    assert 'AddSlide("Blank")' not in script


@pytest.mark.asyncio
async def test_merge_separator_missing_layout_rejected():
    result = await office_merge_presentations(
        source_paths=["gs://b/a.pptx", "gs://b/b.pptx"],
        output_path="gs://b/merged.pptx",
        options={"separator_slide": True, "allowed_layouts": PPTX_LAYOUTS},
    )
    assert result.get("isError") is True
    assert "separator_layout" in result.get("text", "")


@pytest.mark.asyncio
async def test_merge_separator_unknown_layout_rejected():
    result = await office_merge_presentations(
        source_paths=["gs://b/a.pptx", "gs://b/b.pptx"],
        output_path="gs://b/merged.pptx",
        options={
            "separator_slide": True,
            "separator_layout": "Unknown Layout",
            "allowed_layouts": PPTX_LAYOUTS,
        },
    )
    assert result.get("isError") is True
    assert "not in allowed layouts" in result.get("text", "")
