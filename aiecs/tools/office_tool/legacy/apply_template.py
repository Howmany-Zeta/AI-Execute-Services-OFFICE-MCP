"""Legacy alias: office_apply_template → office_apply_template_word."""

from typing import Any, Callable

from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.word.tools.template import office_apply_template_word

OFFICE_APPLY_TEMPLATE_TOOL = {
    "name": "office_apply_template",
    "description": (
        f"Fill a template document with data. Provide template_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "OR template_url (HTTP/HTTPS). "
        "Placeholders in {{key}} format. Data dict keys match placeholder names; values converted to strings."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "template_path": {"type": "string"},
            "template_url": {"type": "string"},
            "data": {"type": "object", "additionalProperties": True},
            "output_path": {"type": "string"},
        },
        "required": ["data", "output_path"],
    },
}


async def office_apply_template(*args: Any, **kwargs: Any) -> dict:
    return await office_apply_template_word(*args, **kwargs)


LEGACY_ALIASES: list[tuple[str, Callable, dict]] = [
    ("office_apply_template", office_apply_template, OFFICE_APPLY_TEMPLATE_TOOL),
]

__all__ = ["LEGACY_ALIASES", "OFFICE_APPLY_TEMPLATE_TOOL", "office_apply_template"]
