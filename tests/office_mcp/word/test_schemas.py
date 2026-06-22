"""Tests for word Pydantic schemas (ADR-010/011/012)."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation, WordEditArgs
from aiecs.tools.office_tool.word.schemas.section_spec import SectionSpec, WordCreateArgs


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
