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
    assert "notesShapes.length > 0" in script
    assert "notesPage.AddTextbox()" in script
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
    assert 'pres.AddSlide("Title and Content"' in script
    assert "Added title" in script
    assert 'GetPlaceholder("subtitle")' in script
    assert "Added subtitle" in script
    assert "Bullet one" in script
    assert "Bullet two" in script
    assert "bodyShape.Clear()" in script


def test_set_bullets_emits_body_placeholder():
    op = EditOperation(op="set_bullets", slide_index=1, items=["Alpha", "Beta"])
    script = build_edit_script([op], file_ext="pptx")
    assert 'pres.GetSlideByIndex(1).GetPlaceholder("body")' in script
    assert "bodyShape.Clear()" in script
    assert "Alpha" in script
    assert "Beta" in script


def test_duplicate_slide_emits_duplicate_call():
    op = EditOperation(op="duplicate_slide", slide_index=2, after_index=3)
    script = build_edit_script([op], file_ext="pptx")
    assert "pres.DuplicateSlide(2, 3)" in script


def test_move_slide_emits_move_call():
    op = EditOperation(op="move_slide", from_index=1, to_index=0)
    script = build_edit_script([op], file_ext="pptx")
    assert "pres.MoveSlide(1, 0)" in script


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
    assert 'GetPlaceholder("body")' in script
    assert "SetImage" in script
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
    assert 'GetPlaceholder("subtitle")' in script
    assert "Sub line" in script
