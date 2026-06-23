"""Builder script generation for office_apply_template_spreadsheet (ADR-014)."""

from __future__ import annotations

import json
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


def _is_explicit_address(key: str) -> bool:
    key_str = str(key)
    return "!" in key_str or bool(re.match(r"^[A-Z]+\d+$", key_str.upper()))


def _js_literal(value: Any) -> str:
    return json.dumps(value)


def build_template_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    Phase 1: explicit Sheet!A1 addresses via SetValue; record {{key}} in cell as consumed.
    Phase 2: remaining {{key}} placeholders via SearchAndReplace in used ranges (ADR-039 dedup).
    """
    explicit: dict[str, Any] = {}
    placeholders: dict[str, Any] = {}
    for key, value in data.items():
        key_str = str(key)
        if key_str.startswith("{{") and key_str.endswith("}}"):
            placeholders[key_str[2:-2]] = value
        elif _is_explicit_address(key_str):
            explicit[key_str] = value
        elif key_str.startswith("{{") or "{{" in key_str:
            placeholders[key_str.strip("{}")] = value
        else:
            placeholders[key_str] = value

    lines = [
        "var count = Api.GetSheetsCount();",
        "var consumed = {};",
        "",
    ]

    for ref, value in explicit.items():
        sheet_name, cell = split_sheet_ref(ref)
        if sheet_name:
            lines.append(f'var ws = Api.GetSheetByName("{escape_js(sheet_name)}");')
            lines.append(f'var rng = ws.GetRange("{escape_js(cell)}");')
            lines.append("var oldVal = rng.GetValue();")
            lines.append(
                'if (oldVal && typeof oldVal === "string") {'
            )
            lines.append(
                '  var matches = oldVal.match(/\\{\\{([^}]+)\\}\\}/g);'
            )
            lines.append("  if (matches) {")
            lines.append("    for (var mi = 0; mi < matches.length; mi++) {")
            lines.append(
                '      consumed[matches[mi].slice(2, -2)] = true;'
            )
            lines.append("    }")
            lines.append("  }")
            lines.append("}")
            lines.append(f"rng.SetValue({_js_literal(value)});")
        else:
            lines.append("var ws = Api.GetActiveSheet();")
            lines.append(f'ws.GetRange("{escape_js(cell)}").SetValue({_js_literal(value)});')

    if placeholders:
        lines.append("")
        lines.append("for (var i = 0; i < count; i++) {")
        lines.append("  var ws = Api.GetSheet(i);")
        lines.append("  var used = ws.GetUsedRange();")
        lines.append("  if (!used) continue;")
        for key, value in placeholders.items():
            search = "{{" + key + "}}"
            lines.append(f"  if (!consumed[{json.dumps(key)}]) {{")
            lines.append(
                f'    used.SearchAndReplace("{escape_js(search)}", "{escape_js(str(value))}");'
            )
            lines.append("  }")
        lines.append("}")

    return "\n".join(lines)
