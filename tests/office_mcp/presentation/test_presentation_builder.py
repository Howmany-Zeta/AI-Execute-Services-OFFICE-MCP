"""Tests for presentation builder script generation."""

import pytest

from aiecs.tools.office_tool.presentation.builder.create import build_create_script
from aiecs.tools.office_tool.presentation.builder.edit import build_edit_script
from aiecs.tools.office_tool.presentation.schemas.edit_ops import EditOperation
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PresentationCreateOptions,
    SlideSpec,
)


def test_create_script_notes_handles_empty_notes_page():
    slides = [SlideSpec(layout="Title Slide", title="T", notes="Speaker notes here")]
    options = PresentationCreateOptions(allowed_layouts=["Title Slide"])
    script = build_create_script(slides, output_ext="pptx", options=options)
    assert "AddNotesText" in script
    assert "Speaker notes here" in script
    assert "GetAllShapes()[0].SetText" not in script


def test_create_bullets_clears_body_placeholder():
    slides = [
        SlideSpec(
            layout="Title and Content",
            title="T",
            bullets=["Alpha", "Beta"],
        )
    ]
    options = PresentationCreateOptions(allowed_layouts=["Title and Content"])
    script = build_create_script(slides, output_ext="pptx", options=options)
    assert "bodyShape.Clear()" in script
    assert "Alpha" in script
    assert "Beta" in script


def test_set_text_uses_shape_index_not_first_shape_fallback():
    op = EditOperation(op="set_text", slide_index=1, shape_index=2, text="Hello")
    script = build_edit_script([op], file_ext="pptx")
    assert "pres.GetSlideByIndex(1).GetAllShapes()[2]" in script
    assert "_officeSetShapeText" in script
    assert "GetAllShapes()[0]" not in script


def test_set_text_without_shape_locator_raises():
    op = EditOperation.model_construct(op="set_text", slide_index=0, text="hi")
    with pytest.raises(ValueError, match="shape_index, match_text, or role"):
        build_edit_script([op], file_ext="pptx")


def test_add_slide_emits_title_subtitle_items():
    op = EditOperation(
        op="add_slide",
        layout="Title and Content",
        title="Added title",
        subtitle="Added subtitle",
        items=["Bullet one", "Bullet two"],
    )
    script = build_edit_script([op], file_ext="pptx")
    assert "Title and Content" in script
    assert "Duplicate()" in script
    assert "ApplyLayout" in script
    assert "Added title" in script
    assert '_officeFindByRole(newSlide, "subtitle")' in script
    assert "Added subtitle" in script
    assert "Bullet one" in script
    assert "Bullet two" in script


def test_set_bullets_emits_body_placeholder():
    op = EditOperation(op="set_bullets", slide_index=1, items=["Alpha", "Beta"])
    script = build_edit_script([op], file_ext="pptx")
    assert '_officeFindByRole(pres.GetSlideByIndex(1), "body")' in script
    assert "Alpha" in script
    assert "Beta" in script


def test_duplicate_slide_emits_duplicate_call():
    op = EditOperation(op="duplicate_slide", slide_index=2, after_index=3)
    script = build_edit_script([op], file_ext="pptx")
    assert "GetSlideByIndex(2).Duplicate()" in script
    assert "MoveTo(3 + 1)" in script


def test_move_slide_emits_move_call():
    op = EditOperation(op="move_slide", from_index=1, to_index=0)
    script = build_edit_script([op], file_ext="pptx")
    assert "GetSlideByIndex(1)" in script
    assert "MoveTo(0)" in script


def test_set_notes_emits_notes_page_helper():
    op = EditOperation(op="set_notes", slide_index=0, text="Speaker notes")
    script = build_edit_script([op], file_ext="pptx")
    assert "GetNotesPage()" in script
    assert "Speaker notes" in script


def test_replace_image_with_role():
    op = EditOperation(
        op="replace_image",
        slide_index=0,
        role="body",
        url="https://example.com/logo.png",
    )
    script = build_edit_script([op], file_ext="pptx")
    assert '_officeFindByRole' in script
    assert "CreateImage" in script
    assert "https://example.com/logo.png" in script


def test_remove_shape_with_match_text():
    op = EditOperation(
        op="remove_shape",
        slide_index=1,
        match_text="DELETE-ME",
    )
    script = build_edit_script([op], file_ext="pptx")
    assert "DELETE-ME" in script
    assert ".Delete()" in script
    assert "indexOf" in script


def test_set_text_with_role_uses_placeholder():
    op = EditOperation(op="set_text", slide_index=0, role="subtitle", text="Sub line")
    script = build_edit_script([op], file_ext="pptx")
    assert '_officeFindByRole' in script
    assert "subtitle" in script
    assert "Sub line" in script


def test_set_run_format_and_geometry_on_slide():
    ops = [
        EditOperation(
            op="set_run_format",
            slide_index=0,
            shape_index=1,
            run_index=0,
            bold=True,
            font_name="Calibri",
        ),
        EditOperation(
            op="set_shape_geometry",
            slide_index=0,
            shape_index=1,
            x_pt=10,
            y_pt=20,
            width_pt=100,
            height_pt=50,
        ),
        EditOperation(op="set_paragraph_format", slide_index=0, shape_index=1, align="center"),
    ]
    script = build_edit_script(ops, file_ext="pptx")
    assert "SetBold(true)" in script
    assert 'SetFontFamily("Calibri")' in script
    assert "SetPosition(" in script
    assert 'SetJc("center")' in script


def test_layout_name_ops_resolve_master_layout():
    op = EditOperation(
        op="set_text",
        layout_name="Title Slide",
        shape_index=0,
        text="Master title",
    )
    script = build_edit_script([op], file_ext="pptx")
    assert "GetMaster" in script
    assert "GetAllLayouts" in script
    assert "Title Slide" in script
    assert "layoutHost" in script
    assert "GetSlideByIndex(0)" not in script


def test_insert_textbox_appends_to_slide():
    op = EditOperation(op="insert_textbox", slide_index=1, width_pt=80, height_pt=40, text="Box")
    script = build_edit_script([op], file_ext="pptx")
    assert 'CreateShape("rect"' in script
    assert "GetSlideByIndex(1)" in script
    assert "AddObject" in script
