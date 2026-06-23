"""
Parse ONLYOFFICE workbook sidecar JSON into sheets[] (ADR-013).
"""

from __future__ import annotations

import json
import re
from typing import Any


def workbook_sidecar_extract_body(*, include_formulas: bool = False) -> str:
    """Builder sidecar JS; ADR-031: optional GetFormula() branch when include_formulas."""
    cell_read = (
        "        var f = used.GetFormula(r, c);\n"
        "        row.push(f && f.length > 0 ? f : used.GetValue(r, c));"
        if include_formulas
        else "        row.push(used.GetValue(r, c));"
    )
    return f"""var out = {{ sheets: [] }};
var count = Api.GetSheetsCount();
for (var i = 0; i < count; i++) {{
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  var used = ws.GetUsedRange();
  var rows = [];
  var usedAddr = null;
  if (used) {{
    var rowCount = used.GetRows().length;
    var colCount = used.GetCols().length;
    for (var r = 0; r < rowCount; r++) {{
      var row = [];
      for (var c = 0; c < colCount; c++) {{
{cell_read}
      }}
      rows.push(row);
    }}
    usedAddr = used.GetAddress();
  }}
  out.sheets.push({{
    sheet_index: i,
    name: name,
    rows: rows,
    used_range: usedAddr,
    row_count: rows.length,
    col_count: rows.length > 0 ? rows[0].length : 0
  }});
}}
var jsonStr = JSON.stringify(out);"""


WORKBOOK_SIDECAR_EXTRACT_BODY = workbook_sidecar_extract_body(include_formulas=False)


def parse_a1(cell: str) -> tuple[int, int]:
    """A1 notation → (row_0based, col_0based)."""
    cell = (cell or "").strip().upper()
    match = re.match(r"^([A-Z]+)(\d+)$", cell)
    if not match:
        raise ValueError(f"Invalid A1 cell: {cell!r}")
    col_letters, row_num = match.group(1), int(match.group(2))
    col = 0
    for ch in col_letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return row_num - 1, col - 1


def parse_range(range_str: str) -> tuple[int, int, int, int]:
    """B2:D5 → (r0, c0, r1, c1) 0-based inclusive."""
    parts = (range_str or "").strip().upper().split(":")
    if len(parts) == 1:
        r, c = parse_a1(parts[0])
        return r, c, r, c
    r0, c0 = parse_a1(parts[0])
    r1, c1 = parse_a1(parts[1])
    return r0, c0, r1, c1


def _col_letter(col_index: int) -> str:
    """0-based column index to Excel letter (0=A)."""
    result = ""
    n = col_index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result or "A"


def _format_a1_range(r0: int, c0: int, r1: int, c1: int) -> str:
    if r0 == r1 and c0 == c1:
        return f"{_col_letter(c0)}{r0 + 1}"
    return f"{_col_letter(c0)}{r0 + 1}:{_col_letter(c1)}{r1 + 1}"


def _set_headers_from_rows(sheet: dict[str, Any]) -> None:
    rows = sheet.get("rows") or []
    if rows:
        sheet["headers"] = list(rows[0])
    else:
        sheet.pop("headers", None)


def _normalize_sheet(raw: dict[str, Any], index: int) -> dict[str, Any]:
    rows = raw.get("rows") or []
    sheet: dict[str, Any] = {
        "sheet_index": raw.get("sheet_index", index),
        "name": raw.get("name") or f"Sheet{index + 1}",
        "rows": rows,
        "row_count": raw.get("row_count", len(rows)),
        "col_count": raw.get("col_count", max((len(r) for r in rows), default=0)),
    }
    if raw.get("used_range"):
        sheet["used_range"] = raw["used_range"]
    elif "used_range" in raw and raw["used_range"] is None:
        sheet.pop("used_range", None)
    _set_headers_from_rows(sheet)
    if raw.get("formulas"):
        sheet["formulas"] = raw["formulas"]
    return sheet


def parse_workbook_json(raw: dict | str) -> list[dict[str, Any]]:
    """Sidecar JSON { sheets: [...] } → normalized sheets[] (ADR-033 headers)."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    sheets_raw = data.get("sheets") if isinstance(data, dict) else data
    if not isinstance(sheets_raw, list):
        return []

    return [_normalize_sheet(s, i) for i, s in enumerate(sheets_raw) if isinstance(s, dict)]


def filter_sheet_names(sheets: list[dict[str, Any]], names: list[str] | None) -> list[dict[str, Any]]:
    if not names:
        return sheets
    allowed = set(names)
    return [s for s in sheets if s.get("name") in allowed]


def apply_range_filter(
    sheets: list[dict[str, Any]], range_str: str | None
) -> list[dict[str, Any]]:
    """ADR-034: clip each sheet to A1 range; update used_range and headers."""
    if not range_str:
        return sheets
    r0, c0, r1, c1 = parse_range(range_str)
    if r1 < r0:
        r0, r1 = r1, r0
    if c1 < c0:
        c0, c1 = c1, c0

    out: list[dict[str, Any]] = []
    for sheet in sheets:
        s = dict(sheet)
        rows = s.get("rows") or []
        clipped: list[list[Any]] = []
        for r in range(r0, r1 + 1):
            if r < 0 or r >= len(rows):
                continue
            row = rows[r]
            clipped.append(list(row[c0 : c1 + 1]) if c0 < len(row) else [])
        s["rows"] = clipped
        s["row_count"] = len(clipped)
        s["col_count"] = max((len(r) for r in clipped), default=0)
        if clipped:
            s["used_range"] = _format_a1_range(r0, c0, r1, c1)
        else:
            s.pop("used_range", None)
        _set_headers_from_rows(s)
        out.append(s)
    return out


def apply_max_rows(sheets: list[dict[str, Any]], max_rows: int | None) -> tuple[list[dict[str, Any]], bool]:
    if max_rows is None:
        return sheets, False
    truncated = False
    out: list[dict[str, Any]] = []
    for sheet in sheets:
        s = dict(sheet)
        rows = s.get("rows") or []
        if len(rows) > max_rows:
            s["rows"] = rows[:max_rows]
            s["row_count"] = max_rows
            truncated = True
        _set_headers_from_rows(s)
        out.append(s)
    return out, truncated


def sheets_to_outline(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sheet_index": s.get("sheet_index", i),
            "name": s.get("name", ""),
            "used_range": s.get("used_range"),
        }
        for i, s in enumerate(sheets)
    ]


def sheets_to_text(sheets: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for sheet in sheets:
        name = sheet.get("name", "Sheet")
        parts.append(f"--- {name} ---")
        for row in sheet.get("rows") or []:
            parts.append("\t".join(str(c) for c in row))
    return "\n".join(parts)
