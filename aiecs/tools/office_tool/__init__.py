"""
Office document tools for MCP.

Public API: gateway tools + legacy aliases (call_tool only for legacy names).
"""

from aiecs.tools.office_tool.gateway.call_api import (
    CALL_API_DESCRIPTION,
    OFFICE_CALL_API_TOOL,
    office_call_api,
)
from aiecs.tools.office_tool.gateway.execute_builder import (
    OFFICE_EXECUTE_BUILDER_TOOL,
    office_execute_builder,
)
from aiecs.tools.office_tool.legacy.apply_template import (
    OFFICE_APPLY_TEMPLATE_TOOL,
    office_apply_template,
)
from aiecs.tools.office_tool.legacy.edit_document import (
    OFFICE_EDIT_DOCUMENT_TOOL,
    office_edit_document,
)
from aiecs.tools.office_tool.legacy.merge_documents import (
    OFFICE_MERGE_DOCUMENTS_TOOL,
    office_merge_documents,
)
from aiecs.tools.office_tool.legacy.read_document import (
    OFFICE_READ_DOCUMENT_TOOL,
    office_read_document,
)

__all__ = [
    "office_execute_builder",
    "OFFICE_EXECUTE_BUILDER_TOOL",
    "office_edit_document",
    "OFFICE_EDIT_DOCUMENT_TOOL",
    "office_read_document",
    "OFFICE_READ_DOCUMENT_TOOL",
    "office_merge_documents",
    "OFFICE_MERGE_DOCUMENTS_TOOL",
    "office_apply_template",
    "OFFICE_APPLY_TEMPLATE_TOOL",
    "office_call_api",
    "OFFICE_CALL_API_TOOL",
    "CALL_API_DESCRIPTION",
]
