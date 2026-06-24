"""Tests for office_create_pdf (ADR-017)."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool.pdf.tools.create import office_create_pdf

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_pdf_native_calls_builder_once():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.pdf"},
    ) as mock_run:
        result = await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Hello"}]}],
            output_path="gs://b/out.pdf",
        )
    assert result.get("success") is True
    assert mock_run.call_count == 1
    script = mock_run.call_args[0][0]
    assert 'CreateFile("pdf")' in script


@pytest.mark.asyncio
async def test_create_pdf_native_failure_no_auto_via_docx():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"isError": True, "text": "native failed"},
    ) as mock_run:
        result = await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Hello"}]}],
            output_path="gs://b/out.pdf",
            options={"create_mode": "native"},
        )
    assert mock_run.call_count == 1
    assert "via_docx" in result.get("text", "")


@pytest.mark.asyncio
async def test_create_pdf_via_docx_mode():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_pdf(
            pages=[
                {"blocks": [{"type": "paragraph", "text": "Hi"}]},
                {"blocks": [{"type": "paragraph", "text": "Page two"}]},
            ],
            output_path="gs://b/out.pdf",
            options={"create_mode": "via_docx"},
        )
    script = mock_run.call_args[0][0]
    assert 'CreateFile("docx")' in script
    assert "AddPageBreak" in script
    assert "doc.Push" in script
    assert "doc.AddPage()" not in script


@pytest.mark.asyncio
async def test_create_pdf_page_size_native():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Sized"}]}],
            output_path="gs://b/out.pdf",
            options={"create_mode": "native", "page_size": "A4"},
        )
    script = mock_run.call_args[0][0]
    assert "AddPage(0, 595, 842" in script
    assert "SetPageSize" not in script


@pytest.mark.asyncio
async def test_create_pdf_page_size_via_docx():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Sized"}]}],
            output_path="gs://b/out.pdf",
            options={"create_mode": "via_docx", "page_size": "Letter"},
        )
    script = mock_run.call_args[0][0]
    assert "SetPageSize(12240, 15840" in script
    assert "GetFinalSection()" in script


@pytest.mark.asyncio
async def test_create_pdf_page_size_letter_native():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Sized"}]}],
            output_path="gs://b/out.pdf",
            options={"create_mode": "native", "page_size": "Letter"},
        )
    script = mock_run.call_args[0][0]
    assert "AddPage(0, 612, 792" in script
    assert "SetPageSize" not in script


@pytest.mark.asyncio
async def test_create_pdf_page_size_a4_via_docx():
    with patch(
        "aiecs.tools.office_tool.pdf.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True},
    ) as mock_run:
        await office_create_pdf(
            pages=[{"blocks": [{"type": "paragraph", "text": "Sized"}]}],
            output_path="gs://b/out.pdf",
            options={"create_mode": "via_docx", "page_size": "A4"},
        )
    script = mock_run.call_args[0][0]
    assert "SetPageSize(11906, 16838" in script
    assert "GetFinalSection()" in script
