"""Fixtures for Word structured Builder normalization."""

from aiecs.tools.office_tool.word.parser.structured import (
    STRUCTURED_WORD_EXTRACT_BODY,
    normalize_word_structured,
)


def _para(**kwargs):
    item = {"class": "paragraph", "style_names": [], "page_breaks": 0, "text": "", "runs": []}
    item.update(kwargs)
    return item


def _section(body, **kwargs):
    section = {"break_type": "continuous", "header": [], "footer": [], "body": body}
    section.update(kwargs)
    return section


def test_extract_script_walks_objects_not_tojson():
    body = STRUCTURED_WORD_EXTRACT_BODY
    assert "GetClassType" in body
    assert "GetHeader" in body
    assert "GetFooter" in body
    assert '"default"' in body
    assert "GetAllFootnotes" in body
    assert "doc.ToJSON" not in body


def test_no_page_breaks_all_page_one():
    raw = {"sections": [_section([
        _para(text="A", style_names=["Normal"]),
        _para(text="B", style_names=["Normal"]),
        {"class": "table", "rows": [["1", "2"]], "page_breaks": 0},
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert [el["page"] for el in elements] == [1, 1, 1]


def test_page_break_keeps_element_page_and_adds_k():
    raw = {"sections": [_section([
        _para(text="before", page_breaks="0"),
        _para(text="has two breaks", page_breaks=2),
        _para(text="after"),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["page"] == 1
    assert elements[1]["page"] == 1
    assert elements[1]["text"] == "has two breaks"
    assert elements[2]["page"] == 3
    assert len(elements) == 3


def test_next_page_section_increments_then_writes_header():
    raw = {
        "sections": [
            _section([_para(text="sec1")], header=[{"text": "H1", "runs": [{"text": "H1"}]}], footer=[{"text": "F1"}]),
            _section(
                [_para(text="sec2 body")],
                break_type="nextPage",
                header=[{"text": "H2"}],
                footer=[{"text": "F2"}],
            ),
        ]
    }
    elements = normalize_word_structured(raw)["elements"]
    types = [(el["type"], el["page"], el["text"]) for el in elements]
    assert types == [
        ("header", 1, "H1"),
        ("footer", 1, "F1"),
        ("paragraph", 1, "sec1"),
        ("header", 2, "H2"),
        ("footer", 2, "F2"),
        ("paragraph", 2, "sec2 body"),
    ]


def test_continuous_section_keeps_page_and_still_inserts_header():
    raw = {
        "sections": [
            _section([_para(text="a")]),
            _section([_para(text="b")], break_type="continuous", header=[{"text": "cont-h"}]),
        ]
    }
    elements = normalize_word_structured(raw)["elements"]
    assert elements[1]["type"] == "header"
    assert elements[1]["page"] == 1
    assert elements[2]["text"] == "b"
    assert elements[2]["page"] == 1


def test_odd_even_section_breaks_increment():
    raw = {
        "sections": [
            _section([_para(text="one")]),
            _section([_para(text="odd")], break_type="oddPage"),
            _section([_para(text="even")], break_type="evenPage"),
        ]
    }
    pages = [el["page"] for el in normalize_word_structured(raw)["elements"]]
    assert pages == [1, 2, 3]


def test_style_match_trim_and_case():
    raw = {"sections": [_section([
        _para(text="h", style_names=[" heading 1 "]),
        _para(text="H", style_names=["Heading 1"]),
        _para(text="toc", style_names=["TOC 1"]),
        _para(text="ml", style_names=[" 目录 1 "]),
        _para(text="cap", style_names=["Caption"]),
        _para(text="zh-cap", style_names=["题注"]),
        _para(text="q", style_names=["Quote"]),
        _para(text="iq", style_names=["Intense Quote"]),
        _para(text="zh-q", style_names=["引用"]),
        _para(text="unknown", style_names=["MyFancyStyle"]),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["type"] == "heading" and elements[0]["level"] == 1
    assert elements[1]["type"] == "heading" and elements[1]["level"] == 1
    assert elements[2]["type"] == "toc"
    assert elements[3]["type"] == "toc"
    assert elements[4]["type"] == "caption"
    assert elements[5]["type"] == "caption"
    assert elements[6]["type"] == "quote"
    assert elements[7]["type"] == "quote"
    assert elements[8]["type"] == "quote"
    assert elements[9]["type"] == "paragraph"


def test_chapter_keeps_type_and_optional_level():
    raw = {"sections": [_section([
        _para(text="ch-ol", style_names=["Chapter"], outline_level=0),
        _para(text="ch-zh", style_names=["章标题"]),
        _para(text="not-ch", style_names=["ChapterTitle"]),
        _para(text="ol0", outline_level=0, style_names=["Normal"]),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["type"] == "chapter"
    assert elements[0]["level"] == 1
    assert elements[1]["type"] == "chapter"
    assert "level" not in elements[1]
    assert elements[2]["type"] == "paragraph"
    assert elements[3]["type"] == "heading"
    assert elements[3]["level"] == 1


def test_heading_from_style_when_no_outline():
    raw = {"sections": [_section([
        _para(text="en", style_names=["Heading 3"]),
        _para(text="zh", style_names=["标题 2"]),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0] == {"page": 1, "type": "heading", "level": 3, "text": "en"}
    assert elements[1]["type"] == "heading" and elements[1]["level"] == 2


def test_list_only_when_not_higher_type():
    raw = {"sections": [_section([
        _para(text="quoted list", style_names=["Quote"], has_numbering=True, list_level=0),
        _para(text="item", has_numbering=True, list_level=1),
        _para(text="bullet", has_bullets=True),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["type"] == "quote"
    assert "level" not in elements[0]
    assert elements[1]["type"] == "list"
    assert elements[1]["level"] == 2
    assert elements[2]["type"] == "list"
    assert "level" not in elements[2]


def test_word_shapes_do_not_become_elements():
    raw = {"sections": [_section([
        _para(text="before"),
        {"class": "shape", "text": "shape text", "page_breaks": 0},
        {"class": "drawing", "text": "textbox text"},
        _para(text="after"),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert [el["text"] for el in elements] == ["before", "after"]
    assert all("shape text" not in el.get("text", "") for el in elements)


def test_footnotes_appended_once_after_body():
    raw = {
        "sections": [_section([
            _para(text="body"),
            _para(text="more", page_breaks=1),
        ])],
        "footnotes": [
            {"text": "note a", "ref_page": 1},
            {"text": "note b"},
        ],
    }
    elements = normalize_word_structured(raw)["elements"]
    assert [el["type"] for el in elements] == ["paragraph", "paragraph", "footnote", "footnote"]
    assert elements[2]["page"] == 1
    assert elements[3]["page"] == 1
    assert elements[3]["text"] == "note b"


def test_runs_keep_explicit_false_and_highlight_none():
    raw = {"sections": [_section([_para(
        text="styled",
        align="justify",
        runs=[{
            "text": "styled",
            "bold": True,
            "italic": False,
            "underline": False,
            "strike": False,
            "highlight": "none",
            "font_name": "Calibri",
            "font_size_pt": 12,
            "font_color": "#112233",
        }],
    )])]}
    run = normalize_word_structured(raw)["elements"][0]["runs"][0]
    assert run["underline"] is False
    assert run["strike"] is False
    assert run["highlight"] == "none"
    assert run["font_color"] == "#112233"
    assert "align" not in normalize_word_structured(raw)["elements"][0]


def test_align_only_left_center_right():
    raw = {"sections": [_section([
        _para(text="L", align="left"),
        _para(text="C", align="CENTER"),
        _para(text="J", align="both"),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["align"] == "left"
    assert elements[1]["align"] == "center"
    assert "align" not in elements[2]


def test_table_cells_are_not_headings():
    raw = {"sections": [_section([{
        "class": "table",
        "rows": [["Heading 1", "章标题"], ["x", "y"]],
        "page_breaks": 0,
    }])]}
    elements = normalize_word_structured(raw)["elements"]
    assert len(elements) == 1
    assert elements[0]["type"] == "table"
    assert elements[0]["rows"][0][0] == "Heading 1"
    assert "text" not in elements[0]


def test_empty_default_header_omitted_first_even_never_present():
    raw = {"sections": [_section(
        [_para(text="body")],
        header=[{"text": "  "}, {"text": "keep"}],
        footer=[],
    )]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["type"] == "header"
    assert elements[0]["text"] == "keep"
    assert all(el["type"] != "footer" for el in elements)


def test_internal_or_display_style_name_hits():
    raw = {"sections": [_section([
        _para(text="by-id", style_id="Heading 1"),
        _para(text="by-display", style_display=" 章标题 "),
    ])]}
    elements = normalize_word_structured(raw)["elements"]
    assert elements[0]["type"] == "heading"
    assert elements[1]["type"] == "chapter"
