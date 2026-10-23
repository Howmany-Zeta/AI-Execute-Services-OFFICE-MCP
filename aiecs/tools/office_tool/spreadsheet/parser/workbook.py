"""
Parse ONLYOFFICE workbook sidecar JSON into sheets[] (ADR-013).
"""

from __future__ import annotations

import json
import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import sanitize_text

ALIGN_H = frozenset({"left", "center", "right", "justify"})
ALIGN_V = frozenset({"top", "center", "bottom"})
BORDER_STYLES = frozenset({"none", "thin", "medium", "thick"})
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_RANGE_HELPERS = r"""
function _colLetter(idx) {
  var result = "";
  var n = idx + 1;
  while (n > 0) {
    var rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result || "A";
}
function _parseA1(addr) {
  var s = String(addr || "").replace(/\$/g, "");
  var bang = s.lastIndexOf("!");
  if (bang >= 0) s = s.slice(bang + 1);
  var m = s.toUpperCase().match(/^([A-Z]+)(\d+)/);
  if (!m) return [0, 0];
  var col = 0;
  for (var i = 0; i < m[1].length; i++) col = col * 26 + (m[1].charCodeAt(i) - 64);
  return [parseInt(m[2], 10) - 1, col - 1];
}
function _usedDims(used) {
  var addr = null;
  try { addr = used.GetAddress(); } catch (e) { addr = null; }
  var rowCount = 0, colCount = 0, originR = 0, originC = 0;
  if (addr) {
    var s = String(addr).replace(/\$/g, "");
    var bang = s.lastIndexOf("!");
    if (bang >= 0) s = s.slice(bang + 1);
    var parts = s.split(":");
    var a = _parseA1(parts[0]);
    var b = parts.length > 1 ? _parseA1(parts[1]) : a;
    originR = Math.min(a[0], b[0]);
    originC = Math.min(a[1], b[1]);
    rowCount = Math.abs(b[0] - a[0]) + 1;
    colCount = Math.abs(b[1] - a[1]) + 1;
  }
  if (!rowCount) {
    try { var gr = used.GetRows(); if (gr && gr.length) rowCount = gr.length; } catch (e2) {}
  }
  if (!colCount) {
    try { var gc = used.GetCols(); if (gc && gc.length) colCount = gc.length; } catch (e3) {}
  }
  if (!rowCount || !colCount) {
    originR = 0;
    originC = 0;
    if (!rowCount) rowCount = 64;
    if (!colCount) colCount = 26;
    if (!addr) addr = "A1:" + _colLetter(colCount - 1) + String(rowCount);
  }
  return { addr: addr, rowCount: rowCount, colCount: colCount, originR: originR, originC: originC };
}
function _isGrid(v) {
  return v && typeof v === "object" && typeof v.length === "number";
}
function _cellScalar(v) {
  if (v === undefined || v === null) return "";
  if (_isGrid(v)) return "";
  return v;
}
function _readCell(ws, used, originR, originC, r, c) {
  var addr = _colLetter(originC + c) + String(originR + r + 1);
  var cellRng = null;
  try { cellRng = ws.GetRange(addr); } catch (e) { cellRng = null; }
  var v = undefined;
  if (cellRng && typeof cellRng.GetValue === "function") {
    try { v = cellRng.GetValue(); } catch (eV) { v = undefined; }
  }
  if (_isGrid(v)) v = undefined;
  if (v === undefined && used && typeof used.GetValue === "function") {
    try { v = used.GetValue(r, c); } catch (eU) { v = undefined; }
    if (_isGrid(v)) v = undefined;
  }
  return _cellScalar(v);
}
"""

