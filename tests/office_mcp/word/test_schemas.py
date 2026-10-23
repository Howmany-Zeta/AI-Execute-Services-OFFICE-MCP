"""Tests for word Pydantic schemas (ADR-010/011/012)."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.word.schemas.edit_ops import EDIT_OPERATION_ITEM_SCHEMA, EditOperation, WordEditArgs
from aiecs.tools.office_tool.word.schemas.section_spec import SectionSpec, WordCreateArgs
from aiecs.tools.office_tool.word.tools.edit import TOOL_DEF


class TestEditOpsSchema:
    def test_delete_block_on_table_rejected(self):
        with pytest.raises(ValidationError):
            EditOperation(op="delete_block", block_index=0, block_type="table")

    def test_no_relative_index_in_schema(self):
        schema = EditOperation.model_json_schema()
        assert "relative_index" not in str(schema)

    def test_search_replace_requires_search_string(self):
        with pytest.raises(ValidationError):
            EditOperation(op="search_replace", replace_string="x")

    def test_search_replace_subtree_requires_locator(self):
        with pytest.raises(ValidationError):
            EditOperation(
                op="search_replace",
                search_string="a",
                replace_string="b",
                scope="subtree",
            )

    def test_search_replace_subtree_with_block_index(self):
        op = EditOperation(
            op="search_replace",
            search_string="a",
            replace_string="b",
            scope="subtree",
            block_index=0,
        )
        assert op.scope == "subtree"

    def test_insert_section_break_without_locator(self):
        op = EditOperation(op="insert_section_break")
        assert op.op == "insert_section_break"

    def test_set_header_accepts_first_variant(self):
        op = EditOperation(op="set_header", text="x", variant="first")
        assert op.variant == "first"

    def test_delete_table_allowed(self):
        op = EditOperation(op="delete_table", block_index=2)
        assert op.op == "delete_table"

    def test_delete_block_image_allowed(self):
        op = EditOperation(op="delete_block", block_index=3, block_type="image")
        assert op.block_type == "image"


class TestEditToolDefSchema:
    def test_operations_schema_matches_edit_ops(self):
        props = TOOL_DEF["inputSchema"]["properties"]["operations"]["items"]["properties"]
        for key in EDIT_OPERATION_ITEM_SCHEMA["properties"]:
            assert key in props
        assert "search_string" in props
        assert "replace_string" in props
        assert props["op"]["enum"] == EDIT_OPERATION_ITEM_SCHEMA["properties"]["op"]["enum"]


class TestSectionSpec:
    def test_add_toc_bool_only(self):
        args = WordCreateArgs(
            sections=[SectionSpec(type="paragraph", text="Hi")],
            output_path="gs://b/out.docx",
            options={"add_toc": True},
        )
        assert args.options.add_toc is True

    def test_paragraph_requires_text(self):
        with pytest.raises(ValidationError):
            SectionSpec(type="paragraph")
