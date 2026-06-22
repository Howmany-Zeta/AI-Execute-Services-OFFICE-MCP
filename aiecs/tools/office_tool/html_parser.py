# deprecated: re-export word html + presentation txt + spreadsheet csv parsers
from aiecs.tools.office_tool.presentation.parser.txt import (  # noqa: F401
    extract_outline_from_txt,
    parse_txt_to_structure,
)
from aiecs.tools.office_tool.spreadsheet.parser.csv import (  # noqa: F401
    extract_outline_from_csv,
    parse_csv_to_structure,
)
from aiecs.tools.office_tool.word.parser.html import (  # noqa: F401
    extract_outline,
    extract_plain_text,
    parse_html_to_structure,
)

__all__ = [
    "extract_outline",
    "extract_outline_from_csv",
    "extract_outline_from_txt",
    "extract_plain_text",
    "parse_csv_to_structure",
    "parse_html_to_structure",
    "parse_txt_to_structure",
]
