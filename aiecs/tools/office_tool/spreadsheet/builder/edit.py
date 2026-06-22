"""Builder script generation for office_edit_spreadsheet (edit body only)."""

from __future__ import annotations

import json

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import EditOperation


def _emit_resolve_sheet(op: EditOperation) -> tuple[str, list[str]]:
    lines: list[str] = []
    if op.sheet_name:
        lines.append(f'var ws = Api.GetSheetByName("{escape_js(op.sheet_name)}");')
        return "ws", lines
    if op.sheet_index is not None:
        return f"Api.GetSheet({op.sheet_index})", lines
    return "Api.GetActiveSheet()", lines


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    ws, setup = _emit_resolve_sheet(op)
    lines.extend(setup)

    if op.op == "set_cell":
        lines.append(f'{ws}.GetRange("{escape_js(op.cell or "")}").SetValue({repr(op.value)});')
    elif op.op == "set_range":
        val_json = json.dumps(op.values)
        lines.append(f'{ws}.GetRange("{escape_js(op.range or "")}").SetValue({val_json});')
    elif op.op == "clear_range":
        lines.append(f'{ws}.GetRange("{escape_js(op.range or "")}").Clear();')
    elif op.op == "set_formula":
        lines.append(f'{ws}.GetRange("{escape_js(op.cell or "")}").SetFormula("{escape_js(op.formula or "")}");')
    elif op.op == "insert_rows":
        at_0 = (op.at_row or 1) - 1
        lines.append(f"{ws}.InsertRows({at_0}, {op.count});")
    elif op.op == "delete_rows":
        from_0 = (op.from_row or 1) - 1
        lines.append(f"{ws}.DeleteRows({from_0}, {op.count});")
    elif op.op == "add_sheet":
        lines.append(f'Api.AddSheet("{escape_js(op.name or "")}");')
    elif op.op == "delete_sheet":
        lines.append(f"{ws}.Delete();")
    elif op.op == "rename_sheet":
        lines.append(f'{ws}.SetName("{escape_js(op.new_name or "")}");')
    elif op.op == "copy_sheet":
        lines.append(f"{ws}.Copy({ws});")

    return lines


def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    lines: list[str] = []
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
