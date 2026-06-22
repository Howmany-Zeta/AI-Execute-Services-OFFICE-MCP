"""Tests for office_create_word."""

import pytest
from unittest.mock import AsyncMock, patch

from aiecs.tools.office_tool.word.tools.create import office_create_word

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_create_word_calls_builder():
    with patch(
        "aiecs.tools.office_tool.word.tools.create.run_builder_script",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.docx"},
    ) as mock_run:
        result = await office_create_word(
            sections=[{"type": "paragraph", "text": "Hello"}],
            output_path="gs://b/out.docx",
        )
    assert result.get("success") is True
    mock_run.assert_called_once()
    script = mock_run.call_args[0][0]
    assert "CreateFile" in script
    assert "Hello" in script


def test_build_create_script_title_and_page_size():
    from aiecs.tools.office_tool.word.builder.create import build_create_script
    from aiecs.tools.office_tool.word.schemas.section_spec import SectionSpec, WordCreateOptions

    script = build_create_script(
        [SectionSpec(type="paragraph", text="Hi")],
        output_ext="docx",
        options=WordCreateOptions(title="Report Title", page_size="Letter"),
    )
    assert 'SetTitle("Report Title")' in script
    assert "SetPageSize(12240, 15840" in script