_FORMULA_HELPERS = r"""
function _readFormula(ws, used, originR, originC, r, c) {
  var addr = _colLetter(originC + c) + String(originR + r + 1);
  var cellRng = null;
  try { cellRng = ws.GetRange(addr); } catch (e) { cellRng = null; }
  var f = undefined;
  if (cellRng && typeof cellRng.GetFormula === "function") {
    try { f = cellRng.GetFormula(); } catch (eF) { f = undefined; }
  }
  if (_isGrid(f)) f = undefined;
  if ((f === undefined || f === null || f === "") && used && typeof used.GetFormula === "function") {
    try { f = used.GetFormula(r, c); } catch (eU) { f = undefined; }
    if (_isGrid(f)) f = undefined;
  }
  if (f !== undefined && f !== null && String(f).length > 0) return f;
  return _readCell(ws, used, originR, originC, r, c);
}
"""

_SHEET_COUNT_JS = """var count = 0;
if (typeof Api.GetSheetsCount === "function") {
  count = Api.GetSheetsCount();
} else if (typeof Api.GetSheets === "function") {
  try { var _all = Api.GetSheets(); count = _all ? _all.length : 0; } catch (eCount) { count = 0; }
}
if (!count) {
  for (var _si = 0; _si < 256; _si++) {
    var _probe = null;
    try { _probe = Api.GetSheet(_si); } catch (eProbe) { _probe = null; }
    if (!_probe) break;
    count++;
  }
}
"""

_STYLE_HELPERS = r"""
function _hex2(n) {
  var s = Math.max(0, Math.min(255, Math.round(Number(n) || 0))).toString(16);
  return s.length < 2 ? "0" + s : s;
}
function _safeCall(obj, name) {
  if (!obj || typeof obj[name] !== "function") return undefined;
  try { return obj[name](); } catch (e) { return undefined; }
}
function _colorToHex(color) {
  if (color === undefined || color === null) return "";
  if (typeof color === "string") {
    var t = color.replace(/^\s+|\s+$/g, "");
    if (!t) return "";
    var low = t.toLowerCase();
    if (low === "none" || low === "auto") return "";
    if (t.charAt(0) === "#" && t.length === 7) return t.toUpperCase();
    return "";
  }
  if (typeof color === "number") {
    var n = color >>> 0;
    return "#" + _hex2((n >> 16) & 255) + _hex2((n >> 8) & 255) + _hex2(n & 255);
  }
  var rgb = _safeCall(color, "GetRGB");
  if (typeof rgb === "number") {
    return "#" + _hex2((rgb >> 16) & 255) + _hex2((rgb >> 8) & 255) + _hex2(rgb & 255);
  }
  var r = color.r !== undefined ? color.r : (color.R !== undefined ? color.R : _safeCall(color, "GetR"));
  var g = color.g !== undefined ? color.g : (color.G !== undefined ? color.G : _safeCall(color, "GetG"));
  var b = color.b !== undefined ? color.b : (color.B !== undefined ? color.B : _safeCall(color, "GetB"));
  if (r !== undefined && g !== undefined && b !== undefined) {
    return "#" + _hex2(r) + _hex2(g) + _hex2(b);
  }
  return "";
}
function _boolish(v) {
  if (v === undefined || v === null) return false;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  var s = String(v).toLowerCase();
  return s === "true" || s === "single" || s === "yes";
}
function _colLetter(idx) {
  var result = "";
  var n = idx + 1;
  while (n > 0) {
    var rem = (n - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    n = Math.floor((n - 1) / 26);
  }
  return result || "A";
}
function _parseA1(addr) {
  var s = String(addr || "").replace(/\$/g, "");
  var bang = s.lastIndexOf("!");
  if (bang >= 0) s = s.slice(bang + 1);
  var m = s.match(/^([A-Z]+)(\d+)/);
  if (!m) return [0, 0];
  var col = 0;
  for (var i = 0; i < m[1].length; i++) col = col * 26 + (m[1].charCodeAt(i) - 64);
  return [parseInt(m[2], 10) - 1, col - 1];
}
function _alignH(v) {
  if (v === undefined || v === null) return "left";
  var s = String(v).toLowerCase();
  if (s.indexOf("center") >= 0) return "center";
  if (s.indexOf("right") >= 0) return "right";
  if (s.indexOf("justify") >= 0) return "justify";
  return "left";
}
function _alignV(v) {
  if (v === undefined || v === null) return "bottom";
  var s = String(v).toLowerCase();
  if (s.indexOf("top") >= 0) return "top";
  if (s.indexOf("center") >= 0) return "center";
  return "bottom";
}
function _isDefaultStyle(st) {
  return !st.number_format && !st.fill_color
    && st.border_left === "none" && st.border_right === "none"
    && st.border_top === "none" && st.border_bottom === "none"
    && !st.border_color
    && !st.bold && !st.italic && !st.underline && !st.strike
    && !st.font_name && st.font_size_pt === null
    && !st.font_color
    && st.align === "left" && st.vertical_align === "bottom";
}
function _extractCellStyle(cell, addr) {
  var nf = _safeCall(cell, "GetNumberFormat");
  var number_format = "";
  if (nf !== undefined && nf !== null) {
    var nfs = String(nf);
    if (nfs && nfs.toLowerCase() !== "general") number_format = nfs;
  }
  var size = _safeCall(cell, "GetFontSize");
  var font = _safeCall(cell, "GetFontName");
  if (font === undefined) font = _safeCall(cell, "GetFontFamily");
  var strike = _safeCall(cell, "GetStrikeout");
  if (strike === undefined) strike = _safeCall(cell, "GetStrike");
  var st = {
    cell: addr,
    number_format: number_format,
    fill_color: _colorToHex(_safeCall(cell, "GetFillColor")),
    border_left: "none",
    border_right: "none",
    border_top: "none",
    border_bottom: "none",
    border_color: "",
    bold: _boolish(_safeCall(cell, "GetBold")),
    italic: _boolish(_safeCall(cell, "GetItalic")),
    underline: _boolish(_safeCall(cell, "GetUnderline")),
    strike: _boolish(strike),
    font_name: font ? String(font) : "",
    font_size_pt: (typeof size === "number") ? size : null,
    font_color: _colorToHex(_safeCall(cell, "GetFontColor") || _safeCall(cell, "GetColor")),
    align: _alignH(_safeCall(cell, "GetAlignHorizontal")),
    vertical_align: _alignV(_safeCall(cell, "GetAlignVertical"))
  };
  if (_isDefaultStyle(st)) return null;
  return st;
}
"""


