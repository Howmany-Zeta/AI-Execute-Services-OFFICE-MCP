"""Re-export coarse TXT parser from core (ADR-029)."""

from aiecs.tools.office_tool.core.coarse_parsers.txt import (
    extract_outline_from_txt,
    parse_txt_to_structure,
)

__all__ = ["extract_outline_from_txt", "parse_txt_to_structure"]
