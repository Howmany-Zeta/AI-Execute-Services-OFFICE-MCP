"""Tests for office_read_pdf."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from aiecs.clients.documentai_client import ONLINE_MAX_BYTES, DocumentAIOnlineLimitError
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
        assert result.get("bookmarks") == []
        assert result["pages"][0]["degrees"] == 0

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

    async def test_document_ai_online_success(self):
        layout = {"documentLayout": {"blocks": [{"pageSpan": {"pageStart": 1, "pageEnd": 1}, "textBlock": {"text": "Hi", "type": "paragraph"}}]}}
        client = AsyncMock()
        client.process_pdf_online = AsyncMock(return_value=layout)
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.stat_object_size",
            new_callable=AsyncMock,
            return_value=100,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.download_object_bytes",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.get_documentai_client",
            return_value=client,
        ), patch(
            "aiecs.config.get_documentai_config",
        ) as cfg:
            cfg.return_value.is_configured.return_value = True
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"engine": "document_ai"},
            )
        assert result.get("success") is True
        assert result.get("read_mode") == "layout"
        assert result.get("parse_engine") == "document_ai"
        assert client.process_pdf_online.await_count == 1

    async def test_document_ai_oversize_skips_dai_uses_builder(self):
        client = AsyncMock()
        sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": "oversize-builder"}]}]}
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.stat_object_size",
            new_callable=AsyncMock,
            return_value=ONLINE_MAX_BYTES + 1,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.online_max_bytes",
            return_value=ONLINE_MAX_BYTES,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.get_documentai_client",
            return_value=client,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.process_pdf_batch",
            new_callable=AsyncMock,
        ) as batch, patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ), patch(
            "aiecs.config.get_documentai_config",
        ) as cfg:
            cfg.return_value.is_configured.return_value = True
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"engine": "document_ai"},
            )
        assert result.get("isError") is not True
        assert result.get("read_mode") == "fine"
        assert result.get("conversion_output_type") == "builder_json"
        assert client.process_pdf_online.await_count == 0
        assert batch.await_count == 0

    async def test_document_ai_online_limit_uses_batch(self):
        layout = {"documentLayout": {"blocks": [{"pageSpan": {"pageStart": 1, "pageEnd": 1}, "textBlock": {"text": "batch-hi", "type": "paragraph"}}]}}
        client = AsyncMock()
        client.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("30 pages"))
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.stat_object_size",
            new_callable=AsyncMock,
            return_value=100,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.download_object_bytes",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.get_documentai_client",
            return_value=client,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.process_pdf_batch",
            new_callable=AsyncMock,
            return_value=layout,
        ) as batch, patch(
            "aiecs.config.get_documentai_config",
        ) as cfg:
            cfg.return_value.is_configured.return_value = True
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"engine": "document_ai"},
            )
        assert result.get("success") is True
        assert result.get("document_ai_mode") == "batch"
        assert batch.await_count == 1

    async def test_document_ai_batch_fail_uses_builder(self):
        sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": "builder-hi"}]}]}
        client = AsyncMock()
        client.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("30 pages"))
        with patch(
            "aiecs.tools.office_tool.pdf.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.stat_object_size",
            new_callable=AsyncMock,
            return_value=100,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.download_object_bytes",
            new_callable=AsyncMock,
            return_value=b"%PDF-1.4 fake",
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.get_documentai_client",
            return_value=client,
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.process_pdf_batch",
            new_callable=AsyncMock,
            side_effect=RuntimeError("batch failed"),
        ), patch(
            "aiecs.tools.office_tool.pdf.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ), patch(
            "aiecs.config.get_documentai_config",
        ) as cfg:
            cfg.return_value.is_configured.return_value = True
            result = await office_read_pdf(
                source_path="gs://b/doc.pdf",
                format="structured",
                options={"engine": "document_ai"},
            )
        assert result.get("isError") is not True
        assert result.get("read_mode") == "fine"
        assert result.get("conversion_output_type") == "builder_json"
