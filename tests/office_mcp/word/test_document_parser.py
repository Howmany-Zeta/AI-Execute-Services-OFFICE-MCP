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

ONLYOFFICE_TOJSON = {
    "type": "document",
    "content": [
        {
            "type": "paragraph",
            "style": "Heading 1",
            "content": [{"type": "run", "content": ["Title"]}],
        },
        {
            "type": "paragraph",
            "style": "Normal",
            "content": [{"type": "run", "content": ["Body paragraph."]}],
        },
    ],
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

    def test_onlyoffice_run_string_content(self):
        blocks = parse_document_json(ONLYOFFICE_TOJSON)
        assert blocks[0]["text"] == "Title"
        assert blocks[0]["type"] == "heading1"
        assert blocks[1]["text"] == "Body paragraph."

    def test_blocks_to_text_and_word_count(self):
        blocks = parse_document_json(SAMPLE_TOJSON)
        text = blocks_to_text(blocks)
        assert "Title" in text
        assert word_count_from_blocks(blocks) >= 3

    def test_nul_only_paragraph_omitted(self):
        raw = {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "\x00"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "keep"}]},
            ]
        }
        blocks = parse_document_json(raw)
        assert [b["text"] for b in blocks] == ["keep"]
        assert blocks[0]["block_index"] == 1

    def test_heading_level_4_stays_paragraph_type(self):
        raw = {
            "content": [
                {
                    "type": "paragraph",
                    "style": "Heading 4",
                    "content": [{"type": "text", "text": "Deep"}],
                }
            ]
        }
        blocks = parse_document_json(raw)
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["heading_level"] == 4
        assert blocks[0]["heading_path"] == ["Deep"]
