"""Fixtures for presentation structured Builder normalization."""

import pytest

from aiecs.tools.office_tool.presentation.parser.structured import (
    STRUCTURED_PRESENTATION_EXTRACT_BODY,
    PresentationStructuredError,
    emu_to_pt,
    flatten_shapes,
    map_line_dash,
    normalize_presentation_structured,
    shape_kind,
)


def _shape(**kwargs):
    shape = {
        "x_emu": 12700,
        "y_emu": 25400,
        "width_emu": 38100,
        "height_emu": 50800,
        "text": "",
        "style": {},
    }
    shape.update(kwargs)
    return shape


def _slide(shapes, **kwargs):
    slide = {"slide_index": 1, "width_emu": 12192000, "height_emu": 6858000, "shapes": shapes}
    slide.update(kwargs)
    return slide


def test_extract_script_uses_getallshapes_not_slidestojson():
    body = STRUCTURED_PRESENTATION_EXTRACT_BODY
    assert "GetAllShapes" in body
    assert "GetSlideByIndex" in body
    assert "SlidesToJSON" not in body


def test_placeholder_mapping_and_empty_filters():
    raw = {"slides": [_slide([
        _shape(placeholder_type="title", text=""),
        _shape(placeholder_type="ctrTitle", text="Centered"),
        _shape(placeholder_type="hdr", text=""),
        _shape(placeholder_type="ftr", text="footer"),
        _shape(placeholder_type="dt", text=""),
        _shape(placeholder_type="sldNum", text="2"),
        _shape(placeholder_type="subTitle", text=""),
        _shape(is_textbox=True, text=""),
        _shape(is_picture=True, text=""),
        _shape(is_connector=True, text=""),
        _shape(text="body shape"),
    ])]}
    result = normalize_presentation_structured(raw)
    types = [(el["type"], el.get("level"), el["text"]) for el in result["elements"]]
    assert types == [
        ("heading", 1, ""),
        ("heading", 1, "Centered"),
        ("header", None, ""),
        ("footer", None, "footer"),
        ("footer", None, ""),
        ("footer", None, "2"),
        ("paragraph", None, "body shape"),
    ]
    kinds = [s["kind"] for s in result["slides"][0]["shapes"]]
    assert "textbox" in kinds
    assert "picture" in kinds
    assert "connector" in kinds
    assert all(el["slide"] == el["slide_index"] == 1 for el in result["elements"])


def test_kind_precedence_picture_and_group_beat_textbox():
    assert shape_kind(_shape(is_picture=True, is_textbox=True)) == "picture"
    assert shape_kind(_shape(unexpanded_group=True, is_textbox=True)) == "group"
    assert shape_kind(_shape(is_textbox=True, text="")) == "textbox"
    assert shape_kind(_shape(text="can type here")) == "shape"
    assert shape_kind(_shape(is_chart=True, is_textbox=True)) == "other"


def test_group_flatten_parent_not_numbered():
    raw = {"slides": [_slide([
        {
            "is_group": True,
            "children": [
                _shape(text="child-a"),
                {
                    "is_group": True,
                    "children": [_shape(text="child-b")],
                },
            ],
            "x_emu": 0,
            "y_emu": 0,
            "width_emu": 100,
            "height_emu": 100,
        },
        _shape(unexpanded_group=True, text="kept\ngroup", x_emu=12700, y_emu=12700, width_emu=12700, height_emu=12700),
    ])]}
    result = normalize_presentation_structured(raw)
    ids = [s["shape_id"] for s in result["slides"][0]["shapes"]]
    assert ids == ["s1-1", "s1-2", "s1-3"]
    assert result["slides"][0]["shapes"][0]["text"] == "child-a"
    assert result["slides"][0]["shapes"][1]["text"] == "child-b"
    assert result["slides"][0]["shapes"][2]["kind"] == "group"
    assert result["slides"][0]["shapes"][2]["text"] == "kept\ngroup"


def test_flatten_helper_skips_expanded_parent():
    tree = [{"is_group": True, "children": [{"text": "a"}, {"text": "b"}]}]
    flat = flatten_shapes(tree)
    assert [n["text"] for n in flat] == ["a", "b"]


def test_emu_divided_by_12700():
    raw = {"slides": [_slide([_shape(
        x_emu=12700,
        y_emu=25400,
        width_emu=38100,
        height_emu=50800,
        style={"line_width_emu": 12700, "line_dash_raw": "solid", "fill": "none"},
    )], width_emu=12192000, height_emu=6858000)]}
    result = normalize_presentation_structured(raw)
    slide = result["slides"][0]
    shape = slide["shapes"][0]
    assert slide["width_pt"] == pytest.approx(960.0)
    assert slide["height_pt"] == pytest.approx(540.0)
    assert shape["x"] == pytest.approx(1.0)
    assert shape["y"] == pytest.approx(2.0)
    assert shape["width"] == pytest.approx(3.0)
    assert shape["height"] == pytest.approx(4.0)
    assert shape["style"]["line_width_pt"] == pytest.approx(1.0)
    assert shape["x"] != 12700
    assert emu_to_pt(12700) == 1.0


def test_missing_shape_coord_is_error_without_payload():
    raw = {"slides": [_slide([_shape(x_emu=None)])]}
    with pytest.raises(PresentationStructuredError):
        normalize_presentation_structured(raw)


def test_missing_canvas_is_error_without_payload():
    raw = {"slides": [_slide([_shape()], width_emu=None)]}
    with pytest.raises(PresentationStructuredError):
        normalize_presentation_structured(raw)


def test_line_dash_mapping():
    assert map_line_dash("solid") == "solid"
    assert map_line_dash("dash") == "dash"
    assert map_line_dash("sysDash") == "dash"
    assert map_line_dash("dot") == "dash"
    assert map_line_dash("dashDot") == "dash"
    assert map_line_dash("none") == "none"
    assert map_line_dash("sysDashDotDot") is None


def test_style_keeps_explicit_false_and_omits_bad_align():
    raw = {"slides": [_slide([_shape(
        text="t",
        style={
            "bold": False,
            "italic": True,
            "align": "justify",
            "line_dash_raw": "dashDot",
            "fill": "none",
            "line_color": "none",
        },
    )])]}
    style = normalize_presentation_structured(raw)["slides"][0]["shapes"][0]["style"]
    assert style["bold"] is False
    assert style["italic"] is True
    assert "align" not in style
    assert style["line_dash"] == "dash"
    assert style["fill"] == "none"
    assert style["line_color"] == "none"