def _sheet_window_js(range_str: str | None) -> str:
    """Prefer an explicit A1 window so huge GetUsedRange sheets do not 504."""
    if range_str:
        r0, c0, r1, c1 = parse_range(range_str)
        if r1 < r0:
            r0, r1 = r1, r0
        if c1 < c0:
            c0, c1 = c1, c0
        a1 = json.dumps(_format_a1_range(r0, c0, r1, c1))
        return (
            f"  var used = null;\n"
            f"  try {{ used = ws.GetRange({a1}); }} catch (eWin) {{ used = null; }}\n"
            f"  var usedAddr = {a1};\n"
            f"  var rowCount = {r1 - r0 + 1};\n"
            f"  var colCount = {c1 - c0 + 1};\n"
            f"  var originR = {r0};\n"
            f"  var originC = {c0};\n"
            "  if (!used) {\n"
            "    used = ws.GetUsedRange();\n"
            "    if (used) {\n"
            "      var dims = _usedDims(used);\n"
            "      usedAddr = dims.addr;\n"
            "      rowCount = dims.rowCount;\n"
            "      colCount = dims.colCount;\n"
            "      originR = dims.originR;\n"
            "      originC = dims.originC;\n"
            "    }\n"
            "  }\n"
        )
    return (
        "  var used = ws.GetUsedRange();\n"
        "  if (!used) {\n"
        "    try { used = ws.GetRange(\"A1:Z64\"); } catch (eUsed) { used = null; }\n"
        "  }\n"
        "  var usedAddr = null;\n"
        "  var rowCount = 0, colCount = 0, originR = 0, originC = 0;\n"
        "  if (used) {\n"
        "    var dims = _usedDims(used);\n"
        "    usedAddr = dims.addr;\n"
        "    rowCount = dims.rowCount;\n"
        "    colCount = dims.colCount;\n"
        "    originR = dims.originR;\n"
        "    originC = dims.originC;\n"
        "  }\n"
    )


