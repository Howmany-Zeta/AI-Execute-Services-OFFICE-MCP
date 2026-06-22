"""Tests for office_read_presentation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.presentation.tools.read import (
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
        assert result.get("_note")

    async def test_missing_source_error(self):
        result = await office_read_presentation()
        assert result.get("isError") is True
