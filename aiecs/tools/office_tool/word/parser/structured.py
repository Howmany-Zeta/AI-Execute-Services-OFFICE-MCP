"""
Builder sidecar extraction and normalization for Word structured reads.

JS dumps sections / runs / style names. Python applies page numbers,
style matching, and element types.
"""

from __future__ import annotations

import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import (
    has_visible_text,
    ltrim_regular_spaces,
    rtrim_regular_spaces,
    sanitize_text,
)

STRUCTURED_WORD_EXTRACT_BODY = r"""
function _str(v) { return (v === undefined || v === null) ? "" : String(v); }
function _pushUnique(arr, v) {
  if (!v) return;
  var s = String(v);
  for (var i = 0; i < arr.length; i++) { if (arr[i] === s) return; }
  arr.push(s);
}
function _safeCall(obj, name) {
  if (!obj || typeof obj[name] !== "function") return undefined;
  try { return obj[name](); } catch (e) { return undefined; }
}
function _hex2(n) {
  var s = Math.max(0, Math.min(255, Math.round(Number(n) || 0))).toString(16);
  return s.length < 2 ? "0" + s : s;
}
function _colorToHex(color) {
  if (color === undefined || color === null) return undefined;
  if (typeof color === "string") {
    var t = color.replace(/^\s+|\s+$/g, "");
    if (!t) return undefined;
    if (t.toLowerCase() === "none" || t.toLowerCase() === "auto") return t.toLowerCase() === "none" ? "none" : undefined;
    if (t.charAt(0) === "#" && t.length === 7) return t.toUpperCase();
    return t;
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
  return undefined;
}
function _boolish(v) {
  if (v === undefined || v === null) return undefined;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  var s = String(v).toLowerCase();
  if (s === "true" || s === "single" || s === "yes") return true;
  if (s === "false" || s === "none" || s === "no") return false;
  return undefined;
}
function extractRun(run) {
  if (!run) return null;
  var out = { text: "" };
  var txt = _safeCall(run, "GetText");
  if (txt !== undefined && txt !== null) out.text = _str(txt);
  var bold = _safeCall(run, "GetBold");
  if (bold !== undefined) out.bold = !!bold;
  var italic = _safeCall(run, "GetItalic");
  if (italic !== undefined) out.italic = !!italic;
  var underline = _safeCall(run, "GetUnderline");
  var ul = _boolish(underline);
  if (ul !== undefined) out.underline = ul;
  else if (underline !== undefined && underline !== null) out.underline = underline !== "none" && underline !== false;
  var strike = _safeCall(run, "GetStrikeout");
  if (strike === undefined) strike = _safeCall(run, "GetStrike");
  if (strike !== undefined) out.strike = !!strike;
  var highlight = _safeCall(run, "GetHighlight");
  if (highlight !== undefined && highlight !== null) {
    if (highlight === false || _str(highlight).toLowerCase() === "none") out.highlight = "none";
    else {
      var hx = _colorToHex(highlight);
      out.highlight = hx !== undefined ? hx : _str(highlight);
    }
  }
  var font = _safeCall(run, "GetFontFamily");
  if (font === undefined) font = _safeCall(run, "GetFontName");
  if (font) out.font_name = _str(font);
  var size = _safeCall(run, "GetFontSize");
  if (typeof size === "number") out.font_size_pt = size;
  var color = _safeCall(run, "GetColor");
  var chex = _colorToHex(color);
  if (chex) out.font_color = chex;
  return out;
}
function extractRunsFromContainer(el) {
  var runs = [];
  if (!el) return runs;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  if (cls === "run" || cls === "textrun") {
    var one = extractRun(el);
    if (one) runs.push(one);
    return runs;
  }
  var n = 0;
  try { n = el.GetElementsCount ? el.GetElementsCount() : 0; } catch (e) { n = 0; }
  if (!n) {
    var t = _safeCall(el, "GetText");
    if (t) runs.push({ text: _str(t) });
    return runs;
  }
  for (var i = 0; i < n; i++) {
    var child = null;
    try { child = el.GetElement(i); } catch (e) { child = null; }
    if (!child) continue;
    var ccls = _str(_safeCall(child, "GetClassType")).toLowerCase();
    if (ccls === "hyperlink" || ccls === "inlinelvlsdt" || ccls === "blocklvlsdt") {
      var inner = extractRunsFromContainer(child);
      for (var k = 0; k < inner.length; k++) runs.push(inner[k]);
      continue;
    }
    if (ccls.indexOf("drawing") >= 0 || ccls.indexOf("shape") >= 0 || ccls === "image" || ccls === "oleobject") {
      continue;
    }
    if (ccls === "run" || ccls === "textrun" || child.GetBold || child.GetText) {
      var r = extractRun(child);
      if (r) runs.push(r);
    } else {
      var nested = extractRunsFromContainer(child);
      for (var m = 0; m < nested.length; m++) runs.push(nested[m]);
    }
  }
  return runs;
}
function countPageBreaks(el) {
  var k = 0;
  if (!el) return 0;
  try {
    if (el.GetPageBreakBefore && el.GetPageBreakBefore() === true) k++;
  } catch (e) {}
  function walk(node) {
    if (!node) return;
    var n = 0;
    try { n = node.GetElementsCount ? node.GetElementsCount() : 0; } catch (e) { n = 0; }
    for (var i = 0; i < n; i++) {
      var child = null;
      try { child = node.GetElement(i); } catch (e) { child = null; }
      if (!child) continue;
      var cls = _str(_safeCall(child, "GetClassType")).toLowerCase();
      var bt = _str(_safeCall(child, "GetBreakType")).toLowerCase();
      if (cls.indexOf("pagebreak") >= 0 || bt.indexOf("page") >= 0) {
        k++;
        continue;
      }
      try {
        if (child.AddPageBreak && child.GetClassType && cls === "run") {
          var innerN = child.GetElementsCount ? child.GetElementsCount() : 0;
          for (var j = 0; j < innerN; j++) {
            var ic = child.GetElement(j);
            var icls = _str(_safeCall(ic, "GetClassType")).toLowerCase();
            var ibt = _str(_safeCall(ic, "GetBreakType")).toLowerCase();
            if (icls.indexOf("pagebreak") >= 0 || ibt.indexOf("page") >= 0) k++;
          }
        }
      } catch (e2) {}
      walk(child);
    }
  }
  walk(el);
  return k;
}
function collectStyleNames(para) {
  var names = [];
  _pushUnique(names, _safeCall(para, "GetStyleName"));
  var st = _safeCall(para, "GetStyle");
  if (st) {
    _pushUnique(names, _safeCall(st, "GetName"));
    _pushUnique(names, _safeCall(st, "GetNamePr"));
    _pushUnique(names, _safeCall(st, "GetStyleId"));
  }
  return names;
}
function extractAlign(para) {
  var jc = _safeCall(para, "GetJc");
  if (jc === undefined || jc === null) return undefined;
  return _str(jc);
}
function extractParagraph(para) {
  var runs = extractRunsFromContainer(para);
  var textParts = [];
  for (var i = 0; i < runs.length; i++) textParts.push(runs[i].text || "");
  var text = textParts.join("");
  if (!text) {
    var gt = _safeCall(para, "GetText");
    if (gt) text = _str(gt);
  }
  var outline = _safeCall(para, "GetOutlineLvl");
  var numbering = _safeCall(para, "GetNumbering");
  if (numbering === undefined) numbering = _safeCall(para, "GetNumPr");
  var hasList = !!numbering;
  var listLevel = undefined;
  if (numbering) {
    var ilvl = _safeCall(numbering, "GetIlvl");
    if (ilvl === undefined) ilvl = _safeCall(numbering, "GetLevel");
    if (typeof ilvl === "object" && ilvl) ilvl = _safeCall(ilvl, "GetLevel");
    if (typeof ilvl === "number") listLevel = ilvl;
  }
  var out = {
    class: "paragraph",
    style_names: collectStyleNames(para),
    page_breaks: countPageBreaks(para),
    has_numbering: hasList,
    text: text,
    runs: runs
  };
  if (typeof outline === "number") out.outline_level = outline;
  if (listLevel !== undefined) out.list_level = listLevel;
  var align = extractAlign(para);
  if (align) out.align = align;
  return out;
}
function extractTable(table) {
  var rows = [];
  var rowCount = 0;
  try { rowCount = table.GetRowsCount ? table.GetRowsCount() : 0; } catch (e) { rowCount = 0; }
  for (var ri = 0; ri < rowCount; ri++) {
    var row = null;
    try { row = table.GetRow(ri); } catch (e) { row = null; }
    var rowCells = [];
    var cellCount = 0;
    if (row && row.GetCellsCount) {
      try { cellCount = row.GetCellsCount(); } catch (e2) { cellCount = 0; }
    }
    for (var ci = 0; ci < cellCount; ci++) {
      var cell = null;
      try { cell = row.GetCell(ci); } catch (e3) { cell = null; }
      var cellText = "";
      if (cell && cell.GetContent) {
        var content = cell.GetContent();
        if (content && content.GetText) {
          try { cellText = _str(content.GetText()); } catch (e4) { cellText = ""; }
        } else if (content && content.GetElement) {
          try {
            var cellEl = content.GetElement(0);
            if (cellEl && cellEl.GetText) cellText = _str(cellEl.GetText());
          } catch (e5) { cellText = ""; }
        }
      }
      rowCells.push(cellText);
    }
    rows.push(rowCells);
  }
  return { class: "table", rows: rows, page_breaks: countPageBreaks(table) };
}
function extractHeaderFooterParas(section, kind) {
  var out = [];
  if (!section) return out;
  var getter = kind === "header" ? "GetHeader" : "GetFooter";
  if (typeof section[getter] !== "function") return out;
  var part = null;
  try { part = section[getter]("default"); } catch (e) { part = null; }
  if (!part) return out;
  var n = 0;
  try { n = part.GetElementsCount ? part.GetElementsCount() : 0; } catch (e2) { n = 0; }
  for (var i = 0; i < n; i++) {
    var el = null;
    try { el = part.GetElement(i); } catch (e3) { el = null; }
    if (!el) continue;
    var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
    if (cls === "paragraph") out.push(extractParagraph(el));
  }
  return out;
}
function sectionBreakType(section) {
  if (!section) return "continuous";
  var t = _safeCall(section, "GetType");
  if (t === undefined) t = _safeCall(section, "GetStartType");
  return t ? _str(t) : "continuous";
}
function isFootnoteLike(para) {
  var names = collectStyleNames(para);
  for (var i = 0; i < names.length; i++) {
    var low = names[i].toLowerCase();
    if (low.indexOf("footnote") >= 0 || low.indexOf("endnote") >= 0) return true;
  }
  var cls = _str(_safeCall(para, "GetClassType")).toLowerCase();
  return cls.indexOf("footnote") >= 0 || cls.indexOf("endnote") >= 0;
}
function extractNotes(doc, method) {
  var notes = [];
  var arr = _safeCall(doc, method);
  if (!arr || !arr.length) return notes;
  for (var i = 0; i < arr.length; i++) {
    var note = arr[i];
    if (!note) continue;
    var para = note;
    if (note.GetContent) {
      try {
        var content = note.GetContent();
        if (content && content.GetElement) para = content.GetElement(0) || note;
      } catch (e) { para = note; }
    }
    var item = extractParagraph(para);
    item.ref_page = null;
    notes.push(item);
  }
  return notes;
}
function extractDrawingOrShape(el) {
  if (!el) return null;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  var isImage = cls === "image" || cls === "pic" || cls === "picture" || !!_safeCall(el, "GetImage");
  if (isImage) {
    var alt = _str(_safeCall(el, "GetTitle") || _safeCall(el, "GetDesc") || _safeCall(el, "GetAltText") || "image");
    return { class: "image", alt: alt, text: alt, page_breaks: 0 };
  }
  var text = "";
  var content = _safeCall(el, "GetDocContent");
  if (!content) content = _safeCall(el, "GetContent");
  if (content) {
    var runs = extractRunsFromContainer(content);
    var parts = [];
    for (var i = 0; i < runs.length; i++) parts.push(runs[i].text || "");
    text = parts.join("");
    if (!text) text = _str(_safeCall(content, "GetText"));
  }
  if (!text) text = _str(_safeCall(el, "GetText"));
  if (text) return { class: "textbox", text: text, page_breaks: countPageBreaks(el) };
  return null;
}
function extractInlineDrawings(para) {
  var out = [];
  if (!para || !para.GetElementsCount) return out;
  var n = 0;
  try { n = para.GetElementsCount(); } catch (e) { n = 0; }
  for (var i = 0; i < n; i++) {
    var child = null;
    try { child = para.GetElement(i); } catch (e2) { child = null; }
    if (!child) continue;
    var ccls = _str(_safeCall(child, "GetClassType")).toLowerCase();
    if (ccls.indexOf("drawing") >= 0 || ccls.indexOf("shape") >= 0 || ccls === "image" || ccls === "oleobject") {
      var extra = extractDrawingOrShape(child);
      if (extra) out.push(extra);
    }
  }
  return out;
}

var doc = Api.GetDocument();
var sectionsOut = [];
var current = null;
var lastSection = null;

function startSection(section) {
  current = {
    break_type: sectionsOut.length === 0 ? "continuous" : sectionBreakType(section),
    header: extractHeaderFooterParas(section, "header"),
    footer: extractHeaderFooterParas(section, "footer"),
    body: []
  };
  lastSection = section;
  sectionsOut.push(current);
}

var count = 0;
try { count = doc.GetElementsCount(); } catch (e) { count = 0; }
for (var i = 0; i < count; i++) {
  var el = null;
  try { el = doc.GetElement(i); } catch (e) { el = null; }
  if (!el) continue;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  if (cls === "paragraph" && isFootnoteLike(el)) continue;
  var sec = _safeCall(el, "GetSection");
  if (!current) {
    startSection(sec || (doc.GetFinalSection ? doc.GetFinalSection() : null));
  } else if (sec && lastSection && sec !== lastSection) {
    startSection(sec);
  }
  if (cls === "table") {
    current.body.push(extractTable(el));
  } else if (cls === "paragraph") {
    current.body.push(extractParagraph(el));
    var extras = extractInlineDrawings(el);
    for (var x = 0; x < extras.length; x++) current.body.push(extras[x]);
  } else {
    var drawn = extractDrawingOrShape(el);
    if (drawn) current.body.push(drawn);
  }
}
if (!sectionsOut.length) {
  var fallbackSec = doc.GetFinalSection ? doc.GetFinalSection() : null;
  startSection(fallbackSec);
}
var footnotes = extractNotes(doc, "GetAllFootnotes");
var endnotes = extractNotes(doc, "GetAllEndnotes");
for (var n = 0; n < endnotes.length; n++) footnotes.push(endnotes[n]);
var jsonStr = JSON.stringify({ sections: sectionsOut, footnotes: footnotes });
"""


