"""Tests for Word fine sidecar overlay (runs, lists, headers, images)."""

from aiecs.tools.office_tool.word.parser.fine import (
    WORD_TOJSON_EXTRACT_BODY,
    parse_fine_sidecar,
)


def test_extract_body_has_tojson_and_header_variants():
    body = WORD_TOJSON_EXTRACT_BODY
    assert "doc.ToJSON" in body
    assert "GetHeader" in body
    assert '"default"' in body
    assert '"first"' in body
    assert '"even"' in body
    assert "GetAllFootnotes" in body
    assert "GetAllComments" in body
    assert "SetTitlePage" not in body


def test_overlay_attaches_runs_align_list_and_cells():
    raw = {
        "document": {
            "content": [
                {"type": "paragraph", "style": "Heading 1", "content": [{"type": "text", "text": "Title"}]},
                {"type": "paragraph", "style": "Normal", "content": [{"type": "text", "text": "Body"}]},
                {"type": "table", "rows": [["A", "B"]]},
            ]
        },
        "body": [
            {
                "element_index": 0,
                "class": "paragraph",
                "text": "Title",
                "align": "center",
                "outline_level": 0,
                "runs": [{"text": "Title", "bold": True, "font_name": "Calibri", "font_size_pt": 16}],
            },
            {
                "element_index": 1,
                "class": "paragraph",
                "text": "Body",
                "align": "justify",
                "list_type": "bullet",
                "list_level": 0,
                "runs": [{"text": "Body", "italic": True}],
            },
            {
                "element_index": 2,
                "class": "table",
                "rows": [["A", "B"]],
                "cells": [
                    {"row": 0, "col": 0, "text": "A", "align": "left", "runs": [{"text": "A", "bold": True}]},
                    {"row": 0, "col": 1, "text": "B"},
                ],
            },
        ],
        "sections": [{"section_index": 0, "header": [{"variant": "default", "text": "Hdr"}], "footer": []}],
    }
    blocks, sections, warnings, extras = parse_fine_sidecar(raw)
    assert extras["footnotes"] == []
    assert extras["comments"] == []
    assert warnings == []
    assert [b["block_index"] for b in blocks] == [0, 1, 2]
    assert blocks[0]["runs"][0]["run_index"] == 0
    assert blocks[0]["runs"][0]["bold"] is True
    assert blocks[0]["align"] == "center"
    assert blocks[0]["heading_level"] == 1
    assert blocks[1]["align"] == "justify"
    assert blocks[1]["list_type"] == "bullet"
    assert blocks[1]["list_level"] == 0
    assert blocks[2]["cells"][0] == {
        "row": 0,
        "col": 0,
        "text": "A",
        "align": "left",
        "runs": [{"text": "A", "bold": True, "run_index": 0}],
    }
    assert all(b.get("type") != "header" for b in blocks)
    assert sections[0]["header"][0]["variant"] == "default"
    assert sections[0]["header"][0]["text"] == "Hdr"


def test_headers_are_not_blocks_and_first_even_are_present():
    raw = {
        "document": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "Body"}]}]},
        "body": [{"element_index": 0, "class": "paragraph", "text": "Body", "runs": [{"text": "Body"}]}],
        "sections": [{
            "section_index": 0,
            "break_type": "next",
            "different_first_page": True,
            "odd_even_headers": True,
            "columns": {"count": 2},
            "header": [
                {"variant": "default", "text": "Default header", "page_number": {"position": "center", "format": "PAGE"}},
                {"variant": "first", "text": "First header"},
                {"variant": "even", "text": "Even header"},
            ],
            "footer": [{"variant": "default", "text": "1"}],
        }],
    }
    blocks, sections, _, extras = parse_fine_sidecar(raw)
    assert [b["type"] for b in blocks] == ["paragraph"]
    header = sections[0]["header"]
    assert [part["variant"] for part in header] == ["default", "first", "even"]
    assert header[0]["page_number"] == {"position": "center", "format": "PAGE"}
    assert header[0]["page_number"].get("start") is None
    assert "1" not in str(header[0]["page_number"])
    assert header[1]["text"] == "First header"
    assert sections[0]["footer"][0]["text"] == "1"
    assert sections[0]["break_type"] == "next"
    assert sections[0]["different_first_page"] is True
    assert sections[0]["odd_even_headers"] is True
    assert sections[0]["columns"] == {"count": 2}
    assert extras["footnotes"] == []


