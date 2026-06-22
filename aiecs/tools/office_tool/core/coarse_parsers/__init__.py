"""Coarse Conversion API output parsers (html, txt, csv).

Shared by core/coarse_read and vertical read tools. Lives in core/ so
coarse_read does not import word|presentation|spreadsheet (ADR-029).
"""

from aiecs.tools.office_tool.core.coarse_parsers.csv import (
    csv_to_coarse_sheets,
    extract_outline_from_csv,
    parse_csv_to_structure,
)
from aiecs.tools.office_tool.core.coarse_parsers.html import (
    extract_outline,
    extract_plain_text,
    parse_html_to_structure,
)
from aiecs.tools.office_tool.core.coarse_parsers.txt import (
    extract_outline_from_txt,
    parse_txt_to_structure,
)

__all__ = [
    "csv_to_coarse_sheets",
    "extract_outline",
    "extract_outline_from_csv",
    "extract_outline_from_txt",
    "extract_plain_text",
    "parse_csv_to_structure",
    "parse_html_to_structure",
    "parse_txt_to_structure",
]
