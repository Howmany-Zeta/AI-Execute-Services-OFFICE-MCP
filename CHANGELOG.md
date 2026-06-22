# Changelog

All notable changes to the Office Tool MCP server.

## [Unreleased]

### M3 — Registry + Adapter (ADR-024, ADR-025, ADR-026)

- **`list_tools` now exposes 8 canonical tools** (gateway×2 + word×6) instead of 6 legacy tools.
- **Legacy tools hidden from `list_tools`**: `office_read_document`, `office_edit_document`, `office_merge_documents`, `office_apply_template`. They remain callable via `call_tool` during migration (12 registered handlers).
- **New registry** (`aiecs/tools/office_tool/registry.py`): explicit module list; no pkgutil scanning.
- **Gateway tools** moved to `aiecs/tools/office_tool/gateway/` with `[Gateway]` description prefix.
- **Word canonical tools** registered with `[Word]` description prefix.
- **Health endpoint** adds `canonical_count` (8) and `registered_handler_count` (12).
- See [docs/LEGACY_TOOL_MIGRATION.md](docs/LEGACY_TOOL_MIGRATION.md) for migration guide.

### M4 — Presentation vertical (ADR-016, ADR-025)

- **Five new canonical tools**: `office_read_presentation`, `office_create_presentation`, `office_edit_presentation`, `office_merge_presentations`, `office_apply_template_presentation`.
- **`list_tools` now exposes 13 canonical tools** (gateway×2 + word×6 + presentation×5).
- **`registered_handler_count` is 17** (13 canonical + 4 legacy).
- Presentation tools use `[Presentation]` description prefix; layout enum validation (ADR-016).
- `parse_txt_to_structure` moved to `presentation/parser/txt.py` (legacy import path preserved via `html_parser` shim).

### M5 — Spreadsheet vertical (ADR-013, ADR-014, ADR-015)

- **Five new canonical tools**: `office_read_spreadsheet`, `office_create_spreadsheet`, `office_edit_spreadsheet`, `office_merge_spreadsheets`, `office_apply_template_spreadsheet`.
- **`list_tools` now exposes 18 canonical tools** (gateway×2 + word×6 + presentation×5 + spreadsheet×5).
- **`registered_handler_count` is 22** (18 canonical + 4 legacy).
- Spreadsheet tools use `[Spreadsheet]` prefix; A1/range notation (ADR-015); template explicit `Sheet!A1` + `{{key}}` (ADR-014).
- `parse_csv_to_structure` moved to `spreadsheet/parser/csv.py` (legacy import preserved via `html_parser` shim).
- `probe_ds_capabilities.py`: GetSheetsCount gate skeleton for fine read E2E skip (ADR-021).

### M6 — PDF vertical (ADR-017–020, ADR-030) — FINAL registry

- **Five new canonical tools**: `office_read_pdf`, `office_create_pdf`, `office_edit_pdf`, `office_merge_pdfs`, `office_fill_pdf_form`.
- **No `office_apply_template_pdf`** (ADR-030); form filling via `office_fill_pdf_form` only.
- **`list_tools` FINAL: 23 canonical tools**; **`registered_handler_count` FINAL: 27**.
- PDF tools use `[PDF]` prefix; coarse read page boundaries (ADR-020); merge builder default + explicit conversion engine (ADR-018).
- `create_mode` native/via_docx with no auto fallback (ADR-017).

- **`core/` freeze** begins after M3 merge — bugfix-only changes.

### M7 — Documentation & Gate G5

- **README.md**: 23 canonical tools, architecture tree, E2E commands with category markers.
- **Plan.md**: M0–M7 milestone status complete.
- **LLM guides** (OT-129) and **UPGRADE §8/§7.1 status tables** (OT-130) synced with registry.
- **`probe_ds_capabilities.py`**: full Builder smoke for `GetSheetsCount` and PDF native create; `ds_capabilities` session fixture in conftest.
- **Gate G5**: health `tool_count`/`canonical_count` == 23, `registered_handler_count` == 27; docs match registry.
- **Shims retained** (ADR-022); legacy tools hidden from `list_tools`, no `[Legacy]` prefix (ADR-024/025).

### ADR-022 breaking — Remove import shims

- **Deleted** flat re-export shims: `conversion_output`, `html_parser`, `storage`, `storage_paths`, `object_fetch`, `docbuilder_script`, `source_resolver`, `execute_builder`, `call_api`, `read_document`, `edit_document`, `merge_document`, `apply_template`.
- **`office_tool.__init__`** now imports from `gateway.*` and `legacy.*` only.
- **Import canonical paths**: `core.categories`, `core.storage`, `word.parser.html`, `presentation.parser.txt`, `spreadsheet.parser.csv`, etc.

- **`test_e2e_office_tools.py`**: gateway + legacy smoke; category E2E in `word/`/`presentation/`/`spreadsheet/`/`pdf/`.
- **OT-138 FINAL**: adapter, OpenAI format, FastMCP, integration assert 23 canonical / no legacy in `list_tools`.
- **`.github/workflows/ci-office-mcp.yml`**: unit tests on push/PR; optional E2E via `workflow_dispatch` + DS secrets.
- **README §10.4**: per-PR regression checklist documented.
