"""Builder script generation for office_create_spreadsheet."""

from __future__ import annotations

import json

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.spreadsheet.schemas.workbook_spec import (
    SheetSpec,
    SpreadsheetCreateOptions,
)


def _emit_sheet_data(ws_var: str, rows: list[list]) -> list[str]:
    lines: list[str] = []
    if not rows:
        return lines
    data_json = json.dumps(rows)
    lines.append(f"var data = {data_json};")
    lines.append(f"var start = {ws_var}.GetRangeByNumber(0, 0);")
    lines.append(f"var end = {ws_var}.GetRangeByNumber(data.length - 1, data[0].length - 1);")
    lines.append(f"{ws_var}.GetRange(start, end).SetValue(data);")
    return lines


def build_create_script(
    sheets: list[SheetSpec],
    *,
    output_ext: str,
    options: SpreadsheetCreateOptions,
) -> str:
    lines = [f'builder.CreateFile("{output_ext}");']
    for i, spec in enumerate(sheets):
        if i == 0:
            lines.append("var ws = Api.GetActiveSheet();")
        else:
            lines.append("Api.AddSheet();")
            lines.append(f"var ws = Api.GetSheet({i});")
        lines.append(f'ws.SetName("{escape_js(spec.name)}");')
        lines.extend(_emit_sheet_data("ws", spec.rows))
    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
