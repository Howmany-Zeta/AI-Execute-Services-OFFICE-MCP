"""Registry tests — counts per milestone (ADR-024)."""

from aiecs.tools.office_tool.registry import (
    CANONICAL_MODULES,
    LEGACY_MODULES,
    OFFICE_TOOL_MODULES,
    canonical_count,
    collect_office_tools,
    get_handlers,
    tool_count,
)

# M6 milestone counts (FINAL)
M6_CANONICAL = 23
M6_HANDLERS = 27

LEGACY_TOOL_NAMES = {
    "office_read_document",
    "office_edit_document",
    "office_merge_documents",
    "office_apply_template",
}

PDF_TOOL_NAMES = {
    "office_read_pdf",
    "office_create_pdf",
    "office_edit_pdf",
    "office_merge_pdfs",
    "office_fill_pdf_form",
}


class TestRegistryM6:
    """M6 FINAL: M5 + pdf×5 canonical; 4 legacy handlers only."""

    def test_module_lists(self):
        assert len(CANONICAL_MODULES) == M6_CANONICAL
        assert len(LEGACY_MODULES) == 4
        assert len(OFFICE_TOOL_MODULES) == M6_CANONICAL + 4

    def test_collect_office_tools_count(self):
        assert len(collect_office_tools()) == M6_CANONICAL

    def test_get_handlers_count(self):
        assert len(get_handlers()) == M6_HANDLERS

    def test_tool_count_helpers(self):
        assert tool_count() == M6_CANONICAL
        assert canonical_count() == M6_CANONICAL

    def test_legacy_not_in_collect(self):
        names = {t["name"] for t in collect_office_tools()}
        assert names.isdisjoint(LEGACY_TOOL_NAMES)

    def test_legacy_in_handlers(self):
        assert LEGACY_TOOL_NAMES <= set(get_handlers().keys())

    def test_pdf_tools_in_collect(self):
        names = {t["name"] for t in collect_office_tools()}
        assert PDF_TOOL_NAMES <= names
        assert "office_apply_template_pdf" not in names

    def test_no_pdf_legacy_aliases(self):
        handlers = get_handlers()
        assert "office_read_pdf" in handlers
        assert handlers["office_read_pdf"] is not handlers.get("office_read_document")

    def test_category_description_prefixes(self):
        tools = {t["name"]: t["description"] for t in collect_office_tools()}
        for name in PDF_TOOL_NAMES:
            assert tools[name].startswith("[PDF]"), name

    def test_final_counts(self):
        assert len(collect_office_tools()) == 23
        assert len(get_handlers()) == 27