_ALIGN_OK = frozenset({"left", "center", "right"})
_PAGE_SECTION_BREAKS = frozenset({
    "nextpage",
    "next_page",
    "next page",
    "oddpage",
    "odd_page",
    "odd page",
    "evenpage",
    "even_page",
    "even page",
})

_LATIN_TOC = tuple(f"toc {i}" for i in range(1, 10))
_LATIN_CAPTION = ("caption",)
_LATIN_QUOTE = ("quote", "intense quote")
_LATIN_CHAPTER = ("chapter",)
_LATIN_HEADING = tuple(f"heading {i}" for i in range(1, 10))

_ZH_TOC = tuple(f"目录 {i}" for i in range(1, 10))
_ZH_CAPTION = ("题注",)
_ZH_QUOTE = ("引用", "明显引用")
_ZH_CHAPTER = ("章标题",)
_ZH_HEADING = tuple(f"标题 {i}" for i in range(1, 10))

_WORD_COUNT_RE = re.compile(r"\S+")
_HEADING_NUM_RE = re.compile(r"(?:heading|标题)\s*([1-9])$", re.I)
_RUN_STYLE_KEYS = (
    "bold",
    "italic",
    "underline",
    "strike",
    "highlight",
    "font_name",
    "font_size_pt",
    "font_color",
)


