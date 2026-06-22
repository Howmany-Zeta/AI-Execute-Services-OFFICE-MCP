"""Tests for office_edit_word."""

import pytest
from unittest.mock import AsyncMock, patch

from aiecs.tools.office_tool.word.tools.edit import office_edit_word

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_edit_word_delegates_to_run_builder_on_source():
    with patch(
        "aiecs.tools.office_tool.word.tools.edit.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed", "docx", "gs://b/in.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.word.tools.edit.run_builder_on_source",
        new_callable=AsyncMock,
        return_value={"success": True, "output_path": "gs://b/out.docx"},
    ) as mock_run:
        result = await office_edit_word(
            source_path="gs://b/in.docx",
            output_path="gs://b/out.docx",
            operations=[{"op": "search_replace", "search_string": "a", "replace_string": "b"}],
        )
    assert result.get("success") is True
    body = mock_run.call_args[0][2]
    assert "SearchAndReplace" in body
