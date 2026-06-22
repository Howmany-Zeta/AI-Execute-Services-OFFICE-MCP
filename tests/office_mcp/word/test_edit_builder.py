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