def workbook_sidecar_extract_body(
    *,
    include_formulas: bool = False,
    include_styles: bool = False,
    max_rows: int | None = None,
    max_cols: int | None = None,
    max_output_bytes: int | None = None,
    range: str | None = None,
) -> str:
    """Builder sidecar JS; ADR-031: optional GetFormula() branch when include_formulas."""
    cell_read = (
        "        row.push(_readFormula(ws, used, originR, originC, r, c));"
        if include_formulas
        else "        row.push(_readCell(ws, used, originR, originC, r, c));"
    )
    style_cell = (
        "        var addr = _colLetter(originC + c) + String(originR + r + 1);\n"
        "        var cellObj = ws.GetRange(addr);\n"
        "        var st = _extractCellStyle(cellObj, addr);\n"
        "        if (st) cell_styles.push(st);\n"
        if include_styles
        else ""
    )
    if (
        max_rows is None
        and max_cols is None
        and max_output_bytes is None
        and not include_styles
        and not range
    ):
        helpers = _RANGE_HELPERS + (_FORMULA_HELPERS if include_formulas else "")
        return f"""{helpers}var out = {{ sheets: [] }};
{_SHEET_COUNT_JS}for (var i = 0; i < count; i++) {{
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  if (name === "_office_sidecar") continue;
  var used = ws.GetUsedRange();
  if (!used) {{
    try {{ used = ws.GetRange("A1:Z64"); }} catch (eUsed) {{ used = null; }}
  }}
  var rows = [];
  var usedAddr = null;
  if (used) {{
    var dims = _usedDims(used);
    usedAddr = dims.addr;
    var rowCount = dims.rowCount;
    var colCount = dims.colCount;
    var originR = dims.originR;
    var originC = dims.originC;
    if (colCount > 256) colCount = 256;
    if (rowCount > 2000) rowCount = 2000;
    for (var r = 0; r < rowCount; r++) {{
      var row = [];
      for (var c = 0; c < colCount; c++) {{
{cell_read}
      }}
      rows.push(row);
    }}
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

    if max_rows is not None and max_cols is None and not range:
        max_cols = 32
    window_js = _sheet_window_js(range)
    row_guard = (
        f"      if (r >= {int(max_rows)}) {{ truncated = truncated || 'rows'; break; }}\n"
        if max_rows is not None
        else ""
    )
    col_guard = (
        f"        if (c >= {int(max_cols)}) {{ truncated = truncated || 'columns'; break; }}\n"
        if max_cols is not None
        else ""
    )
    if max_output_bytes is not None:
        out_init = f"var outBytes = 2;\nvar maxOut = {int(max_output_bytes)};\n"
        out_after_cell = (
            "        var cellVal = row[row.length - 1];\n"
            "        outBytes += (cellVal === null || cellVal === undefined) ? 2 : String(cellVal).length + 2;\n"
            "        if (st) outBytes += 80;\n"
            if include_styles
            else (
                "        var cellVal = row[row.length - 1];\n"
                "        outBytes += (cellVal === null || cellVal === undefined) ? 2 : String(cellVal).length + 2;\n"
            )
        )
        out_after_cell += "        if (outBytes > maxOut) { truncated = 'output'; break; }\n"
        out_sheet_break = "  if (truncated === 'output') break;\n"
    else:
        out_init = ""
        out_after_cell = ""
        out_sheet_break = ""
    style_prefix = (
        (_STYLE_HELPERS if include_styles else "")
        + _RANGE_HELPERS
        + (_FORMULA_HELPERS if include_formulas else "")
    )
    style_vars = (
        "  var cell_styles = [];\n  var column_widths = [];\n  var row_heights = [];\n"
        if include_styles
        else ""
    )
    origin_init = (
        "    usedAddr = used.GetAddress();\n"
        "    var origin = _parseA1(usedAddr);\n"
        "    var originR = origin[0];\n"
        "    var originC = origin[1];\n"
        if include_styles
        else ""
    )
    used_addr_after = "" if include_styles else "    usedAddr = used.GetAddress();\n"
    style_sizes = (
        "    for (var wc = 0; wc < colCount; wc++) {{\n"
        "      var colL = _colLetter(originC + wc);\n"
        "      var colRng = ws.GetRange(colL + ':' + colL);\n"
        "      var w = _safeCall(colRng, 'GetColumnWidth');\n"
        "      if (typeof w === 'number') column_widths.push({{ column: colL, width_pt: w }});\n"
        "    }}\n"
        "    for (var hr = 0; hr < rows.length; hr++) {{\n"
        "      var sheetRow = originR + hr + 1;\n"
        "      var rowRng = ws.GetRange(String(sheetRow) + ':' + String(sheetRow));\n"
        "      var h = _safeCall(rowRng, 'GetRowHeight');\n"
        "      if (typeof h === 'number') row_heights.push({{ sheet_row: sheetRow, height_pt: h }});\n"
        "    }}\n"
        if include_styles
        else ""
    )
    style_fields = (
        ",\n    cell_styles: cell_styles,\n    column_widths: column_widths,\n    row_heights: row_heights"
        if include_styles
        else ""
    )
    return (
        style_prefix
        + f"""var out = {{ sheets: [] }};
{_SHEET_COUNT_JS}var truncated = null;
{out_init}for (var i = 0; i < count; i++) {{
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  if (name === "_office_sidecar") continue;
  var rows = [];
  var sheetTrunc = null;
{window_js}{style_vars}  if (used) {{
    if (colCount > 256) {{ truncated = truncated || 'columns'; colCount = 256; }}
{origin_init}    for (var r = 0; r < rowCount; r++) {{
{row_guard}      var row = [];
      for (var c = 0; c < colCount; c++) {{
{col_guard}{cell_read}
{style_cell}{out_after_cell}      }}
      rows.push(row);
      if (truncated === 'output') {{ sheetTrunc = 'output'; break; }}
    }}
    if (truncated && truncated !== 'output') sheetTrunc = truncated;
{used_addr_after}{style_sizes}  }}
  var sheet = {{
    sheet_index: i,
    name: name,
    rows: rows,
    used_range: usedAddr,
    row_count: rows.length,
    col_count: rows.length > 0 ? rows[0].length : 0{style_fields}
  }};
  if (sheetTrunc) sheet.truncated = sheetTrunc;
  out.sheets.push(sheet);
{out_sheet_break}}}
var jsonStr = JSON.stringify(out);"""
    )


WORKBOOK_SIDECAR_EXTRACT_BODY = workbook_sidecar_extract_body(include_formulas=False)


def parse_a1(cell: str) -> tuple[int, int]:
    """A1 notation → (row_0based, col_0based)."""
    cell = (cell or "").strip().upper().replace("$", "")
    if "!" in cell:
        cell = cell.split("!")[-1]
    match = re.match(r"^([A-Z]+)(\d+)$", cell)
    if not match:
        raise ValueError(f"Invalid A1 cell: {cell!r}")
    col_letters, row_num = match.group(1), int(match.group(2))
    col = 0
    for ch in col_letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return row_num - 1, col - 1


def used_range_origin(used_range: str | None) -> tuple[int, int]:
    """Top-left of used_range as 0-based (row, col). Missing range is A1."""
    if not used_range:
        return 0, 0
    r0, c0, _, _ = parse_range(used_range)
    return r0, c0


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


def _sanitize_sheet_cell(value: Any) -> Any:
    # GetValue() on a multi-cell range can leak a 2D array into one cell.
    if isinstance(value, (list, tuple, dict)):
        return ""
    if isinstance(value, str):
        return sanitize_text(value, trim_edges=True)
    if value is None:
        return ""
    return value


def _normalize_hex(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip().upper()
    return text if HEX_COLOR_RE.match(text) else ""


def _normalize_border(value: Any) -> str:
    text = str(value or "none").strip().lower()
    return text if text in BORDER_STYLES else "none"


def _is_default_cell_style(item: dict[str, Any]) -> bool:
    return (
        not item.get("number_format")
        and not item.get("fill_color")
        and item.get("border_left") == "none"
        and item.get("border_right") == "none"
        and item.get("border_top") == "none"
        and item.get("border_bottom") == "none"
        and not item.get("border_color")
        and not item.get("bold")
        and not item.get("italic")
        and not item.get("underline")
        and not item.get("strike")
        and not item.get("font_name")
        and item.get("font_size_pt") is None
        and not item.get("font_color")
        and item.get("align") == "left"
        and item.get("vertical_align") == "bottom"
    )


def _normalize_cell_style(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw.get("cell"):
        return None
    try:
        parse_a1(str(raw["cell"]))
    except ValueError:
        return None
    number_format = raw.get("number_format")
    if number_format in (None, "General", "general"):
        number_format = ""
    else:
        number_format = str(number_format)
    font_size = raw.get("font_size_pt")
    try:
        font_size_pt = float(font_size) if font_size is not None else None
    except (TypeError, ValueError):
        font_size_pt = None
    align = str(raw.get("align") or "left").lower()
    valign = str(raw.get("vertical_align") or "bottom").lower()
    item = {
        "cell": str(raw["cell"]).replace("$", "").split("!")[-1].upper(),
        "number_format": number_format,
        "fill_color": _normalize_hex(raw.get("fill_color")),
        "border_left": _normalize_border(raw.get("border_left")),
        "border_right": _normalize_border(raw.get("border_right")),
        "border_top": _normalize_border(raw.get("border_top")),
        "border_bottom": _normalize_border(raw.get("border_bottom")),
        "border_color": _normalize_hex(raw.get("border_color")),
        "bold": bool(raw.get("bold")),
        "italic": bool(raw.get("italic")),
        "underline": bool(raw.get("underline")),
        "strike": bool(raw.get("strike")),
        "font_name": str(raw.get("font_name") or ""),
        "font_size_pt": font_size_pt,
        "font_color": _normalize_hex(raw.get("font_color")),
        "align": align if align in ALIGN_H else "left",
        "vertical_align": valign if valign in ALIGN_V else "bottom",
    }
    if _is_default_cell_style(item):
        return None
    return item


def _normalize_column_width(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    column = str(raw.get("column") or "").replace("$", "").upper()
    if not re.match(r"^[A-Z]+$", column):
        return None
    try:
        width_pt = float(raw["width_pt"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"column": column, "width_pt": width_pt}


def _normalize_row_height(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        sheet_row = int(raw["sheet_row"])
        height_pt = float(raw["height_pt"])
    except (KeyError, TypeError, ValueError):
        return None
    if sheet_row < 1:
        return None
    return {"sheet_row": sheet_row, "height_pt": height_pt}


def _normalize_sheet(raw: dict[str, Any], index: int) -> dict[str, Any]:
    raw_rows = raw.get("rows") or []
    rows = [
        [_sanitize_sheet_cell(cell) for cell in row] if isinstance(row, (list, tuple)) else row
        for row in raw_rows
    ]
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
    if raw.get("truncated"):
        sheet["truncated"] = raw["truncated"]
    if "cell_styles" in raw:
        sheet["cell_styles"] = [
            item for item in (_normalize_cell_style(x) for x in (raw.get("cell_styles") or []))
            if item
        ]
    if "column_widths" in raw:
        sheet["column_widths"] = [
            item for item in (_normalize_column_width(x) for x in (raw.get("column_widths") or []))
            if item
        ]
    if "row_heights" in raw:
        sheet["row_heights"] = [
            item for item in (_normalize_row_height(x) for x in (raw.get("row_heights") or []))
            if item
        ]
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

    return [
        _normalize_sheet(s, i)
        for i, s in enumerate(sheets_raw)
        if isinstance(s, dict) and s.get("name") != "_office_sidecar"
    ]


def filter_sheet_names(sheets: list[dict[str, Any]], names: list[str] | None) -> list[dict[str, Any]]:
    if not names:
        return sheets
    allowed = set(names)
    return [s for s in sheets if s.get("name") in allowed]


def _clip_style_arrays(sheet: dict[str, Any], r0: int, c0: int, r1: int, c1: int) -> None:
    if "cell_styles" in sheet:
        kept: list[dict[str, Any]] = []
        for item in sheet.get("cell_styles") or []:
            try:
                sr, sc = parse_a1(item.get("cell") or "")
            except ValueError:
                continue
            if r0 <= sr <= r1 and c0 <= sc <= c1:
                kept.append(item)
        sheet["cell_styles"] = kept
    if "column_widths" in sheet:
        kept_w: list[dict[str, Any]] = []
        for item in sheet.get("column_widths") or []:
            try:
                _, sc = parse_a1(f"{item.get('column')}1")
            except ValueError:
                continue
            if c0 <= sc <= c1:
                kept_w.append(item)
        sheet["column_widths"] = kept_w
    if "row_heights" in sheet:
        kept_h: list[dict[str, Any]] = []
        for item in sheet.get("row_heights") or []:
            sheet_row = item.get("sheet_row")
            if not isinstance(sheet_row, int):
                continue
            if r0 <= sheet_row - 1 <= r1:
                kept_h.append(item)
        sheet["row_heights"] = kept_h


def apply_range_filter(
    sheets: list[dict[str, Any]], range_str: str | None
) -> list[dict[str, Any]]:
    """ADR-034: clip each sheet to A1 range using used_range as the grid origin."""
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
        origin_r, origin_c = used_range_origin(s.get("used_range"))
        clipped: list[list[Any]] = []
        for sheet_r in range(r0, r1 + 1):
            grid_r = sheet_r - origin_r
            if grid_r < 0 or grid_r >= len(rows):
                continue
            row = rows[grid_r]
            grid_c0 = c0 - origin_c
            grid_c1 = c1 - origin_c
            if grid_c0 < 0:
                grid_c0 = 0
            clipped.append(list(row[grid_c0 : grid_c1 + 1]) if grid_c0 < len(row) else [])
        s["rows"] = clipped
        s["row_count"] = len(clipped)
        s["col_count"] = max((len(r) for r in clipped), default=0)
        if clipped:
            first_r = max(r0, origin_r)
            first_c = max(c0, origin_c)
            last_r = min(r1, origin_r + len(rows) - 1) if rows else first_r
            last_c = min(c1, origin_c + max((len(r) for r in rows), default=1) - 1) if rows else first_c
            if last_r < first_r or last_c < first_c:
                s.pop("used_range", None)
            else:
                s["used_range"] = _format_a1_range(first_r, first_c, last_r, last_c)
                _clip_style_arrays(s, first_r, first_c, last_r, last_c)
        else:
            s.pop("used_range", None)
            _clip_style_arrays(s, r0, c0, r1, c1)
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
            origin_r, _ = used_range_origin(s.get("used_range"))
            last_kept = origin_r + max_rows - 1
            if "cell_styles" in s:
                kept = []
                for item in s.get("cell_styles") or []:
                    try:
                        sr, _ = parse_a1(item.get("cell") or "")
                    except ValueError:
                        continue
                    if sr <= last_kept:
                        kept.append(item)
                s["cell_styles"] = kept
            if "row_heights" in s:
                s["row_heights"] = [
                    item
                    for item in (s.get("row_heights") or [])
                    if isinstance(item.get("sheet_row"), int) and item["sheet_row"] - 1 <= last_kept
                ]
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
            parts.append("\t".join(sanitize_text(c, trim_edges=True) for c in row))
    return "\n".join(parts)
