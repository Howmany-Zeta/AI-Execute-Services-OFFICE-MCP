"""Builder script generation for office_edit_spreadsheet (edit body only)."""

from __future__ import annotations

import json

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.spreadsheet.schemas.edit_ops import EditOperation


def _js_value(value: object) -> str:
    """Serialize a Python value for ONLYOFFICE SetValue (valid JSON literal)."""
    return json.dumps(value)


def _js_rgb(hex_color: str) -> str:
    raw = hex_color.lstrip("#")
    red = int(raw[0:2], 16)
    green = int(raw[2:4], 16)
    blue = int(raw[4:6], 16)
    return f"Api.CreateColorFromRGB({red}, {green}, {blue})"


def _field_set(op: EditOperation, name: str) -> bool:
    return name in op.model_fields_set


def _emit_resolve_sheet(op: EditOperation) -> tuple[str, list[str]]:
    lines: list[str] = []
    if op.sheet_name:
        lines.append(f'var ws = Api.GetSheetByName("{escape_js(op.sheet_name)}");')
        return "ws", lines
    if op.sheet_index is not None:
        return f"Api.GetSheet({op.sheet_index})", lines
    return "Api.GetActiveSheet()", lines


def _emit_cell_style(rng: str, op: EditOperation) -> list[str]:
    lines: list[str] = []
    if _field_set(op, "number_format"):
        fmt = op.number_format or "General"
        lines.append(f'{rng}.SetNumberFormat("{escape_js(fmt)}");')
    if _field_set(op, "fill_color"):
        if op.fill_color:
            lines.append(f"{rng}.SetFillColor({_js_rgb(op.fill_color)});")
        else:
            lines.append(f"{rng}.SetFillColor(Api.CreateNoFill());")
    if _field_set(op, "bold"):
        lines.append(f"{rng}.SetBold({str(bool(op.bold)).lower()});")
    if _field_set(op, "italic"):
        lines.append(f"{rng}.SetItalic({str(bool(op.italic)).lower()});")
    if _field_set(op, "underline"):
        lines.append(f"{rng}.SetUnderline({str(bool(op.underline)).lower()});")
    if _field_set(op, "strike"):
        lines.append(f"{rng}.SetStrikeout({str(bool(op.strike)).lower()});")
    if _field_set(op, "font_name"):
        lines.append(f'{rng}.SetFontName("{escape_js(op.font_name or "")}");')
    if _field_set(op, "font_size_pt") and op.font_size_pt is not None:
        lines.append(f"{rng}.SetFontSize({float(op.font_size_pt)});")
    if _field_set(op, "font_color") and op.font_color:
        lines.append(f"{rng}.SetFontColor({_js_rgb(op.font_color)});")
    if _field_set(op, "align"):
        lines.append(f'{rng}.SetAlignHorizontal("{op.align or "left"}");')
    if _field_set(op, "vertical_align"):
        lines.append(f'{rng}.SetAlignVertical("{op.vertical_align or "bottom"}");')
    border_color = (
        _js_rgb(op.border_color)
        if _field_set(op, "border_color") and op.border_color
        else "Api.CreateColorFromRGB(0, 0, 0)"
    )
    for field_name, side in (
        ("border_left", "Left"),
        ("border_right", "Right"),
        ("border_top", "Top"),
        ("border_bottom", "Bottom"),
    ):
        if _field_set(op, field_name):
            style = (getattr(op, field_name) or "none").capitalize()
            lines.append(f'{rng}.SetBorders("{side}", "{style}", {border_color});')
    return lines


def _emit_clear_format(rng: str) -> list[str]:
    none = "Api.CreateColorFromRGB(0, 0, 0)"
    return [
        f'{rng}.SetNumberFormat("General");',
        f"{rng}.SetFillColor(Api.CreateNoFill());",
        f'{rng}.SetBorders("Left", "None", {none});',
        f'{rng}.SetBorders("Right", "None", {none});',
        f'{rng}.SetBorders("Top", "None", {none});',
        f'{rng}.SetBorders("Bottom", "None", {none});',
        f"{rng}.SetBold(false);",
        f"{rng}.SetItalic(false);",
        f"{rng}.SetUnderline(false);",
        f"{rng}.SetStrikeout(false);",
        f'{rng}.SetFontName("");',
        f'{rng}.SetAlignHorizontal("left");',
        f'{rng}.SetAlignVertical("bottom");',
    ]


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    ws, setup = _emit_resolve_sheet(op)
    lines.extend(setup)

    if op.op == "set_cell":
        lines.append(
            f'{ws}.GetRange("{escape_js(op.cell or "")}").SetValue({_js_value(op.value)});'
        )
    elif op.op == "set_range":
        val_json = json.dumps(op.values)
        lines.append(f'{ws}.GetRange("{escape_js(op.range or "")}").SetValue({val_json});')
    elif op.op == "clear_range":
        lines.append(f'{ws}.GetRange("{escape_js(op.range or "")}").SetValue("");')
    elif op.op == "clear_format":
        lines.append(f'var clearFmt = {ws}.GetRange("{escape_js(op.range or "")}");')
        lines.extend(_emit_clear_format("clearFmt"))
    elif op.op == "set_cell_style":
        addr = op.cell or op.range or ""
        lines.append(f'var styleRng = {ws}.GetRange("{escape_js(addr)}");')
        lines.extend(_emit_cell_style("styleRng", op))
    elif op.op == "set_column_width":
        col = (op.column or "").upper()
        lines.append(f'{ws}.GetRange("{col}:{col}").SetColumnWidth({float(op.width_pt)});')
    elif op.op == "set_row_height":
        lines.append(
            f'{ws}.GetRange("{op.sheet_row}:{op.sheet_row}").SetRowHeight({float(op.height_pt)});'
        )
    elif op.op == "set_formula":
        lines.append(f'{ws}.GetRange("{escape_js(op.cell or "")}").SetFormula("{escape_js(op.formula or "")}");')
    elif op.op == "insert_rows":
        at_0 = (op.at_row or 1) - 1
        lines.append(f"{ws}.InsertRows({at_0}, {op.count});")
        if op.values:
            val_json = json.dumps(op.values)
            num_cols = len(op.values[0])
            lines.append(f"var start = {ws}.GetRangeByNumber({at_0}, 0);")
            lines.append(f"var end = {ws}.GetRangeByNumber({at_0 + op.count - 1}, {num_cols - 1});")
            lines.append(f"{ws}.GetRange(start, end).SetValue({val_json});")
    elif op.op == "delete_rows":
        from_0 = (op.from_row or 1) - 1
        lines.append(f"{ws}.DeleteRows({from_0}, {op.count});")
    elif op.op == "add_sheet":
        # Match create builder: AddSheet() then SetName on new sheet index (ADR/create parity).
        lines.append("Api.AddSheet();")
        lines.append("var newWs = Api.GetSheet(Api.GetSheetsCount() - 1);")
        lines.append(f'newWs.SetName("{escape_js(op.name or "")}");')
    elif op.op == "delete_sheet":
        lines.append(f"{ws}.Delete();")
    elif op.op == "rename_sheet":
        lines.append(f'{ws}.SetName("{escape_js(op.new_name or "")}");')
    elif op.op == "copy_sheet":
        # Same pattern as merge builder: Copy relative to active sheet (ADR-035).
        lines.append(f"var copiedSheet = {ws}.Copy(Api.GetActiveSheet());")
        if op.new_name:
            lines.append(f'copiedSheet.SetName("{escape_js(op.new_name)}");')

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
