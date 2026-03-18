"""
Office document tools for MCP.

Tools: office_execute_builder, office_edit_document, office_read_document,
office_merge_documents, office_apply_template, office_call_api.
"""

from aiecs.tools.office_tool.execute_builder import (
    office_execute_builder,
    OFFICE_EXECUTE_BUILDER_TOOL,
)
from aiecs.tools.office_tool.edit_document import (
    office_edit_document,
    OFFICE_EDIT_DOCUMENT_TOOL,
)
from aiecs.tools.office_tool.read_document import (
    office_read_document,
    OFFICE_READ_DOCUMENT_TOOL,
)
from aiecs.tools.office_tool.merge_document import (
    office_merge_documents,
    OFFICE_MERGE_DOCUMENTS_TOOL,
)
from aiecs.tools.office_tool.apply_template import (
    office_apply_template,
    OFFICE_APPLY_TEMPLATE_TOOL,
)
from aiecs.tools.office_tool.call_api import (
    office_call_api,
    OFFICE_CALL_API_TOOL,
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
]
