"""Legacy compat: package exports forward to legacy handlers."""

import pytest

from aiecs.tools.office_tool import (
    office_apply_template,
    office_edit_document,
    office_merge_documents,
)
from aiecs.tools.office_tool.legacy.apply_template import LEGACY_ALIASES as APPLY_ALIASES
from aiecs.tools.office_tool.legacy.edit_document import LEGACY_ALIASES as EDIT_ALIASES
from aiecs.tools.office_tool.legacy.merge_documents import LEGACY_ALIASES as MERGE_ALIASES
from aiecs.tools.office_tool.word.tools.edit_script import office_edit_word_script
from aiecs.tools.office_tool.word.tools.merge import office_merge_word
from aiecs.tools.office_tool.word.tools.template import office_apply_template_word

pytestmark = pytest.mark.asyncio


def test_legacy_aliases_registered():
    assert EDIT_ALIASES[0][0] == "office_edit_document"
    assert MERGE_ALIASES[0][0] == "office_merge_documents"
    assert APPLY_ALIASES[0][0] == "office_apply_template"


def test_root_imports_same_handlers():
    assert office_edit_document is not None
    assert office_merge_documents is not None
    assert office_apply_template is not None


@pytest.mark.asyncio
async def test_legacy_edit_forwards(monkeypatch):
    called = {}

    async def fake(*args, **kwargs):
        called["yes"] = True
        return {"success": True, "output_path": kwargs.get("output_path")}

    monkeypatch.setattr(
        "aiecs.tools.office_tool.legacy.edit_document.office_edit_word_script",
        fake,
    )
    result = await office_edit_document(
        edit_script="x();",
        output_path="gs://b/out.docx",
        source_path="gs://b/in.docx",
    )
    assert called.get("yes")
    assert result.get("success") is True
