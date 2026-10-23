"""Unit tests for the office_read_document Markdown projector."""

from aiecs.tools.office_tool.core.read_markdown import (
    assemble_markdown,
    markdown_to_plain,
    sheet_pages,
    truncate_output,
    word_elements_to_pages,
)
from aiecs.tools.office_tool.core.structured_read import layout_to_md_elements
from aiecs.tools.office_tool.word.parser.structured import normalize_word_structured


def test_word_outline_heading_list_and_table_in_one_document():
    raw = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [
                {"class": "paragraph", "outline_level": 0, "text": "Quarterly Report", "page_breaks": 0},
                {"class": "paragraph", "has_numbering": True, "text": "Ship the reader", "page_breaks": 0},
                {"class": "table", "rows": [["ColA", "ColB"], ["1", "2"]], "page_breaks": 0},
            ],
        }],
        "footnotes": [],
    }
    elements = normalize_word_structured(raw)["elements"]
    pages = word_elements_to_pages(elements)
    md = assemble_markdown(pages)
    assert "[Page 1]" in md
    assert "# Quarterly Report" in md
    assert "- Ship the reader" in md
    assert "| ColA | ColB |" in md
    assert "| --- | --- |" in md
    assert "block_index" not in md
    assert "shape_id" not in md


def test_empty_paragraphs_omitted_page_gaps_kept():
    elements = [
        {"type": "paragraph", "page": 1, "text": "keep"},
        {"type": "paragraph", "page": 1, "text": "   "},
        {"type": "paragraph", "page": 3, "text": "later"},
    ]
    md = assemble_markdown(word_elements_to_pages(elements))
    assert md.count("[Page 1]") == 1
    assert "[Page 2]" not in md
    assert "[Page 3]" in md
    assert "keep" in md
    assert "later" in md


def test_header_footer_footnote_toc_caption_textbox_rules():
    elements = [
        {"type": "header", "page": 1, "text": "Acme Header"},
        {"type": "paragraph", "page": 1, "text": "Body one"},
        {"type": "toc", "page": 1, "text": "Contents"},
        {"type": "caption", "page": 1, "text": "Figure 1"},
        {"type": "textbox", "page": 1, "text": "Callout text"},
        {"type": "textbox", "page": 1, "text": ""},
        {"type": "footer", "page": 1, "text": "page footer"},
        {"type": "footnote", "page": 1, "text": "a note"},
        {"type": "header", "page": 2, "text": "Acme Header"},
        {"type": "paragraph", "page": 2, "text": "Body two"},
        {"type": "footer", "page": 2, "text": "page footer"},
    ]
    md = assemble_markdown(word_elements_to_pages(elements))
    assert md.count("Acme Header") == 1
    assert md.count("page footer") == 1
    assert md.count("a note") == 1
    assert md.count("Contents") == 1
    assert md.count("Figure 1") == 1
    assert "Callout text" in md
    assert md.index("Acme Header") < md.index("Body one")
    assert md.index("Body one") < md.index("a note")
    assert "Body two" in md


def test_excel_three_sheets_are_three_pages():
    pages = sheet_pages([
        {"name": "Sheet1", "rows": [["colA", "colB"], [1, 2]]},
        {"name": "Sheet2", "rows": [["x"], ["y"]]},
        {"name": "Sheet3", "rows": [["z"]]},
    ])
    md = assemble_markdown(pages)
    assert md.count("[Page ") == 3
    assert "<!-- sheet: Sheet1 -->" in md
    assert "<!-- sheet: Sheet2 -->" in md
    assert "<!-- sheet: Sheet3 -->" in md
    assert "colA,colB" in md


def test_dai_with_pagestart_writes_markers():
    elements, has_start = layout_to_md_elements({
        "documentLayout": {"blocks": [{
            "pageSpan": {"pageStart": 2},
            "textBlock": {"type": "paragraph", "text": "scanned body"},
        }]}
    })
    assert has_start is True
    pages = word_elements_to_pages(elements)
    md = assemble_markdown(pages)
    assert "[Page 2]" in md
    assert "scanned body" in md


def test_dai_without_pagestart_omits_markers():
    elements, has_start = layout_to_md_elements({
        "documentLayout": {"blocks": [{
            "textBlock": {"type": "paragraph", "text": "no page span"},
        }]}
    })
    assert has_start is False
    pages = []
    from aiecs.tools.office_tool.core.read_markdown import MdPage, element_to_block
    blocks = [element_to_block(el) for el in elements]
    pages.append(MdPage(page=None, blocks=[b for b in blocks if b], show_marker=False))
    md = assemble_markdown(pages)
    assert "[Page " not in md
    assert "no page span" in md


def test_plain_strips_markers():
    md = "[Page 1]\n# Title\n\n- item\n"
    plain = markdown_to_plain(md)
    assert "[Page" not in plain
    assert "#" not in plain
    assert "Title" in plain
    assert "item" in plain


def test_output_truncate():
    text, truncated = truncate_output("abcdef", 3)
    assert truncated is True
    assert len(text.encode("utf-8")) <= 3
