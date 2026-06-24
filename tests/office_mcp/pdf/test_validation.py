"""Tests for pdf/validation.py."""

from aiecs.tools.office_tool.pdf.validation import validate_pdf_output_path, validate_pdf_source_ext


class TestPdfValidation:
    def test_validate_pdf_source_ext_accepts_pdf(self):
        assert validate_pdf_source_ext("pdf") is None

    def test_validate_pdf_source_ext_rejects_docx(self):
        result = validate_pdf_source_ext("docx")
        assert result is not None
        assert result.get("isError") is True
        assert "pdf" in result.get("text", "").lower()

    def test_validate_pdf_output_path_accepts_pdf(self):
        assert validate_pdf_output_path("gs://b/out.pdf") is None

    def test_validate_pdf_output_path_rejects_docx(self):
        result = validate_pdf_output_path("gs://b/out.docx")
        assert result is not None
        assert result.get("isError") is True
        assert "pdf" in result.get("text", "").lower()
