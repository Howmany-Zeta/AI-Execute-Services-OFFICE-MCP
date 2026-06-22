"""Tests for office_read_word."""

import pytest
from unittest.mock import AsyncMock, patch

from aiecs.tools.office_tool.word.tools.read import office_read_word, TOOL_NAME, TOOL_DEF

pytestmark = pytest.mark.asyncio


class TestReadWordTool:
    def test_tool_exports(self):
        assert TOOL_NAME == "office_read_word"
        assert TOOL_DEF["name"] == "office_read_word"
        assert "[Word]" in TOOL_DEF["description"]

    async def test_fine_read_success(self):
        sidecar = {
            "content": [
                {
                    "type": "paragraph",
                    "style": "Heading 1",
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ]
        }
        with patch(
            "aiecs.tools.office_tool.word.tools.read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.docx", "docx", "gs://b/doc.docx", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.word.tools.read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ):
            result = await office_read_word(source_path="gs://b/doc.docx", format="structured")

        assert result.get("success") is True
        assert result.get("category") == "word"
        assert result.get("blocks") == result.get("units")
        assert len(result.get("units", [])) >= 1

    async def test_missing_source_error(self):
        result = await office_read_word()
        assert result.get("isError") is True
