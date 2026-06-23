"""Tests for office_read_presentation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.read import (
    COARSE_NOTE,
    TOOL_DEF,
    TOOL_NAME,
    office_read_presentation,
)

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"


class TestReadPresentationTool:
    def test_tool_exports(self):
        assert TOOL_NAME == "office_read_presentation"
        assert "[Presentation]" in TOOL_DEF["description"]

    async def test_fine_read_success(self):
        sidecar = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
            )

        assert result.get("success") is True
        assert result.get("category") == "presentation"
        assert result.get("slides") == result.get("units")
        assert result.get("slide_count") == 3
        assert "layouts" in result
        assert "Title Slide" in result["layouts"]

    async def test_coarse_read_success(self):
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=("Slide One\n\nSlide Two", None),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
                options={"read_mode": "coarse"},
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "coarse"
        assert result.get("_note") == (
            "Coarse txt read is for preview only — re-read with read_mode=fine before edit."
        )
        assert result.get("_locator_note")

    async def test_fine_sidecar_failure_coarse_fallback(self):
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(None, "sidecar failed"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=("Slide One\n\nSlide Two", None),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
                options={"read_mode": "fine", "allow_coarse_fallback": True},
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "coarse"
        assert COARSE_NOTE in (result.get("_note") or "")

    async def test_fine_sidecar_failure_no_fallback(self):
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(None, "sidecar failed"),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
                options={"read_mode": "fine", "allow_coarse_fallback": False},
            )

        assert result.get("isError") is True
        assert "sidecar failed" in result.get("text", "")

    async def test_fine_read_incomplete_layouts_note(self):
        sidecar = {
            "slides": [
                {
                    "layout": "Title Slide",
                    "title": "Only layout used",
                    "shapes": [{"placeholder_type": "title", "text": "Only layout used"}],
                }
            ]
        }
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "fine"
        assert "layouts[] may be incomplete" in (result.get("_note") or "")
        assert "ADR-047" in (result.get("_note") or "")
        assert result.get("_locator_note")

    async def test_fine_read_passes_slide_range_to_extract_body(self):
        sidecar = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ) as mock_sidecar:
            await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="structured",
                options={"slide_range": [1, 2]},
            )

        extract_body = mock_sidecar.call_args[0][3]
        assert "SlidesToJSON(1, 2," in extract_body

    async def test_fine_text_format_omits_layouts_and_locator(self):
        sidecar = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        with patch(
            "aiecs.tools.office_tool.presentation.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/deck.pptx", "pptx", "gs://b/deck.pptx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.presentation.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_presentation(
                source_path="gs://b/deck.pptx",
                format="text",
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "fine"
        assert isinstance(result.get("text"), str)
        assert "slides" not in result
        assert "layouts" not in result
        assert "_locator_note" not in result
        assert "format=structured" in (result.get("_note") or "")

    async def test_missing_source_error(self):
        result = await office_read_presentation()
        assert result.get("isError") is True
