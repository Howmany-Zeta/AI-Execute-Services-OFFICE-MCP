"""Re-export coarse HTML parser from core (ADR-029)."""

from aiecs.tools.office_tool.core.coarse_parsers.html import (
    extract_outline,
    extract_plain_text,
    parse_html_to_structure,
)

__all__ = ["extract_outline", "extract_plain_text", "parse_html_to_structure"]
