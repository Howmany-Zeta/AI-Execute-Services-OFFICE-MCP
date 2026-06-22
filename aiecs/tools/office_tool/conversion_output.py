# deprecated: use core.categories
from aiecs.tools.office_tool.core.categories import (  # noqa: F401
    PDF_EXTENSIONS,
    PRESENTATION_EXTENSIONS,
    SPREADSHEET_EXTENSIONS,
    WORD_EXTENSIONS,
    DocumentCategory,
    assert_category_path,
    builder_file_ext,
    classify_file_ext,
    llm_coarse_output_type,
    llm_coarse_output_type as llm_output_type,
)

__all__ = [
    "DocumentCategory",
    "PDF_EXTENSIONS",
    "PRESENTATION_EXTENSIONS",
    "SPREADSHEET_EXTENSIONS",
    "WORD_EXTENSIONS",
    "assert_category_path",
    "builder_file_ext",
    "classify_file_ext",
    "llm_coarse_output_type",
    "llm_output_type",
]
