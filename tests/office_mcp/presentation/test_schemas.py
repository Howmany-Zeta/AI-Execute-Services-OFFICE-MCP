"""Tests for presentation Pydantic schemas (ADR-016)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.presentation.schemas.edit_ops import EditOperation, PresentationEditArgs
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PresentationCreateArgs,
    SlideSpec,
    validate_add_slide_layouts,
    validate_slides_layouts,
)

FIXTURES = Path(__file__).parent / "fixtures"
PPTX_LAYOUTS = json.loads((FIXTURES / "layouts_pptx.json").read_text())


class TestLayoutValidation:
    def test_validate_slides_layouts_rejects_unknown(self):
        slides = [SlideSpec(layout="Unknown Layout")]
        err = validate_slides_layouts(slides, PPTX_LAYOUTS)
        assert err is not None
        assert "Unknown Layout" in err

    def test_validate_slides_layouts_accepts_enum(self):
        slides = [SlideSpec(layout="Title Slide")]
        assert validate_slides_layouts(slides, PPTX_LAYOUTS) is None

    def test_create_with_allowed_layouts(self):
        args = PresentationCreateArgs(
            slides=[SlideSpec(layout="Title and Content", title="Hi")],
            output_path="gs://b/out.pptx",
            options={"allowed_layouts": PPTX_LAYOUTS},
        )
        assert args.slides[0].layout == "Title and Content"

    def test_create_requires_allowed_layouts(self):
        with pytest.raises(ValidationError):
            PresentationCreateArgs(
                slides=[SlideSpec(layout="Title Slide", title="Hi")],
                output_path="gs://b/out.pptx",
                options={},
            )

    def test_validate_add_slide_layouts_requires_allowed_layouts(self):
        op = EditOperation(op="add_slide", layout="Title Slide")
        err = validate_add_slide_layouts([op], None)
        assert err is not None
        assert "allowed_layouts" in err


class TestEditOpsSchema:
    def test_add_slide_requires_layout(self):
        with pytest.raises(ValidationError):
            EditOperation(op="add_slide")

    def test_delete_slide_requires_slide_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="delete_slide")

    def test_set_text_requires_slide_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_text", text="x")

    def test_invalid_slide_index_negative(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_title", slide_index=-1, text="x")

    def test_edit_args_source_required(self):
        with pytest.raises(ValidationError):
            PresentationEditArgs(output_path="gs://b/out.pptx", operations=[{"op": "set_title", "slide_index": 0, "text": "T"}])
