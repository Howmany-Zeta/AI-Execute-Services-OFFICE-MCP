"""
Parse ONLYOFFICE workbook sidecar JSON into sheets[] (ADR-013).
"""

from __future__ import annotations

import json
import re
from typing import Any


WORKBOOK_SIDECAR_EXTRACT_BODY = """var out = { sheets: [] };
var count = Api.GetSheetsCount();
for (var i = 0; i < count; i++) {
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  var used = ws.GetUsedRange();
  var rows = [];
  var usedAddr = null;
  if (used) {
    var rowCount = used.GetRows().length;
    var colCount = used.GetCols().length;
    for (var r = 0; r < rowCount; r++) {
      var row = [];
      for (var c = 0; c < colCount; c++) {
        row.push(used.GetValue(r, c));
      }
      rows.push(row);
    }
    usedAddr = used.GetAddress();
  }
  out.sheets.push({
    sheet_index: i,
    name: name,
    rows: rows,
    used_range: usedAddr,
    row_count: rows.length,
    col_count: rows.length > 0 ? rows[0].length : 0
  });
}
var jsonStr = JSON.stringify(out);"""


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
    if raw.get("headers"):
        sheet["headers"] = raw["headers"]
    if raw.get("formulas"):
        sheet["formulas"] = raw["formulas"]
    return sheet


def parse_workbook_json(raw: dict | str) -> list[dict[str, Any]]:
    """Sidecar JSON { sheets: [...] } → normalized sheets[]."""
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
