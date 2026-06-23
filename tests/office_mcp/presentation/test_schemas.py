"""Tests for presentation Pydantic schemas (ADR-016)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.presentation.schemas.edit_ops import (
    EDIT_OPERATION_ITEM_SCHEMA,
    EditOperation,
    OpName,
    PRESENTATION_EDIT_INPUT_SCHEMA,
    PresentationEditArgs,
)
from aiecs.tools.office_tool.presentation.schemas.read import PRESENTATION_READ_INPUT_SCHEMA
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PRESENTATION_CREATE_INPUT_SCHEMA,
    PresentationCreateArgs,
    SlideSpec,
    validate_add_slide_layouts,
    validate_slides_layouts,
)
from aiecs.tools.office_tool.presentation.tools.create import TOOL_DEF as CREATE_TOOL_DEF
from aiecs.tools.office_tool.presentation.tools.edit import TOOL_DEF
from aiecs.tools.office_tool.presentation.tools.read import TOOL_DEF as READ_TOOL_DEF

FIXTURES = Path(__file__).parent / "fixtures"
PPTX_LAYOUTS = json.loads((FIXTURES / "layouts_pptx.json").read_text())
ODP_LAYOUTS = json.loads((FIXTURES / "layouts_odp.json").read_text())


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

    def test_validate_slides_layouts_accepts_odp_enum(self):
        slides = [SlideSpec(layout="Title")]
        assert validate_slides_layouts(slides, ODP_LAYOUTS) is None

    def test_validate_slides_layouts_rejects_unknown_odp_layout(self):
        slides = [SlideSpec(layout="Unknown ODP Layout")]
        err = validate_slides_layouts(slides, ODP_LAYOUTS)
        assert err is not None
        assert "Unknown ODP Layout" in err

    def test_create_with_odp_allowed_layouts(self):
        args = PresentationCreateArgs(
            slides=[SlideSpec(layout="Title and Content", title="Hi")],
            output_path="gs://b/out.odp",
            options={"allowed_layouts": ODP_LAYOUTS},
        )
        assert args.slides[0].layout == "Title and Content"


class TestEditOpsSchema:
    def test_add_slide_requires_layout(self):
        with pytest.raises(ValidationError):
            EditOperation(op="add_slide")

    def test_add_slide_accepts_title_subtitle_items(self):
        op = EditOperation(
            op="add_slide",
            layout="Title and Content",
            title="New slide title",
            subtitle="Subtitle here",
            items=["Point A", "Point B"],
        )
        assert op.title == "New slide title"
        assert op.subtitle == "Subtitle here"
        assert op.items == ["Point A", "Point B"]

    def test_delete_slide_requires_slide_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="delete_slide")

    def test_duplicate_slide_requires_slide_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="duplicate_slide")

    def test_move_slide_requires_from_and_to_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="move_slide", from_index=0)

    def test_set_notes_requires_slide_index_and_text(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_notes", slide_index=0)

    def test_set_text_requires_slide_index(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_text", text="x")

    def test_invalid_slide_index_negative(self):
        with pytest.raises(ValidationError):
            EditOperation(op="set_title", slide_index=-1, text="x")

    def test_edit_args_source_required(self):
        with pytest.raises(ValidationError):
            PresentationEditArgs(output_path="gs://b/out.pptx", operations=[{"op": "set_title", "slide_index": 0, "text": "T"}])


class TestEditToolDefSchema:
    def _operation_item_properties(self, input_schema: dict) -> dict:
        items = input_schema["properties"]["operations"]["items"]
        if "$ref" in items:
            ref_name = items["$ref"].rsplit("/", 1)[-1]
            return input_schema["$defs"][ref_name]["properties"]
        return items["properties"]

    def test_operations_schema_matches_edit_ops(self):
        props = self._operation_item_properties(TOOL_DEF["inputSchema"])
        for key in EDIT_OPERATION_ITEM_SCHEMA["properties"]:
            assert key in props
        assert "title" in props
        assert "subtitle" in props
        assert "items" in props
        assert props["op"]["enum"] == list(OpName.__args__)
        assert set(props["op"]["enum"]) == set(OpName.__args__)

    def test_edit_input_schema_matches_pydantic(self):
        assert TOOL_DEF["inputSchema"] == PRESENTATION_EDIT_INPUT_SCHEMA

    def test_edit_operation_item_schema_keeps_title_property(self):
        assert "title" in EDIT_OPERATION_ITEM_SCHEMA["properties"]
        assert "subtitle" in EDIT_OPERATION_ITEM_SCHEMA["properties"]
        assert "items" in EDIT_OPERATION_ITEM_SCHEMA["properties"]

    def test_create_input_schema_matches_pydantic(self):
        assert CREATE_TOOL_DEF["inputSchema"] == PRESENTATION_CREATE_INPUT_SCHEMA
        slide_items = CREATE_TOOL_DEF["inputSchema"]["properties"]["slides"]["items"]
        assert "$ref" in slide_items or "properties" in slide_items
        assert "layout" in (
            slide_items.get("properties", {})
            or CREATE_TOOL_DEF["inputSchema"]["$defs"]["SlideSpec"]["properties"]
        )

    def test_read_input_schema_matches_pydantic(self):
        assert READ_TOOL_DEF["inputSchema"] == PRESENTATION_READ_INPUT_SCHEMA
        options = READ_TOOL_DEF["inputSchema"]["properties"]["options"]
        if "$ref" in options:
            ref_name = options["$ref"].rsplit("/", 1)[-1]
            option_props = READ_TOOL_DEF["inputSchema"]["$defs"][ref_name]["properties"]
        else:
            option_props = options["properties"]
        assert "allow_coarse_fallback" in option_props
        assert "slide_range" in option_props