def test_inline_image_attaches_to_host_paragraph():
    raw = {
        "document": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "See fig"}]}]},
        "body": [{
            "element_index": 0,
            "class": "paragraph",
            "text": "See fig",
            "images": [{"image_index": 0, "alt": "logo", "width_pt": 72, "height_pt": 36}],
        }],
        "sections": [],
    }
    blocks, _, _, _ = parse_fine_sidecar(raw)
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["images"][0]["alt"] == "logo"
    assert blocks[0]["images"][0]["image_index"] == 0


def test_top_level_image_keeps_element_index():
    raw = {
        "document": {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Before"}]},
                {"type": "image", "alt": "photo"},
                {"type": "paragraph", "content": [{"type": "text", "text": "After"}]},
            ]
        },
        "body": [
            {"element_index": 0, "class": "paragraph", "text": "Before"},
            {"element_index": 1, "class": "image", "alt": "photo", "width_pt": 100, "height_pt": 80},
            {"element_index": 2, "class": "paragraph", "text": "After"},
        ],
        "sections": [],
    }
    blocks, _, _, _ = parse_fine_sidecar(raw)
    assert [b["block_index"] for b in blocks] == [0, 1, 2]
    assert blocks[1]["type"] == "image"
    assert blocks[1]["width_pt"] == 100


def test_text_mismatch_skips_style_and_warns():
    raw = {
        "document": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "Alpha"}]}]},
        "body": [{
            "element_index": 0,
            "class": "paragraph",
            "text": "Beta",
            "align": "right",
            "runs": [{"text": "Beta", "bold": True}],
        }],
        "sections": [],
    }
    blocks, _, warnings, _ = parse_fine_sidecar(raw)
    assert "runs" not in blocks[0]
    assert "align" not in blocks[0]
    assert warnings


def test_page_break_textbox_chart_caption_keep_element_index():
    raw = {
        "document": {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Intro"}]},
                {"type": "table", "rows": [["A"]]},
                {"type": "paragraph", "style": "Caption", "content": [{"type": "text", "text": "Table 1"}]},
            ]
        },
        "body": [
            {"element_index": 0, "class": "paragraph", "text": "Intro"},
            {"element_index": 1, "class": "table", "rows": [["A"]]},
            {"element_index": 2, "class": "caption", "text": "Table 1", "style_names": ["Caption"]},
            {"element_index": 3, "class": "page_break", "text": ""},
            {
                "element_index": 4,
                "class": "textbox",
                "text": "Callout",
                "runs": [{"text": "Callout", "italic": True}],
                "x_pt": 10,
                "y_pt": 20,
                "width_pt": 120,
                "height_pt": 40,
            },
            {"element_index": 5, "class": "chart", "chart_type": "bar", "rows": [["1", "2"]]},
        ],
        "sections": [],
    }
    blocks, _, _, extras = parse_fine_sidecar(raw)
    types = {b["block_index"]: b["type"] for b in blocks}
    assert types[3] == "page_break"
    assert types[4] == "textbox"
    assert types[5] == "chart"
    caption = next(b for b in blocks if b["type"] == "caption")
    assert caption["target_block_index"] == 1
    textbox = next(b for b in blocks if b["type"] == "textbox")
    assert textbox["runs"][0]["run_index"] == 0
    assert textbox["x_pt"] == 10
    assert extras["footnotes"] == []


def test_footnotes_and_comments_are_not_blocks():
    raw = {
        "document": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "See note"}]}]},
        "body": [{
            "element_index": 0,
            "class": "paragraph",
            "text": "See note",
            "runs": [{"text": "See note", "footnote_id": "fn1"}],
        }],
        "sections": [],
        "footnotes": [{"footnote_id": "fn1", "text": "A footnote", "runs": [{"text": "A footnote"}]}],
        "comments": [{"comment_id": "c1", "text": "Please check", "quote": "See note"}],
    }
    blocks, _, _, extras = parse_fine_sidecar(raw)
    assert [b["type"] for b in blocks] == ["paragraph"]
    assert extras["footnotes"][0]["footnote_id"] == "fn1"
    assert extras["footnotes"][0]["block_index"] == 0
    assert extras["comments"][0]["comment_id"] == "c1"
    assert extras["comments"][0]["block_index"] == 0
