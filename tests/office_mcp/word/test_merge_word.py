"""Tests for office_merge_word SaveFile extension (W3)."""

from aiecs.tools.office_tool.word.builder.merge import build_merge_script


def test_odt_output_ext_in_script():
    script = build_merge_script(
        ["https://u1"],
        ["docx"],
        output_path="gs://bucket/merged.odt",
        add_page_break=False,
        add_toc=False,
    )
    assert 'builder.CreateFile("odt")' in script
    assert 'builder.SaveFile("odt", "output.odt")' in script
