"""Tests for office_edit_pdf."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.pdf.tools.edit import office_edit_pdf

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_edit_pdf_add_paragraph():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pdf"},
    ) as mock_run:
        result = await office_edit_pdf(
            source_path="gs://b/doc.pdf",
            output_path="gs://b/out.pdf",
            operations=[{"op": "add_paragraph", "page_index": 0, "text": "New text"}],
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "GetDocument" in body
    assert "New text" in body


@pytest.mark.asyncio
async def test_edit_pdf_rejects_non_pdf_source():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.docx", "docx", "gs://b/doc.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
    ) as mock_run:
        result = await office_edit_pdf(
            source_path="gs://b/doc.docx",
            output_path="gs://b/out.pdf",
            operations=[{"op": "add_paragraph", "page_index": 0, "text": "New text"}],
        )
    assert result.get("isError") is True
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_edit_pdf_rejects_non_pdf_output():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
    ) as mock_run:
        result = await office_edit_pdf(
            source_path="gs://b/doc.pdf",
            output_path="gs://b/out.docx",
            operations=[{"op": "add_paragraph", "page_index": 0, "text": "New text"}],
        )
    assert result.get("isError") is True
    mock_run.assert_not_called()
