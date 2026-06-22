"""Tests for word/builder/edit.py script generation."""

from aiecs.tools.office_tool.word.builder.edit import build_edit_script
from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation


class TestBuildEditScript:
    def test_set_block_text_uses_block_index_get_element(self):
        ops = [EditOperation(op="set_block_text", block_index=4, text="Updated body")]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(4)" in script
        assert "blockTarget.SetText" in script
        assert 'doc.Search("")' not in script

    def test_delete_block_uses_block_index(self):
        ops = [EditOperation(op="delete_block", block_index=2)]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(2)" in script
        assert "blockTarget.Delete()" in script

    def test_apply_style_uses_block_index(self):
        ops = [EditOperation(op="apply_style", block_index=1, style_name="Heading 2")]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(1)" in script
        assert 'SetStyle("Heading 2")' in script

    def test_match_text_still_uses_search(self):
        ops = [EditOperation(op="set_block_text", match_text="Intro", text="New intro")]
        script = build_edit_script(ops, file_ext="docx")
        assert 'doc.Search("Intro")' in script
        assert "GetElement" not in script

    def test_insert_bullets_after_block_index(self):
        ops = [
            EditOperation(
                op="insert_bullets",
                items=["A", "B"],
                block_index=3,
            )
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.AddElement(4, oBulletPara0)" in script
        assert "doc.AddElement(5, oBulletPara1)" in script

    def test_insert_table_after_heading_path(self):
        ops = [
            EditOperation(
                op="insert_table",
                rows=[["H1", "H2"], ["a", "b"]],
                heading_path=["Chapter 1", "Summary"],
            )
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert 'doc.Search("Summary")' in script
        assert "doc.AddElement(insertIdx + 1, oTable)" in script

    def test_insert_paragraph_after_heading_snippet(self):
        ops = [
            EditOperation(
                op="insert_paragraph",
                text="New line",
                after="Introduction",
            )
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert 'doc.Search("Introduction")' in script
        assert "doc.AddElement(insertIdx + 1, oPara)" in script

    def test_search_replace_subtree_uses_block_text(self):
        ops = [
            EditOperation(
                op="search_replace",
                search_string="foo",
                replace_string="bar",
                scope="subtree",
                block_index=2,
            )
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(2)" in script
        assert "blockTarget.GetText()" in script
        assert 'blockTarget.SetText(_txt.split("foo").join("bar"))' in script
        assert "SearchAndReplace" not in script.split("if (blockTarget)")[0]

    def test_search_replace_document_level(self):
        ops = [
            EditOperation(
                op="search_replace",
                search_string="x",
                replace_string="y",
            )
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert "SearchAndReplace" in script
        assert "blockTarget.GetText()" not in script

    def test_add_page_break_after_block_index(self):
        ops = [EditOperation(op="add_page_break", block_index=1)]
        script = build_edit_script(ops, file_ext="docx")
        assert "AddPageBreak()" in script
        assert "doc.AddElement(2, pageBreakPara)" in script

    def test_insert_section_break_at_end(self):
        ops = [EditOperation(op="insert_section_break")]
        script = build_edit_script(ops, file_ext="docx")
        assert 'AddBreak("section")' in script
        assert "doc.Push(sectionBreakPara)" in script
