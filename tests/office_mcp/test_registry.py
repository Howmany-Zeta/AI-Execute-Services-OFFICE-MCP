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

SPREADSHEET_TOOL_NAMES = {
    "office_read_spreadsheet",
    "office_create_spreadsheet",
    "office_edit_spreadsheet",
    "office_merge_spreadsheets",
    "office_apply_template_spreadsheet",
}

CATEGORY_PREFIXES = {
    "gateway": "[Gateway]",
    "word": "[Word]",
    "presentation": "[Presentation]",
    "spreadsheet": "[Spreadsheet]",
    "pdf": "[PDF]",
}

PRESENTATION_TOOL_NAMES = {
    "office_read_presentation",
    "office_create_presentation",
    "office_edit_presentation",
    "office_merge_presentations",
    "office_apply_template_presentation",
}

M4_CANONICAL = 13
M4_HANDLERS = 17


class TestRegistryM4:
    """M4 milestone: gateway×2 + word×6 + presentation×5 canonical tools."""

    def test_presentation_modules_slice(self):
        presentation_modules = CANONICAL_MODULES[8:13]
        assert len(presentation_modules) == 5
        assert all(".presentation." in mod for mod in presentation_modules)

    def test_presentation_tool_names_in_m4_slice(self):
        tools = collect_office_tools()
        m4_tools = tools[:M4_CANONICAL]
        names = {t["name"] for t in m4_tools}
        assert PRESENTATION_TOOL_NAMES <= names

    def test_m4_canonical_count_slice(self):
        assert len(collect_office_tools()[:M4_CANONICAL]) == M4_CANONICAL

    def test_presentation_tools_use_presentation_prefix(self):
        tools = {t["name"]: t["description"] for t in collect_office_tools()}
        for name in PRESENTATION_TOOL_NAMES:
            assert tools[name].startswith("[Presentation]"), name

    def test_m4_handlers_milestone_count(self):
        assert M4_CANONICAL + len(LEGACY_MODULES) == M4_HANDLERS
        m4_canonical_names = {t["name"] for t in collect_office_tools()[:M4_CANONICAL]}
        m4_handler_names = m4_canonical_names | LEGACY_TOOL_NAMES
        assert len(m4_handler_names) == M4_HANDLERS
        assert m4_handler_names <= set(get_handlers().keys())


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

    def test_spreadsheet_tools_in_collect_m6(self):
        """ST-057: spreadsheet×5 canonical tools in M6 registry 23/27."""
        names = {t["name"] for t in collect_office_tools()}
        assert SPREADSHEET_TOOL_NAMES <= names
        assert len(collect_office_tools()) == M6_CANONICAL
        assert len(get_handlers()) == M6_HANDLERS

    def test_no_pdf_legacy_aliases(self):
        handlers = get_handlers()
        assert "office_read_pdf" in handlers
        assert handlers["office_read_pdf"] is not handlers.get("office_read_document")

    def test_category_description_prefixes(self):
        """ADR-025: every canonical tool description uses its category prefix."""
        tools = collect_office_tools()
        assert len(tools) == len(CANONICAL_MODULES)
        for mod_path, tool_def in zip(CANONICAL_MODULES, tools):
            category = mod_path.split(".")[3]
            expected = CATEGORY_PREFIXES[category]
            name = tool_def["name"]
            assert tool_def["description"].startswith(expected), name

    def test_pdf_tools_use_pdf_prefix(self):
        tools = {t["name"]: t["description"] for t in collect_office_tools()}
        for name in PDF_TOOL_NAMES:
            assert tools[name].startswith("[PDF]"), name

    def test_final_counts(self):
        assert len(collect_office_tools()) == 23
        assert len(get_handlers()) == 27

    def test_registry_caches_handlers(self):
        first = get_handlers()
        second = get_handlers()
        assert first is not second
        assert first == second
        assert first["office_read_word"] is second["office_read_word"]
