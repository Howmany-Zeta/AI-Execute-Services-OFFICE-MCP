"""Tests for presentation/parser/slides.py."""

import json
from pathlib import Path

from aiecs.tools.office_tool.presentation.parser.slides import (
    apply_slide_range,
    build_slides_extract_body,
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
        assert slides[0]["shapes"][0]["type"] == "text"

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

    def test_empty_placeholder_and_textbox_keep_original_index(self):
        slides, _ = parse_slides_json({
            "slides": [{
                "slide_index": 0,
                "title": "  Deck  ",
                "layout": "Title Slide",
                "shapes": [
                    {"text": "\x00", "placeholderType": "title"},
                    {"text": "Body", "role": "body"},
                    {"text": "   "},
                    {"text": "", "is_textbox": True},
                ],
            }]
        })
        assert slides[0]["title"] == "Deck"
        shapes = slides[0]["shapes"]
        assert [(s["shape_index"], s["type"], s["text"]) for s in shapes] == [
            (0, "shape", ""),
            (1, "text", "Body"),
            (3, "shape", ""),
        ]
        assert shapes[0]["role"] == "title"
        assert shapes[1]["role"] == "body"

    def test_picture_kept_as_image_and_text_classified(self):
        slides, _ = parse_slides_json({
            "slides": [{
                "layout": "Title Slide",
                "shapes": [
                    {"type": "shape", "placeholder_type": "title", "text": "Quarterly Review"},
                    {"type": "image", "text": ""},
                    {"is_picture": True, "is_textbox": True, "text": "caption"},
                    {"text": "   "},
                ],
            }]
        })
        shapes = slides[0]["shapes"]
        assert [(s["shape_index"], s["type"]) for s in shapes] == [
            (0, "text"),
            (1, "image"),
            (2, "image"),
        ]
        assert shapes[0]["text"] == "Quarterly Review"

    def test_word_count_from_slides(self):
        raw = json.loads((FIXTURES / "slides_tojson_pptx.json").read_text())
        slides, _ = parse_slides_json(raw)
        assert word_count_from_slides(slides) > 0

    def test_build_slides_extract_body_default_range(self):
        body = build_slides_extract_body(0, None)
        assert "SlidesToJSON(0, last," in body
        assert "GetSlidesCount()" in body
        assert "GetAllShapes" in body
        assert "GetNotesPage" in body
        assert "GetBodyShapeText" in body

    def test_build_slides_extract_body_explicit_range(self):
        body = build_slides_extract_body(1, 2)
        assert "SlidesToJSON(1, 2," in body
        assert "GetSlidesCount()" not in body
        assert "GetAllShapes" in body
        assert "collectLayoutShapes" in body

    def test_shape_runs_align_geometry_and_layout_shapes(self):
        from aiecs.tools.office_tool.presentation.parser.slides import normalize_layout_shapes

        slides, layouts = parse_slides_json({
            "layouts": ["Title Slide"],
            "slides": [{
                "slide_index": 0,
                "layout": "Title Slide",
                "shapes": [{
                    "text": "Hello",
                    "placeholder_type": "title",
                    "align": "center",
                    "x_pt": 12,
                    "y_pt": 24,
                    "width_pt": 200,
                    "height_pt": 40,
                    "runs": [
                        {"text": "Hel", "bold": True, "font_name": "Arial"},
                        {"text": "lo", "italic": True},
                    ],
                }],
            }],
            "layout_shapes": [{
                "layout_name": "Title Slide",
                "shapes": [{"text": "Master title", "placeholder_type": "title"}],
            }],
            "layout_shapes_warning": "",
        })
        shape = slides[0]["shapes"][0]
        assert shape["align"] == "center"
        assert shape["x_pt"] == 12
        assert shape["runs"][0]["run_index"] == 0
        assert shape["runs"][0]["bold"] is True
        extras = normalize_layout_shapes({
            "layout_shapes": [{
                "layout_name": "Title Slide",
                "shapes": [{"text": "Master title", "placeholder_type": "title"}],
            }],
        }, layouts)
        assert extras["layout_shapes"][0]["layout_name"] == "Title Slide"
        assert extras["layout_shapes"][0]["shapes"][0]["shape_index"] == 0
