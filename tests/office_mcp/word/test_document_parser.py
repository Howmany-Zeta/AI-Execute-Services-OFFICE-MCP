"""Tests for word/parser/document.py."""

import json

import pytest

from aiecs.tools.office_tool.word.parser.document import (
    blocks_to_outline,
    blocks_to_text,
    parse_document_json,
    word_count_from_blocks,
)

SAMPLE_TOJSON = {
    "content": [
        {
            "type": "paragraph",
            "style": "Heading 1",
            "content": [{"type": "text", "text": "Title"}],
        },
        {
            "type": "paragraph",
            "style": "Normal",
            "content": [{"type": "text", "text": "Body paragraph."}],
        },
        {
            "type": "table",
            "rows": [["A", "B"], ["1", "2"]],
        },
    ]
}


class TestParseDocumentJson:
    def test_headings_and_paragraph(self):
        blocks = parse_document_json(SAMPLE_TOJSON)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "heading1"
        assert blocks[0]["text"] == "Title"
        assert blocks[0]["heading_path"] == ["Title"]
        assert blocks[1]["type"] == "paragraph"

    def test_table_block(self):
        blocks = parse_document_json(SAMPLE_TOJSON)
        table = blocks[2]
        assert table["type"] == "table"
        assert table["row_count"] == 2
        assert table["col_count"] == 2

    def test_from_json_string(self):
        blocks = parse_document_json(json.dumps(SAMPLE_TOJSON))
        assert len(blocks) == 3

    def test_malformed_empty(self):
        assert parse_document_json({}) == []

    def test_blocks_to_outline(self):
        blocks = parse_document_json(SAMPLE_TOJSON)
        outline = blocks_to_outline(blocks)
        assert len(outline) == 1
        assert outline[0]["type"] == "heading1"

    def test_blocks_to_text_and_word_count(self):
        blocks = parse_document_json(SAMPLE_TOJSON)
        text = blocks_to_text(blocks)
        assert "Title" in text
        assert word_count_from_blocks(blocks) >= 3
