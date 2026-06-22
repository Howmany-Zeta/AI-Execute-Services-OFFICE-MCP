"""Builder script generation for office_apply_template_spreadsheet (ADR-014)."""

from __future__ import annotations

import re
from typing import Any

from aiecs.tools.office_tool.core.builder_js import escape_js


def split_sheet_ref(ref: str) -> tuple[str | None, str]:
    """'Summary!B2' → ('Summary', 'B2'); 'B2' → (None, 'B2')."""
    ref = (ref or "").strip()
    if "!" in ref:
        sheet, cell = ref.split("!", 1)
        return sheet.strip(), cell.strip()
    return None, ref


def build_template_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    Phase 1: explicit Sheet!A1 addresses via SetValue.
    Phase 2: remaining {{key}} placeholders via SearchAndReplace in used ranges.
    """
    explicit: dict[str, Any] = {}
    placeholders: dict[str, Any] = {}
    for key, value in data.items():
        key_str = str(key)
        if key_str.startswith("{{") and key_str.endswith("}}"):
            placeholders[key_str[2:-2]] = value
        elif "!" in key_str or re.match(r"^[A-Z]+\d+$", key_str.upper()):
            explicit[key_str] = value
        elif key_str.startswith("{{") or "{{" in key_str:
            placeholders[key_str.strip("{}")] = value
        else:
            placeholders[key_str] = value

    lines = ["var count = Api.GetSheetsCount();", ""]

    for ref, value in explicit.items():
        sheet_name, cell = split_sheet_ref(ref)
        if sheet_name:
            lines.append(f'var ws = Api.GetSheetByName("{escape_js(sheet_name)}");')
        else:
            lines.append("var ws = Api.GetActiveSheet();")
        lines.append(f'ws.GetRange("{escape_js(cell)}").SetValue({repr(value)});')

    if placeholders:
        lines.append("")
        lines.append("for (var i = 0; i < count; i++) {")
        lines.append("  var ws = Api.GetSheet(i);")
        lines.append("  var used = ws.GetUsedRange();")
        lines.append("  if (!used) continue;")
        for key, value in placeholders.items():
            search = "{{" + key + "}}"
            lines.append(
                f'  used.SearchAndReplace("{escape_js(search)}", "{escape_js(str(value))}");'
            )
        lines.append("}")

    return "\n".join(lines)
