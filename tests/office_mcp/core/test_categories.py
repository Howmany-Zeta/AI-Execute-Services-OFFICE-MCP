"""Tests for core/categories.py."""

import pytest

from aiecs.tools.office_tool.core.categories import (
    assert_category_path,
    builder_file_ext,
    classify_file_ext,
    llm_coarse_output_type,
)


class TestClassifyFileExt:
    def test_docx_is_word(self):
        assert classify_file_ext("docx") == "word"

    def test_pptx_is_presentation(self):
        assert classify_file_ext("pptx") == "presentation"

    def test_xlsx_is_spreadsheet(self):
        assert classify_file_ext("xlsx") == "spreadsheet"

    def test_pdf_is_pdf(self):
        assert classify_file_ext("pdf") == "pdf"

    def test_unknown_extension(self):
        assert classify_file_ext("xyz") == "unknown"


class TestLlmCoarseOutputType:
    def test_word_html(self):
        assert llm_coarse_output_type("docx") == "html"

    def test_presentation_txt(self):
        assert llm_coarse_output_type("pptx") == "txt"

    def test_spreadsheet_csv(self):
        assert llm_coarse_output_type("xlsx") == "csv"

    def test_pdf_txt(self):
        assert llm_coarse_output_type("pdf") == "txt"


class TestBuilderFileExt:
    def test_from_gs_path(self):
        assert builder_file_ext("gs://bucket/path/file.docx") == "docx"


class TestAssertCategoryPath:
    def test_matching_word_path(self):
        assert assert_category_path("word", "gs://b/doc.docx") is None

    def test_mismatch_returns_message(self):
        msg = assert_category_path("word", "gs://b/slides.pptx")
        assert msg is not None
        assert "word" in msg
