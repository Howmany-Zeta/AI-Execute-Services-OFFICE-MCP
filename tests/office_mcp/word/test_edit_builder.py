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
        assert "doc.GetElement(" not in script

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

    def test_set_run_format_emits_font_calls(self):
        ops = [EditOperation(
            op="set_run_format",
            block_index=2,
            run_index=1,
            bold=True,
            font_size_pt=14,
            font_name="Calibri",
        )]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(2)" in script
        assert "SetBold(true)" in script
        assert "SetFontSize(14" in script
        assert 'SetFontFamily("Calibri")' in script

    def test_set_paragraph_format_emits_set_jc(self):
        ops = [EditOperation(op="set_paragraph_format", block_index=0, align="center")]
        script = build_edit_script(ops, file_ext="docx")
        assert 'SetJc("center")' in script

    def test_set_list_uses_numbering(self):
        ops = [EditOperation(op="set_list", block_index=3, list_type="bullet", list_level=1)]
        script = build_edit_script(ops, file_ext="docx")
        assert 'CreateNumbering("bullet")' in script
        assert "GetLevel(1)" in script
        assert "SetNumbering" in script
        assert "•" not in script

    def test_set_header_default_with_page_number(self):
        ops = [EditOperation(
            op="set_header",
            section_index=0,
            text="Confidential",
            page_number={"position": "right", "start": 2},
        )]
        script = build_edit_script(ops, file_ext="docx")
        assert 'GetHeader("default"' in script
        assert "AddPageNumber()" in script
        assert "SetStartPageNumber(2)" in script
        assert "SetTitlePage" not in script
        assert "SetEvenAndOddHdrFtr" not in script

    def test_set_heading_accepts_heading_level(self):
        ops = [EditOperation(op="set_heading", block_index=0, text="Deep", heading_level=4)]
        script = build_edit_script(ops, file_ext="docx")
        assert 'SetStyle("Heading 4")' in script

    def test_move_block_uses_remove_and_add(self):
        ops = [EditOperation(op="move_block", block_index=4, to_block_index=1)]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(4)" in script
        assert "RemoveElement" in script
        assert "AddElement(moveDest, moveSrc)" in script

    def test_insert_image_uses_create_image(self):
        ops = [EditOperation(op="insert_image", url="https://cdn.example/a.png", after="end")]
        script = build_edit_script(ops, file_ext="docx")
        assert "Api.CreateImage" in script
        assert "https://cdn.example/a.png" in script

    def test_set_header_first_variant_enables_title_page(self):
        ops = [EditOperation(op="set_header", text="Cover", variant="first")]
        script = build_edit_script(ops, file_ext="docx")
        assert 'GetHeader("title"' in script
        assert "SetTitlePage(true)" in script

    def test_set_run_format_emits_strike_highlight_color(self):
        ops = [EditOperation(
            op="set_run_format",
            block_index=0,
            strike=True,
            highlight="#FFFF00",
            font_color="#112233",
        )]
        script = build_edit_script(ops, file_ext="docx")
        assert "SetStrikeout(true)" in script
        assert 'SetHighlight("#FFFF00")' in script
        assert "CreateColorFromRGB(17, 34, 51)" in script

    def test_delete_table_row_uses_get_row_object(self):
        ops = [EditOperation(op="delete_table_row", block_index=4, row=1)]
        script = build_edit_script(ops, file_ext="docx")
        assert "doc.GetElement(4)" in script
        assert "GetRow(1)" in script
        assert "RemoveRow(delRow)" in script

    def test_set_footer_does_not_throw_on_get_footer(self):
        ops = [EditOperation(op="set_footer", text="LIVE-FOOTER")]
        script = build_edit_script(ops, file_ext="docx")
        assert "GetFooter" in script
        assert "catch (eHf1)" in script

    def test_set_section_and_typed_section_break(self):
        ops = [
            EditOperation(op="set_section", section_index=0, columns=2, different_first_page=True),
            EditOperation(op="insert_section_break", break_type="odd"),
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert "SetEqualColumns(2, 720)" in script
        assert "SetTitlePage(true)" in script
        assert 'AddBreak("oddPage")' in script

    def test_search_replace_document_level_stays_on_body_search(self):
        ops = [EditOperation(op="search_replace", search_string="x", replace_string="y")]
        script = build_edit_script(ops, file_ext="docx")
        assert "SearchAndReplace" in script
        assert "GetHeader" not in script
        assert "GetAllFootnotes" not in script

    def test_insert_footnote_and_comment_emitters(self):
        ops = [
            EditOperation(op="insert_footnote", block_index=1, run_index=0, text="fn", footnote_id="fn1"),
            EditOperation(op="insert_comment", block_index=1, text="note"),
            EditOperation(op="insert_chart", chart_type="bar", rows=[["1", "2"]]),
            EditOperation(op="insert_textbox", width_pt=80, height_pt=40, text="Box"),
        ]
        script = build_edit_script(ops, file_ext="docx")
        assert "AddFootnote" in script
        assert "AddComment" in script
        assert "CreateChart" in script
        assert 'CreateShape("rect"' in script
