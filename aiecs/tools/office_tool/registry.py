"""
Office tool registry — canonical list_tools and handler routing (ADR-024).

M3: collect_office_tools() = 8 (gateway×2 + word×6)
M4: collect_office_tools() = 13 (+ presentation×5)
M5: collect_office_tools() = 18 (+ spreadsheet×5)
M6: collect_office_tools() = 23 (+ pdf×5, FINAL)
M6: get_handlers() = 27 (23 canonical + 4 legacy, FINAL)
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

# M3 canonical: gateway×2 + word×6
# M4: + presentation×5 → 13 canonical
CANONICAL_MODULES: list[str] = [
    "aiecs.tools.office_tool.gateway.execute_builder",
    "aiecs.tools.office_tool.gateway.call_api",
    "aiecs.tools.office_tool.word.tools.read",
    "aiecs.tools.office_tool.word.tools.create",
    "aiecs.tools.office_tool.word.tools.edit",
    "aiecs.tools.office_tool.word.tools.merge",
    "aiecs.tools.office_tool.word.tools.template",
    "aiecs.tools.office_tool.word.tools.edit_script",
    "aiecs.tools.office_tool.presentation.tools.read",
    "aiecs.tools.office_tool.presentation.tools.create",
    "aiecs.tools.office_tool.presentation.tools.edit",
    "aiecs.tools.office_tool.presentation.tools.merge",
    "aiecs.tools.office_tool.presentation.tools.template",
    "aiecs.tools.office_tool.spreadsheet.tools.read",
    "aiecs.tools.office_tool.spreadsheet.tools.create",
    "aiecs.tools.office_tool.spreadsheet.tools.edit",
    "aiecs.tools.office_tool.spreadsheet.tools.merge",
    "aiecs.tools.office_tool.spreadsheet.tools.template",
    "aiecs.tools.office_tool.pdf.tools.read",
    "aiecs.tools.office_tool.pdf.tools.create",
    "aiecs.tools.office_tool.pdf.tools.edit",
    "aiecs.tools.office_tool.pdf.tools.merge",
    "aiecs.tools.office_tool.pdf.tools.fill_form",
]

# Legacy handlers only (ADR-024): not in collect_office_tools
LEGACY_MODULES: list[str] = [
    "aiecs.tools.office_tool.legacy.read_document",
    "aiecs.tools.office_tool.legacy.edit_document",
    "aiecs.tools.office_tool.legacy.merge_documents",
    "aiecs.tools.office_tool.legacy.apply_template",
]

OFFICE_TOOL_MODULES: list[str] = CANONICAL_MODULES + LEGACY_MODULES


def _load_canonical(mod_path: str) -> tuple[str, dict[str, Any], Callable[..., Any]]:
    mod = importlib.import_module(mod_path)
    return mod.TOOL_NAME, dict(mod.TOOL_DEF), mod.handler


def collect_office_tools() -> list[dict[str, Any]]:
    """Return canonical tool definitions for list_tools (ADR-024)."""
    tools: list[dict[str, Any]] = []
    for mod_path in CANONICAL_MODULES:
        _, tool_def, _ = _load_canonical(mod_path)
        tools.append(tool_def)
    return tools


def get_handlers() -> dict[str, Callable[..., Any]]:
    """Return all call_tool handlers including legacy aliases."""
    handlers: dict[str, Callable[..., Any]] = {}
    for mod_path in CANONICAL_MODULES:
        name, _, handler = _load_canonical(mod_path)
        handlers[name] = handler
    for mod_path in LEGACY_MODULES:
        mod = importlib.import_module(mod_path)
        for alias_name, alias_handler, _ in mod.LEGACY_ALIASES:
            handlers[alias_name] = alias_handler
    return handlers


def tool_count() -> int:
    """len(collect_office_tools()); M3=8, M6终态=23."""
    return len(collect_office_tools())


def canonical_count() -> int:
    """Same as tool_count for current milestone (ADR-026)."""
    return tool_count()