def _count_words(text: str) -> int:
    return len(_WORD_COUNT_RE.findall(text)) if text else 0


def _style_names(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    raw = item.get("style_names")
    if isinstance(raw, list):
        names.extend(str(x) for x in raw if x is not None)
    for key in ("style_name", "style_display", "style_id"):
        val = item.get(key)
        if val:
            names.append(str(val))
    return [n.strip() for n in names if str(n).strip()]


def _latin_match(names: list[str], targets: tuple[str, ...]) -> bool:
    wanted = {t.lower() for t in targets}
    return any(name.lower() in wanted for name in names)


def _zh_match(names: list[str], targets: tuple[str, ...]) -> bool:
    wanted = set(targets)
    return any(name in wanted for name in names)


def _heading_level_from_name(names: list[str]) -> int | None:
    for name in names:
        low = name.lower()
        if _latin_match([name], _LATIN_HEADING) or name in _ZH_HEADING:
            match = _HEADING_NUM_RE.search(name) or _HEADING_NUM_RE.search(low)
            if match:
                return int(match.group(1))
            digits = "".join(ch for ch in name if ch.isdigit())
            if digits:
                return int(digits[0])
    return None


def _to_hex_color(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.lower() == "none":
            return "none"
        if text.startswith("#") and len(text) == 7:
            return text.upper()
        if len(text) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in text):
            return f"#{text.upper()}"
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        if number < 0:
            return None
        return f"#{number:06X}"[-7:]
    if isinstance(value, dict):
        red = value.get("r", value.get("red"))
        green = value.get("g", value.get("green"))
        blue = value.get("b", value.get("blue"))
        if red is not None and green is not None and blue is not None:
            return f"#{int(red):02X}{int(green):02X}{int(blue):02X}"
    return None


def _normalize_run(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    text = sanitize_text(raw.get("text"), trim_edges=False)
    if not has_visible_text(text):
        return None
    run: dict[str, Any] = {"text": text}
    for key in ("bold", "italic", "underline", "strike"):
        if key in raw and raw[key] is not None:
            run[key] = bool(raw[key])
    if "highlight" in raw and raw["highlight"] is not None:
        highlight = raw["highlight"]
        if highlight is False or (isinstance(highlight, str) and highlight.strip().lower() == "none"):
            run["highlight"] = "none"
        else:
            converted = _to_hex_color(highlight)
            run["highlight"] = converted if converted is not None else "none"
    if raw.get("font_name"):
        run["font_name"] = str(raw["font_name"])
    if raw.get("font_size_pt") is not None:
        try:
            run["font_size_pt"] = float(raw["font_size_pt"])
        except (TypeError, ValueError):
            pass
    if "font_color" in raw and raw["font_color"] is not None:
        color = _to_hex_color(raw["font_color"])
        if color and color != "none":
            run["font_color"] = color
    hyperlink = raw.get("hyperlink")
    if isinstance(hyperlink, dict) and hyperlink.get("url"):
        run["hyperlink"] = {
            "url": str(hyperlink["url"]),
            "text": str(hyperlink.get("text") or text),
        }
    return run


def _run_signature(run: dict[str, Any]) -> tuple[Any, ...]:
    link = run.get("hyperlink")
    link_url = link.get("url") if isinstance(link, dict) else None
    return tuple(run.get(key) for key in _RUN_STYLE_KEYS) + (link_url,)


def _merge_adjacent_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for run in runs:
        if merged and _run_signature(merged[-1]) == _run_signature(run):
            merged[-1]["text"] = merged[-1]["text"] + run["text"]
        else:
            merged.append(dict(run))
    return merged


def _trim_run_edges(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not runs:
        return []
    trimmed = [dict(run) for run in runs]
    trimmed[0]["text"] = ltrim_regular_spaces(trimmed[0]["text"])
    trimmed[-1]["text"] = rtrim_regular_spaces(trimmed[-1]["text"])
    return [run for run in trimmed if has_visible_text(run.get("text"))]


def _normalize_runs(raw_runs: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_runs, list):
        return []
    runs = [_normalize_run(item) for item in raw_runs]
    kept = [run for run in runs if run is not None]
    return _trim_run_edges(_merge_adjacent_runs(kept))


def _paragraph_text(item: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    if runs:
        return "".join(str(run.get("text") or "") for run in runs)
    return sanitize_text(item.get("text"), trim_edges=True)


def _normalize_word_cell(cell: Any) -> str:
    text = sanitize_text(cell, trim_edges=False)
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\t"):
        text = text[:-1]
    return sanitize_text(text, trim_edges=True)


def _outline_level(item: dict[str, Any]) -> int | None:
    value = item.get("outline_level")
    if isinstance(value, bool) or value is None:
        return None
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= level <= 8:
        return level
    return None


def _list_level(item: dict[str, Any]) -> int | None:
    value = item.get("list_level")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _align(item: dict[str, Any]) -> str | None:
    value = str(item.get("align") or "").strip().lower()
    if value in _ALIGN_OK:
        return value
    return None


def _page_breaks(item: dict[str, Any]) -> int:
    value = item.get("page_breaks") or 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _is_page_section_break(break_type: str) -> bool:
    compact = break_type.lower().replace("_", " ").replace("-", " ")
    compact = " ".join(compact.split())
    return compact.replace(" ", "") in {"nextpage", "oddpage", "evenpage"} or compact in _PAGE_SECTION_BREAKS


def _classify_paragraph(item: dict[str, Any], page: int, type_override: str | None = None) -> dict[str, Any]:
    runs = _normalize_runs(item.get("runs"))
    text = _paragraph_text(item, runs)
    element: dict[str, Any] = {"page": page, "text": text}
    align = _align(item)
    if align:
        element["align"] = align
    if runs:
        element["runs"] = runs

    if type_override:
        element["type"] = type_override
        return element

    names = _style_names(item)
    outline = _outline_level(item)

    if _latin_match(names, _LATIN_TOC) or _zh_match(names, _ZH_TOC):
        element["type"] = "toc"
        return element
    if _latin_match(names, _LATIN_CAPTION) or _zh_match(names, _ZH_CAPTION):
        element["type"] = "caption"
        return element
    if _latin_match(names, _LATIN_QUOTE) or _zh_match(names, _ZH_QUOTE):
        element["type"] = "quote"
        return element
    if _latin_match(names, _LATIN_CHAPTER) or _zh_match(names, _ZH_CHAPTER):
        element["type"] = "chapter"
        if outline is not None:
            element["level"] = outline + 1
        return element
    if outline is not None:
        element["type"] = "heading"
        element["level"] = outline + 1
        return element
    heading_level = _heading_level_from_name(names)
    if heading_level is not None:
        element["type"] = "heading"
        element["level"] = heading_level
        return element
    if item.get("has_numbering") or item.get("has_bullets"):
        element["type"] = "list"
        list_level = _list_level(item)
        if list_level is not None:
            element["level"] = list_level + 1
        return element
    element["type"] = "paragraph"
    return element


def _item_class(item: dict[str, Any]) -> str:
    return str(item.get("class") or item.get("class_type") or item.get("type") or "paragraph").lower()


def _has_content(item: dict[str, Any]) -> bool:
    if has_visible_text(item.get("text")):
        return True
    for run in item.get("runs") or []:
        if isinstance(run, dict) and has_visible_text(run.get("text")):
            return True
    return False


def normalize_word_structured(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Turn Builder sidecar JSON into top-level Word elements."""
    data = raw if isinstance(raw, dict) else {}
    sections = data.get("sections")
    if not isinstance(sections, list):
        sections = [{
            "break_type": "continuous",
            "header": data.get("header") or [],
            "footer": data.get("footer") or [],
            "body": data.get("body") or [],
        }]

    elements: list[dict[str, Any]] = []
    page = 1
    last_body_page = 1

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        break_type = str(section.get("break_type") or "continuous")
        if index > 0 and _is_page_section_break(break_type):
            page += 1
        section_page = page

        for header in section.get("header") or []:
            if isinstance(header, dict) and _has_content(header):
                elements.append(_classify_paragraph(header, section_page, type_override="header"))
        for footer in section.get("footer") or []:
            if isinstance(footer, dict) and _has_content(footer):
                elements.append(_classify_paragraph(footer, section_page, type_override="footer"))

        for item in section.get("body") or []:
            if not isinstance(item, dict):
                continue
            kind = _item_class(item)
            breaks = _page_breaks(item)
            item_page = page
            if kind == "image":
                alt = sanitize_text(item.get("alt") or item.get("text") or "image", trim_edges=True) or "image"
                elements.append({"type": "image", "page": item_page, "alt": alt, "text": alt})
                last_body_page = item_page
                page += breaks
                continue
            if kind == "textbox":
                if _has_content(item):
                    elements.append({
                        "type": "textbox",
                        "page": item_page,
                        "text": sanitize_text(item.get("text"), trim_edges=True),
                    })
                    last_body_page = item_page
                page += breaks
                continue
            if kind not in {"paragraph", "table", ""}:
                page += breaks
                continue
            if kind == "table":
                rows = item.get("rows") if isinstance(item.get("rows"), list) else []
                normalized_rows = [
                    [_normalize_word_cell(cell) for cell in row]
                    if isinstance(row, (list, tuple))
                    else [_normalize_word_cell(row)]
                    for row in rows
                ]
                elements.append({"type": "table", "page": item_page, "rows": normalized_rows})
                last_body_page = item_page
            elif _has_content(item):
                elements.append(_classify_paragraph(item, item_page))
                last_body_page = item_page
            page += breaks

    for note in data.get("footnotes") or []:
        if not isinstance(note, dict):
            continue
        ref_page = note.get("ref_page")
        try:
            note_page = int(ref_page) if ref_page not in (None, "") else last_body_page
        except (TypeError, ValueError):
            note_page = last_body_page
        if _has_content(note):
            elements.append(_classify_paragraph(note, note_page, type_override="footnote"))

    return {"elements": elements}


def word_title_from_elements(elements: list[dict[str, Any]]) -> str:
    for element in elements:
        if element.get("type") in {"chapter", "heading"} and element.get("text"):
            return str(element["text"])
    for element in elements:
        if element.get("text"):
            return str(element["text"])[:200]
    return ""


def word_count_from_elements(elements: list[dict[str, Any]]) -> int:
    total = 0
    for element in elements:
        if element.get("type") == "table":
            for row in element.get("rows") or []:
                if isinstance(row, (list, tuple)):
                    total += sum(_count_words(str(cell)) for cell in row)
        else:
            total += _count_words(str(element.get("text") or ""))
    return total


def word_page_count(elements: list[dict[str, Any]]) -> int:
    pages = [int(el["page"]) for el in elements if isinstance(el.get("page"), int)]
    return max(pages) if pages else 1
