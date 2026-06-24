"""Tests for office_merge_pdfs (ADR-018)."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.pdf.tools.merge import office_merge_pdfs

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_merge_pdfs_default_builder():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.merge.resolve_fetch_url",
        new_callable=AsyncMock,
        return_value="https://signed/a.pdf",
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.merge.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/merged.pdf"},
    ) as mock_run:
        result = await office_merge_pdfs(
            source_paths=["gs://b/a.pdf", "gs://b/b.pdf"],
            output_path="gs://b/merged.pdf",
        )
    assert result.get("success") is True
    script = mock_run.call_args[0][0]
    assert "OpenFile" in script


@pytest.mark.asyncio
async def test_merge_pdfs_conversion_engine_explicit():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.merge.resolve_fetch_url",
        new_callable=AsyncMock,
        return_value="https://signed/a.pdf",
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.merge.merge_pdfs_conversion",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/merged.pdf"},
    ) as mock_conv, patch(
        "aiecs.tools.office_tool.pdf.tools.merge.run_builder_script",
        new_callable=AsyncMock,
    ) as mock_builder:
        result = await office_merge_pdfs(
            source_paths=["gs://b/a.pdf", "gs://b/b.pdf"],
            output_path="gs://b/merged.pdf",
            options={"engine": "conversion"},
        )
    assert result.get("success") is True
    mock_conv.assert_called_once()
    mock_builder.assert_not_called()


@pytest.mark.asyncio
async def test_merge_pdfs_rejects_single_source():
    result = await office_merge_pdfs(
        source_paths=["gs://b/a.pdf"],
        output_path="gs://b/merged.pdf",
    )
    assert result.get("isError") is True
    assert "at least 2" in result.get("text", "").lower()


@pytest.mark.asyncio
async def test_merge_pdfs_rejects_non_pdf_output():
    result = await office_merge_pdfs(
        source_paths=["gs://b/a.pdf", "gs://b/b.pdf"],
        output_path="gs://b/merged.docx",
    )
    assert result.get("isError") is True


@pytest.mark.asyncio
async def test_merge_pdfs_rejects_non_pdf_source():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.merge.resolve_fetch_url",
        new_callable=AsyncMock,
        return_value="https://signed/a.docx",
    ), patch(
        "aiecs.tools.office_tool.pdf.tools.merge.run_builder_script",
        new_callable=AsyncMock,
    ) as mock_run:
        result = await office_merge_pdfs(
            source_paths=["gs://b/a.docx", "gs://b/b.pdf"],
            output_path="gs://b/merged.pdf",
        )
    assert result.get("isError") is True
    mock_run.assert_not_called()
