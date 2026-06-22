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


def test_set_text_uses_shape_index_not_first_shape_fallback():
    op = EditOperation(op="set_text", slide_index=1, shape_index=2, text="Hello")
    script = build_edit_script([op], file_ext="pptx")
    assert "pres.GetSlideByIndex(1).GetAllShapes()[2]" in script
    assert "GetAllShapes()[0]" not in script


def test_set_text_without_shape_locator_raises():
    op = EditOperation.model_construct(op="set_text", slide_index=0, text="hi")
    with pytest.raises(ValueError, match="shape_index, match_text, or role"):
        build_edit_script([op], file_ext="pptx")
