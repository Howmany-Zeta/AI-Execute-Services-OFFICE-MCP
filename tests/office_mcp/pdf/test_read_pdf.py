"""Tests for office_read_pdf."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.pdf.tools.read import TOOL_DEF, TOOL_NAME, office_read_pdf

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"


class TestReadPdfTool:
    def test_tool_exports(self):
        assert TOOL_NAME == "office_read_pdf"
        assert "[PDF]" in TOOL_DEF["description"]

    async def test_fine_read_success(self):
        sidecar = json.loads((FIXTURES / "document_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_pdf(source_path="gs://b/doc.pdf", format="structured")

        assert result.get("success") is True
        assert result.get("category") == "pdf"
        assert result.get("pages") == result.get("units")
        assert result.get("page_count") == 2

    async def test_read_pdf_missing_source(self):
        result = await office_read_pdf()
        assert result.get("isError") is True
        assert "source" in result.get("text", "").lower()

    async def test_fine_read_strips_annotations_by_default(self):
        sidecar = json.loads((FIXTURES / "document_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_pdf(source_path="gs://b/doc.pdf", format="structured")

        assert result.get("success") is True
        page0 = result["pages"][0]
        assert "annotations" not in page0

    async def test_fine_read_include_annotations(self):
        sidecar = json.loads((FIXTURES / "document_sidecar.json").read_text())
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"include_annotations": True},
            )

        assert result.get("success") is True
        assert result["pages"][0]["annotations"][0]["kind"] == "highlight"

    async def test_coarse_read_pages(self):
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=("Page1\fPage2", None),
        ):
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"read_mode": "coarse"},
            )

        assert result.get("success") is True
        assert result.get("read_mode") == "coarse"
        assert result.get("page_count") == 2

    async def test_fine_read_notes_missing_widgets_api(self):
        sidecar = {
            "widgets_api_available": False,
            "pages": [{"page_index": 0, "blocks": [{"block_index": 0, "type": "paragraph", "text": "Hi"}]}],
        }
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"include_form_fields": True},
            )

        assert result.get("success") is True
        assert "GetAllWidgets" in result.get("_note", "")
