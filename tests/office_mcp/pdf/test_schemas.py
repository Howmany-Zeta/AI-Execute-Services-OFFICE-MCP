"""Tests for PDF Pydantic schemas (ADR-030)."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.pdf.schemas.edit_ops import (
    EDIT_OPERATION_ITEM_SCHEMA,
    EditOperation,
    OpName,
    PdfEditArgs,
)
from aiecs.tools.office_tool.pdf.schemas.merge import PdfMergeArgs
from aiecs.tools.office_tool.pdf.schemas.page_spec import PAGE_ITEM_SCHEMA, PageSpec, PdfCreateArgs
from aiecs.tools.office_tool.pdf.tools.create import TOOL_DEF as CREATE_TOOL_DEF
from aiecs.tools.office_tool.pdf.tools.edit import TOOL_DEF


class TestPdfSchemas:
    def test_fill_form_field_not_in_edit_ops(self):
        schema = EditOperation.model_json_schema()
        assert "fill_form_field" not in str(schema.get("properties", {}).get("op", {}))

    def test_edit_tool_def_op_enum_matches_schema(self):
        props = TOOL_DEF["inputSchema"]["properties"]["operations"]["items"]["properties"]
        enum = props["op"].get("enum") or props["op"].get("anyOf", [{}])[0].get("enum", [])
        assert set(enum) == set(OpName.__args__)
        assert set(EDIT_OPERATION_ITEM_SCHEMA["properties"]["op"]["enum"]) == set(OpName.__args__)

    def test_create_tool_def_pages_match_page_spec_schema(self):
        pages_items = CREATE_TOOL_DEF["inputSchema"]["properties"]["pages"]["items"]
        assert pages_items is PAGE_ITEM_SCHEMA
        assert CREATE_TOOL_DEF["inputSchema"]["properties"]["pages"]["minItems"] == 1

    def test_create_mode_enum(self):
        args = PdfCreateArgs(
            pages=[PageSpec(blocks=[{"type": "paragraph", "text": "Hi"}])],
            output_path="gs://b/out.pdf",
            options={"create_mode": "via_docx"},
        )
        assert args.options.create_mode == "via_docx"

    def test_add_paragraph_requires_fields(self):
        with pytest.raises(ValidationError):
            EditOperation(op="add_paragraph", page_index=0)

    def test_merge_engine_default_builder(self):
        args = PdfMergeArgs(source_urls=["http://a/a.pdf", "http://b/b.pdf"], output_path="gs://b/out.pdf")
        assert args.options.engine == "builder"

    def test_merge_requires_at_least_two_sources(self):
        with pytest.raises(ValidationError):
            PdfMergeArgs(source_paths=["gs://b/a.pdf"], output_path="gs://b/out.pdf")

    def test_read_args_source_required(self):
        from aiecs.tools.office_tool.pdf.schemas.read import PdfReadArgs

        with pytest.raises(ValidationError):
            PdfReadArgs()

    def test_edit_args_source_required(self):
        with pytest.raises(ValidationError):
            PdfEditArgs(
                output_path="gs://b/out.pdf",
                operations=[{"op": "add_paragraph", "page_index": 0, "text": "x"}],
            )
