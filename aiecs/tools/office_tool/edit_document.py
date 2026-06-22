# deprecated: use legacy.edit_document / word.tools.edit_script
from aiecs.tools.office_tool.legacy.edit_document import (  # noqa: F401
    OFFICE_EDIT_DOCUMENT_TOOL,
    office_edit_document,
)

__all__ = ["OFFICE_EDIT_DOCUMENT_TOOL", "office_edit_document"]
