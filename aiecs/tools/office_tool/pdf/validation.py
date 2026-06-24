"""PDF path/extension validation for PDF write tools."""

from __future__ import annotations

from typing import Any

from aiecs.tools.office_tool.core.categories import assert_category_path, classify_file_ext
from aiecs.tools.office_tool.core.errors import err


def validate_pdf_source_ext(file_ext: str) -> dict[str, Any] | None:
    """Return error dict when source extension is not a PDF category file."""
    if classify_file_ext(file_ext) == "pdf":
        return None
    cat_err = assert_category_path("pdf", f"file.{file_ext}")
    return err(cat_err or f"Not a PDF file: .{file_ext}")


def validate_pdf_output_path(output_path: str) -> dict[str, Any] | None:
    """Return error dict when output_path is not a PDF category path."""
    path_err = assert_category_path("pdf", output_path)
    if path_err:
        return err(path_err)
    return None
