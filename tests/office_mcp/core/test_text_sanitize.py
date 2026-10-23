"""Character-layer hygiene shared by Word and PDF callers."""

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text


def test_strips_nul_and_other_c0_keeps_whitespace():
    assert sanitize_text("A\x00B\x07C") == "ABC"
    assert sanitize_text("keep\t\n\r") == "keep\t\n\r"
    assert has_visible_text("\x00") is False
    assert bool("\x00".strip()) is True


def test_trims_regular_spaces_not_tabs_or_newlines():
    assert sanitize_text("  SCREENER" + (" " * 78)) == "SCREENER"
    assert sanitize_text("\tkept") == "\tkept"
    assert sanitize_text("kept\n") == "kept\n"
    assert sanitize_text("  title  ") == "title"


def test_nbsp_and_ideographic_space_are_regular_spaces():
    assert sanitize_text("森海塞尔\xa0") == "森海塞尔"
    assert sanitize_text("\u3000") == ""
    assert has_visible_text("\u00a0") is False
    assert has_visible_text("\u3000") is False
    assert has_visible_text("\r\n") is False


def test_middle_spaces_stay():
    assert sanitize_text("hello world") == "hello world"
    assert sanitize_text("思想 政治") == "思想 政治"


def test_has_visible_text_false_for_whitespace_only():
    assert has_visible_text("   ") is False
    assert has_visible_text("\t\n") is False
    assert has_visible_text("ok") is True
