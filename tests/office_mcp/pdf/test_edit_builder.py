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
        assert "doc.AddPage(insertAt)" in script
        assert "var insertAt = 1;" in script
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
        assert "CreateFreeTextAnnot" in script
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
        assert "_officePdfPush(page, oTable)" in script

    def test_add_paragraph_emits_style_fields(self):
        op = EditOperation(
            op="add_paragraph",
            page_index=0,
            text="Styled",
            align="justify",
            bold=True,
            font_name="Calibri",
            font_size_pt=14,
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "SetJc('both')" in script
        assert "SetBold(true)" in script
        assert 'SetFontFamily("Calibri")' in script
        assert "SetFontSize(14.0)" in script

    def test_set_block_text_updates_in_place(self):
        op = EditOperation(op="set_block_text", page_index=0, block_index=2, text="Rewritten")
        script = build_edit_script([op], file_ext="pdf")
        assert "_officePdfBlock(page, 2)" in script
        assert "SetText" in script
        assert "RemoveElement" not in script.split("_officePdfBlock(page, 2)", 1)[1]

    def test_set_block_text_updates_table_rows(self):
        op = EditOperation(
            op="set_block_text",
            page_index=1,
            block_index=0,
            rows=[["A", "B"]],
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "GetCell(0, 0)" in script
        assert "SetText" in script
        assert "Api.CreateTable" not in script

    def test_set_cell_text(self):
        op = EditOperation(
            op="set_cell_text",
            page_index=0,
            block_index=1,
            row=2,
            col=3,
            text="Cell",
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "_officePdfSetCell(tableEl, 2, 3" in script
        assert "Cell" in script

    def test_set_paragraph_format_on_cell(self):
        op = EditOperation(
            op="set_paragraph_format",
            page_index=0,
            block_index=1,
            row=0,
            col=1,
            align="center",
            bold=True,
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "GetCell(0, 1)" in script
        assert "SetJc('center')" in script
        assert "SetBold(true)" in script

    def test_replace_image_uses_url_not_media_path(self):
        op = EditOperation(
            op="replace_image",
            page_index=0,
            image_index=0,
            url="https://example.com/logo.png",
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "Api.CreateImage" in script
        assert "https://example.com/logo.png" in script
        assert "GetAllDrawings" in script
        assert "media/" not in script

    def test_set_and_delete_bookmark(self):
        set_op = EditOperation(
            op="set_bookmark",
            bookmark_id="Intro",
            text="Hello",
            page_index=0,
            block_index=0,
        )
        delete_op = EditOperation(op="delete_bookmark", bookmark_id="Intro")
        script = build_edit_script([set_op, delete_op], file_ext="pdf")
        assert "GetBookmark" in script
        assert "AddBookmark" in script
        assert "DeleteBookmark" in script

    def test_set_annotation_updates_by_index(self):
        op = EditOperation(
            op="set_annotation",
            page_index=0,
            annotation_index=1,
            text="Updated",
            rect={"x": 1, "y": 2, "width": 3, "height": 4},
        )
        script = build_edit_script([op], file_ext="pdf")
        assert "GetAllAnnots" in script
        assert "SetContents" in script
        assert "SetRect" in script

    def test_new_ops_require_locators(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_block_text", page_index=0)
        with pytest.raises(ValidationError):
            EditOperation(op="set_cell_text", page_index=0, block_index=0, row=0)
        with pytest.raises(ValidationError):
            EditOperation(op="set_paragraph_format", page_index=0, block_index=0)
        with pytest.raises(ValidationError):
            EditOperation(op="replace_image", page_index=0, image_index=0)
        with pytest.raises(ValidationError):
            EditOperation(op="set_bookmark")
        with pytest.raises(ValidationError):
            EditOperation(op="set_annotation", page_index=0, annotation_index=0)
