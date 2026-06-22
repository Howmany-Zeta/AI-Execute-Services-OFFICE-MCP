"""Tests for presentation/parser/slides.py."""

import json
from pathlib import Path

from aiecs.tools.office_tool.presentation.parser.slides import (
    apply_slide_range,
    parse_slides_json,
    slides_to_outline,
    slides_to_text,
    word_count_from_slides,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestSlidesParser:
    def test_parse_slides_json_multi_slide(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, layouts = parse_slides_json(raw)
        assert len(slides) == 3
        assert slides[0]["slide_index"] == 0
        assert slides[0]["title"] == "Quarterly Review"
        assert slides[0]["layout"] == "Title Slide"
        assert slides[0]["shapes"][0]["role"] == "title"

    def test_layouts_deduplicated(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        _, layouts = parse_slides_json(raw)
        assert layouts == [
            "Title Slide",
            "Title and Content",
            "Section Header",
            "Two Content",
        ]
        assert len(layouts) == len(set(layouts))

    def test_slide_range_inclusive(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, _ = parse_slides_json(raw)
        filtered = apply_slide_range(slides, (1, 2))
        assert len(filtered) == 2
        assert filtered[0]["slide_index"] == 1

    def test_slides_to_outline(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, _ = parse_slides_json(raw)
        outline = slides_to_outline(slides)
        assert outline[0] == {"slide_index": 0, "title": "Quarterly Review"}

    def test_slides_to_text_separator(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, _ = parse_slides_json(raw)
        text = slides_to_text(slides)
        assert "--- slide 1 ---" in text
        assert "Quarterly Review" in text

    def test_word_count_from_slides(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, _ = parse_slides_json(raw)
        assert word_count_from_slides(slides) > 0
