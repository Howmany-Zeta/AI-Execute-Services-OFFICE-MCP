"""Tests for pdf/builder/edit.py script generation."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.pdf.builder.edit import build_edit_script
from aiecs.tools.office_tool.pdf.schemas.edit_ops import EditOperation


class TestBuildEditScript:
    def test_add_paragraph_with_align(self):
        op = EditOperation(op="add_paragraph", page_index=0, text="Title", align="center")
        script = build_edit_script([op], file_ext="pdf")
        assert "SetJc('center')" in script
        assert "Title" in script

    def test_set_page_text_replaces_blocks(self):
        op = EditOperation(
            op="set_page_text",
            page_index=1,
            blocks=[{"type": "paragraph", "text": "Fresh content", "align": "right"}],
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "RemoveElement(0)" in script
        assert "SetJc('right')" in script
        assert "Fresh content" in script

    def test_add_page_with_blocks(self):
        op = EditOperation(
            op="add_page",
            after_index=0,
            blocks=[{"type": "paragraph", "text": "New page body"}],
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "doc.AddPage(0)" in script
        assert "GetElementsCount() - 1" in script
        assert "New page body" in script

    def test_delete_page(self):
        op = EditOperation(op="delete_page", page_index=1)
        script = build_edit_script([op], file_ext="pdf")
        assert "doc.RemoveElement(1)" in script

    def test_rotate_page(self):
        op = EditOperation(op="rotate_page", page_index=0, degrees=90)
        script = build_edit_script([op], file_ext="pdf")
        assert "page.Rotate(90)" in script

    def test_add_annotation(self):
        op = EditOperation(
            op="add_annotation",
            page_index=0,
            kind="freetext",
            text="Note",
            rect={"x": 10, "y": 20, "width": 80, "height": 30},
        )
        script = build_edit_script([op], file_ext="pdf")
        assert 'AddAnnotation("freetext"' in script
        assert "Note" in script

    def test_set_page_text_requires_blocks(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_page_text", page_index=0)

    def test_set_page_text_emits_table_blocks(self):
        op = EditOperation(
            op="set_page_text",
            page_index=0,
            blocks=[{"type": "table", "rows": [["A", "B"]]}],
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "Api.CreateTable" in script
        assert "page.Push(oTable)" in script
