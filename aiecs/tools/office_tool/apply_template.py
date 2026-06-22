# deprecated: use legacy.apply_template / word.tools.template
from aiecs.tools.office_tool.legacy.apply_template import (  # noqa: F401
    OFFICE_APPLY_TEMPLATE_TOOL,
    office_apply_template,
)
from aiecs.tools.office_tool.word.builder.template import build_apply_template_script as _build_apply_template_script

__all__ = ["OFFICE_APPLY_TEMPLATE_TOOL", "office_apply_template", "_build_apply_template_script"]
