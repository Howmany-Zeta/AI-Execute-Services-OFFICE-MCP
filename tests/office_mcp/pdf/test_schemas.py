"""Tests for PDF Pydantic schemas (ADR-030)."""

import pytest
from pydantic import ValidationError

from aiecs.tools.office_tool.pdf.schemas.edit_ops import EditOperation, PdfEditArgs, PdfMergeArgs
from aiecs.tools.office_tool.pdf.schemas.page_spec import PageSpec, PdfCreateArgs


class TestPdfSchemas:
    def test_fill_form_field_not_in_edit_ops(self):
        schema = EditOperation.model_json_schema()
        assert "fill_form_field" not in str(schema.get("properties", {}).get("op", {}))

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

    def test_edit_args_source_required(self):
        with pytest.raises(ValidationError):
            PdfEditArgs(
                output_path="gs://b/out.pdf",
                operations=[{"op": "add_paragraph", "page_index": 0, "text": "x"}],
            )
