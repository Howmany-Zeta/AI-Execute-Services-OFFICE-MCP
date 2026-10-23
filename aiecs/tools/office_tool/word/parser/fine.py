"""
Fine Word sidecar: ToJSON skeleton plus live walk for runs, lists, headers, images.
"""

from __future__ import annotations

from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text
from aiecs.tools.office_tool.word.parser.structured import (
    _LATIN_CAPTION,
    _ZH_CAPTION,
    _align,
    _heading_level_from_name,
    _latin_match,
    _normalize_runs,
    _normalize_word_cell,
    _outline_level,
    _style_names,
    _zh_match,
)

WORD_TOJSON_EXTRACT_BODY = r"""
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
function emuToPt(v) {
  if (typeof v !== "number") return undefined;
  if (Math.abs(v) > 1000) return v / 12700.0;
  return v;
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
  var note = _safeCall(run, "GetFootnote");
  if (!note) note = _safeCall(run, "GetEndnote");
  if (note) {
    out.footnote_id = _str(_safeCall(note, "GetId") || _safeCall(note, "GetIndex") || "");
  } else {
    var rcls = _str(_safeCall(run, "GetClassType")).toLowerCase();
    if (rcls.indexOf("footnoteref") >= 0 || rcls.indexOf("endnoteref") >= 0) {
      out.footnote_id = _str(_safeCall(run, "GetId") || _safeCall(run, "GetValue") || "");
    }
  }
  return out;
}
function hyperlinkUrl(el) {
  var url = _safeCall(el, "GetLink");
  if (!url) url = _safeCall(el, "GetValue");
  if (!url) url = _safeCall(el, "GetUrl");
  if (!url) url = _safeCall(el, "GetAddress");
  return url ? _str(url) : "";
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
    if (ccls === "hyperlink") {
      var url = hyperlinkUrl(child);
      var inner = extractRunsFromContainer(child);
      for (var k = 0; k < inner.length; k++) {
        if (url) inner[k].hyperlink = { url: url, text: inner[k].text || "" };
        runs.push(inner[k]);
      }
      continue;
    }
    if (ccls === "inlinelvlsdt" || ccls === "blocklvlsdt") {
      var nestedSdt = extractRunsFromContainer(child);
      for (var s = 0; s < nestedSdt.length; s++) runs.push(nestedSdt[s]);
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
function isImageLike(el) {
  if (!el) return false;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  if (cls === "image" || cls === "pic" || cls === "picture") return true;
  if (cls.indexOf("drawing") >= 0 && !!_safeCall(el, "GetImage")) return true;
  return !!_safeCall(el, "GetImage");
}
function extractImage(el) {
  var alt = _str(_safeCall(el, "GetTitle") || _safeCall(el, "GetDesc") || _safeCall(el, "GetAltText") || "image");
  var out = { class: "image", alt: alt || "image", text: alt || "image" };
  var w = emuToPt(_safeCall(el, "GetWidth"));
  var h = emuToPt(_safeCall(el, "GetHeight"));
  if (w !== undefined) out.width_pt = w;
  if (h !== undefined) out.height_pt = h;
  return out;
}
function extractInlineImages(para) {
  var out = [];
  if (!para || !para.GetElementsCount) return out;
  var n = 0;
  try { n = para.GetElementsCount(); } catch (e) { n = 0; }
  var imageIndex = 0;
  for (var i = 0; i < n; i++) {
    var child = null;
    try { child = para.GetElement(i); } catch (e2) { child = null; }
    if (!child || !isImageLike(child)) continue;
    var img = extractImage(child);
    img.image_index = imageIndex;
    imageIndex++;
    out.push(img);
  }
  return out;
}
function isPageNumberNode(el) {
  if (!el) return false;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  if (cls.indexOf("pagenum") >= 0 || cls.indexOf("pagenumber") >= 0 || cls.indexOf("pagefield") >= 0) return true;
  var instr = _str(_safeCall(el, "GetInstruction") || _safeCall(el, "GetFieldCode") || _safeCall(el, "GetType") || "");
  if (instr && instr.toUpperCase().indexOf("PAGE") >= 0 && instr.toUpperCase().indexOf("PAGEREF") < 0) return true;
  return false;
}
function findPageNumber(part, align) {
  var found = null;
  function walk(el) {
    if (!el || found) return;
    if (isPageNumberNode(el)) {
      found = { position: align || "left" };
      return;
    }
    var n = 0;
    try { n = el.GetElementsCount ? el.GetElementsCount() : 0; } catch (e) { n = 0; }
    for (var i = 0; i < n; i++) {
      try { walk(el.GetElement(i)); } catch (e2) {}
    }
  }
  walk(part);
  return found;
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
  var listType = undefined;
  if (numbering) {
    var ilvl = _safeCall(numbering, "GetIlvl");
    if (ilvl === undefined) ilvl = _safeCall(numbering, "GetLevel");
    if (typeof ilvl === "object" && ilvl) ilvl = _safeCall(ilvl, "GetLevel");
    if (typeof ilvl === "number") listLevel = ilvl;
    var nt = _str(_safeCall(numbering, "GetNumType") || _safeCall(numbering, "GetType") || _safeCall(numbering, "GetClassType") || "").toLowerCase();
    if (nt.indexOf("bullet") >= 0) listType = "bullet";
    else if (nt.indexOf("number") >= 0 || nt.indexOf("decimal") >= 0 || nt.indexOf("arabic") >= 0) listType = "number";
    else listType = "number";
  }
  var out = {
    class: "paragraph",
    style_names: collectStyleNames(para),
    has_numbering: hasList,
    text: text,
    runs: runs
  };
  if (typeof outline === "number") out.outline_level = outline;
  if (listLevel !== undefined) out.list_level = listLevel;
  if (listType) out.list_type = listType;
  var align = extractAlign(para);
  if (align) out.align = align;
  var images = extractInlineImages(para);
  if (images.length) out.images = images;
  return out;
}
function extractCell(cell, row, col) {
  var out = { row: row, col: col, text: "", runs: [] };
  if (!cell || !cell.GetContent) return out;
  var content = cell.GetContent();
  if (!content) return out;
  var para = content;
  if (content.GetElement) {
    try { para = content.GetElement(0) || content; } catch (e) { para = content; }
  }
  var extracted = extractParagraph(para);
  out.text = extracted.text || "";
  out.runs = extracted.runs || [];
  if (extracted.align) out.align = extracted.align;
  return out;
}
function extractTable(table) {
  var rows = [];
  var cells = [];
  var rowCount = 0;
  try { rowCount = table.GetRowsCount ? table.GetRowsCount() : 0; } catch (e) { rowCount = 0; }
  for (var ri = 0; ri < rowCount; ri++) {
    var row = null;
    try { row = table.GetRow(ri); } catch (e2) { row = null; }
    var rowCells = [];
    var cellCount = 0;
    if (row && row.GetCellsCount) {
      try { cellCount = row.GetCellsCount(); } catch (e3) { cellCount = 0; }
    }
    for (var ci = 0; ci < cellCount; ci++) {
      var cell = null;
      try { cell = row.GetCell(ci); } catch (e4) { cell = null; }
      var extracted = extractCell(cell, ri, ci);
      rowCells.push(extracted.text);
      cells.push(extracted);
    }
    rows.push(rowCells);
  }
  return { class: "table", rows: rows, cells: cells };
}
function countPageBreaks(el) {
  var k = 0;
  if (!el) return 0;
  try { if (el.GetPageBreakBefore && el.GetPageBreakBefore() === true) k++; } catch (e) {}
  function walk(node) {
    if (!node) return;
    var n = 0;
    try { n = node.GetElementsCount ? node.GetElementsCount() : 0; } catch (e2) { n = 0; }
    for (var i = 0; i < n; i++) {
      var child = null;
      try { child = node.GetElement(i); } catch (e3) { child = null; }
      if (!child) continue;
      var cls = _str(_safeCall(child, "GetClassType")).toLowerCase();
      var bt = _str(_safeCall(child, "GetBreakType")).toLowerCase();
      if (cls.indexOf("pagebreak") >= 0 || bt.indexOf("page") >= 0) k++;
      walk(child);
    }
  }
  walk(el);
  return k;
}
function isCaptionStyle(names) {
  if (!names) return false;
  for (var i = 0; i < names.length; i++) {
    var low = _str(names[i]).toLowerCase();
    if (low === "caption" || names[i] === "题注") return true;
  }
  return false;
}
function extractGeometry(el) {
  var out = {};
  var x = emuToPt(_safeCall(el, "GetPosX"));
  if (x === undefined) x = emuToPt(_safeCall(el, "GetX"));
  if (x === undefined) x = emuToPt(_safeCall(el, "GetLeft"));
  var y = emuToPt(_safeCall(el, "GetPosY"));
  if (y === undefined) y = emuToPt(_safeCall(el, "GetY"));
  if (y === undefined) y = emuToPt(_safeCall(el, "GetTop"));
  var w = emuToPt(_safeCall(el, "GetWidth"));
  var h = emuToPt(_safeCall(el, "GetHeight"));
  if (x !== undefined) out.x_pt = x;
  if (y !== undefined) out.y_pt = y;
  if (w !== undefined) out.width_pt = w;
  if (h !== undefined) out.height_pt = h;
  return out;
}
function extractTextbox(el) {
  var content = _safeCall(el, "GetDocContent");
  if (!content) content = _safeCall(el, "GetContent");
  var runs = extractRunsFromContainer(content || el);
  var textParts = [];
  for (var i = 0; i < runs.length; i++) textParts.push(runs[i].text || "");
  var text = textParts.join("");
  if (!text) text = _str(_safeCall(content, "GetText") || _safeCall(el, "GetText"));
  if (!text && !runs.length) return null;
  var out = { class: "textbox", text: text, runs: runs };
  var g = extractGeometry(el);
  for (var k in g) out[k] = g[k];
  return out;
}
function extractChart(el) {
  var out = {
    class: "chart",
    chart_type: _str(_safeCall(el, "GetChartType") || _safeCall(el, "GetType") || "unknown"),
    rows: []
  };
  var series = _safeCall(el, "GetAllSeries") || _safeCall(el, "GetSeries");
  if (series && series.length) {
    for (var si = 0; si < series.length; si++) {
      var values = _safeCall(series[si], "GetValues") || _safeCall(series[si], "GetData");
      var row = [];
      if (values && values.length) {
        for (var vi = 0; vi < values.length; vi++) row.push(_str(values[vi]));
      }
      if (row.length) out.rows.push(row);
    }
  }
  var g = extractGeometry(el);
  for (var gk in g) out[gk] = g[gk];
  return out;
}
function extractHeaderFooterVariant(section, kind, variant) {
  var out = [];
  if (!section) return out;
  var getter = kind === "header" ? "GetHeader" : "GetFooter";
  if (typeof section[getter] !== "function") return out;
  var apiName = variant === "first" ? "title" : variant;
  var part = null;
  try { part = section[getter](apiName); } catch (e) { part = null; }
  if (!part) return out;
  var n = 0;
  try { n = part.GetElementsCount ? part.GetElementsCount() : 0; } catch (e2) { n = 0; }
  var firstAlign = undefined;
  for (var i = 0; i < n; i++) {
    var el = null;
    try { el = part.GetElement(i); } catch (e3) { el = null; }
    if (!el) continue;
    var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
    if (cls !== "paragraph") continue;
    var para = extractParagraph(el);
    if (!firstAlign && para.align) firstAlign = para.align;
    var entry = { variant: variant, text: para.text || "", runs: para.runs || [] };
    if (para.align) entry.align = para.align;
    out.push(entry);
  }
  var pageNumber = findPageNumber(part, firstAlign);
  if (pageNumber) {
    if (!out.length) out.push({ variant: variant, text: "", runs: [] });
    out[0].page_number = pageNumber;
  }
  return out;
}
function extractHeaderFooter(section, kind) {
  var out = [];
  var variants = ["default", "first", "even"];
  for (var v = 0; v < variants.length; v++) {
    var parts = extractHeaderFooterVariant(section, kind, variants[v]);
    for (var i = 0; i < parts.length; i++) out.push(parts[i]);
  }
  return out;
}
function sectionBreakType(section) {
  var t = _str(_safeCall(section, "GetType") || _safeCall(section, "GetStartType") || "").toLowerCase();
  var compact = t.replace(/[_\s-]/g, "");
  if (compact.indexOf("odd") >= 0) return "odd";
  if (compact.indexOf("even") >= 0) return "even";
  if (compact.indexOf("next") >= 0 || compact.indexOf("page") >= 0) return "next";
  return "continuous";
}
function extractSectionFlags(section) {
  var flags = { break_type: sectionBreakType(section) };
  var titlePage = _safeCall(section, "GetTitlePage");
  if (titlePage === undefined) titlePage = _safeCall(section, "IsTitlePage");
  if (titlePage !== undefined) flags.different_first_page = !!titlePage;
  var evenOdd = _safeCall(section, "GetEvenAndOddHdFtr");
  if (evenOdd === undefined) evenOdd = _safeCall(section, "IsEvenAndOddHdFtr");
  if (evenOdd === undefined) evenOdd = _safeCall(section, "GetEvenAndOddHeaders");
  if (evenOdd !== undefined) flags.odd_even_headers = !!evenOdd;
  var colCount = _safeCall(section, "GetColsCount");
  if (colCount === undefined) colCount = _safeCall(section, "GetColumnsCount");
  if (typeof colCount === "number") flags.columns = { count: colCount };
  return flags;
}
function extractNotes(doc, method, kind) {
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
    item.footnote_id = _str(_safeCall(note, "GetId") || _safeCall(note, "GetIndex") || i);
    item.note_kind = kind;
    notes.push(item);
  }
  return notes;
}
function extractComments(doc) {
  var out = [];
  var arr = _safeCall(doc, "GetAllComments");
  if (!arr) arr = _safeCall(doc, "GetComments");
  if (!arr || !arr.length) return out;
  for (var i = 0; i < arr.length; i++) {
    var c = arr[i];
    if (!c) continue;
    out.push({
      comment_id: _str(_safeCall(c, "GetId") || i),
      text: _str(_safeCall(c, "GetText") || _safeCall(c, "GetContents") || ""),
      quote: _str(_safeCall(c, "GetQuoteText") || _safeCall(c, "GetQuotedText") || "")
    });
  }
  return out;
}

var doc = Api.GetDocument();
var documentJson = null;
try {
  documentJson = doc.ToJSON(false, false, false, false, false, false);
  if (typeof documentJson === "string") {
    try { documentJson = JSON.parse(documentJson); } catch (eParse) {}
  }
} catch (eToJson) { documentJson = null; }

var bodyItems = [];
var count = 0;
try { count = doc.GetElementsCount(); } catch (eCount) { count = 0; }
for (var i = 0; i < count; i++) {
  var el = null;
  try { el = doc.GetElement(i); } catch (eEl) { el = null; }
  if (!el) continue;
  var cls = _str(_safeCall(el, "GetClassType")).toLowerCase();
  var item = null;
  if (cls === "table") item = extractTable(el);
  else if (cls === "chart" || !!_safeCall(el, "GetChartType")) item = extractChart(el);
  else if (isImageLike(el)) item = extractImage(el);
  else if (cls === "paragraph") {
    if (countPageBreaks(el) > 0 && !_str(_safeCall(el, "GetText")).replace(/\s/g, "")) {
      item = { class: "page_break", text: "", runs: [] };
    } else {
      item = extractParagraph(el);
      if (isCaptionStyle(item.style_names || [])) item.class = "caption";
    }
  } else if (cls.indexOf("drawing") >= 0 || cls.indexOf("shape") >= 0 || cls === "textbox") {
    if (isImageLike(el)) item = extractImage(el);
    else if (cls === "chart" || !!_safeCall(el, "GetChartType")) item = extractChart(el);
    else item = extractTextbox(el);
  }
  if (item) {
    item.element_index = i;
    bodyItems.push(item);
  }
}

function sectionRecord(section, index) {
  var flags = extractSectionFlags(section);
  var rec = {
    section_index: index,
    header: extractHeaderFooter(section, "header"),
    footer: extractHeaderFooter(section, "footer"),
    break_type: flags.break_type
  };
  if (flags.different_first_page !== undefined) rec.different_first_page = flags.different_first_page;
  if (flags.odd_even_headers !== undefined) rec.odd_even_headers = flags.odd_even_headers;
  if (flags.columns) rec.columns = flags.columns;
  return rec;
}

var sectionsOut = [];
var secs = null;
try { secs = doc.GetSections ? doc.GetSections() : null; } catch (eSec) { secs = null; }
if (secs && secs.length) {
  for (var si = 0; si < secs.length; si++) sectionsOut.push(sectionRecord(secs[si], si));
} else {
  var fallback = doc.GetFinalSection ? doc.GetFinalSection() : null;
  sectionsOut.push(sectionRecord(fallback, 0));
}

var footnotes = extractNotes(doc, "GetAllFootnotes", "footnote");
var endnotes = extractNotes(doc, "GetAllEndnotes", "endnote");
var comments = extractComments(doc);
var jsonStr = JSON.stringify({
  document: documentJson,
  body: bodyItems,
  sections: sectionsOut,
  footnotes: footnotes,
  endnotes: endnotes,
  comments: comments
});
"""

_ALIGN_OK = frozenset({"left", "center", "right", "justify"})
_HEADER_VARIANTS = frozenset({"default", "first", "even"})
_BREAK_TYPES = {
    "next": "next",
    "nextpage": "next",
    "next_page": "next",
    "continuous": "continuous",
    "even": "even",
    "evenpage": "even",
    "even_page": "even",
    "odd": "odd",
    "oddpage": "odd",
    "odd_page": "odd",
}
_BLOCK_KINDS = frozenset({"table", "image", "page_break", "textbox", "chart", "caption"})


def _item_class(item: dict[str, Any]) -> str:
    return str(item.get("class") or item.get("class_type") or item.get("type") or "paragraph").lower()


def _assign_run_indexes(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: list[dict[str, Any]] = []
    for index, run in enumerate(runs):
        item = dict(run)
        item["run_index"] = index
        if isinstance(item.get("hyperlink"), dict):
            url = str(item["hyperlink"].get("url") or "")
            text = str(item["hyperlink"].get("text") or item.get("text") or "")
            if url:
                item["hyperlink"] = {"url": url, "text": text}
            else:
                item.pop("hyperlink", None)
        indexed.append(item)
    return indexed


def _normalize_align(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text == "both":
        text = "justify"
    if text in _ALIGN_OK:
        return text
    return _align({"align": value}) if value else None


def _heading_level(item: dict[str, Any]) -> int | None:
    outline = _outline_level(item)
    if outline is not None:
        return min(6, outline + 1)
    return _heading_level_from_name(_style_names(item))


def _has_overlay_content(item: dict[str, Any]) -> bool:
    if _item_class(item) in _BLOCK_KINDS:
        return True
    if has_visible_text(item.get("text")):
        return True
    for run in item.get("runs") or []:
        if isinstance(run, dict) and has_visible_text(run.get("text")):
            return True
    if item.get("images") or item.get("page_number"):
        return True
    return False


def _overlay_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("body"), list):
        return [item for item in data["body"] if isinstance(item, dict)]
    items: list[dict[str, Any]] = []
    for section in data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for item in section.get("body") or []:
            if isinstance(item, dict):
                items.append(item)
    return items


def _normalize_image(raw: dict[str, Any], image_index: int | None = None) -> dict[str, Any]:
    alt = sanitize_text(raw.get("alt") or raw.get("text") or "image", trim_edges=True) or "image"
    image: dict[str, Any] = {"alt": alt}
    if image_index is not None:
        image["image_index"] = image_index
    elif raw.get("image_index") is not None:
        try:
            image["image_index"] = int(raw["image_index"])
        except (TypeError, ValueError):
            pass
    for key in ("width_pt", "height_pt"):
        if raw.get(key) is None:
            continue
        try:
            image[key] = float(raw[key])
        except (TypeError, ValueError):
            pass
    return image


def _normalize_break_type(value: Any) -> str | None:
    compact = str(value or "").strip().lower().replace(" ", "").replace("-", "_")
    compact = compact.replace("__", "_")
    return _BREAK_TYPES.get(compact) or _BREAK_TYPES.get(compact.replace("_", ""))


def _normalize_columns(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, int):
        return {"count": raw} if raw > 0 else None
    if not isinstance(raw, dict):
        return None
    try:
        count = int(raw.get("count", raw.get("columns", 0)))
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    columns: dict[str, Any] = {"count": count}
    widths = raw.get("widths") or raw.get("width_pt")
    if isinstance(widths, list):
        parsed: list[float] = []
        for item in widths:
            try:
                parsed.append(float(item))
            except (TypeError, ValueError):
                continue
        if parsed:
            columns["widths"] = parsed
    return columns


def _apply_geometry(target: dict[str, Any], raw: dict[str, Any]) -> None:
    for key in ("x_pt", "y_pt", "width_pt", "height_pt"):
        if raw.get(key) is None:
            continue
        try:
            target[key] = float(raw[key])
        except (TypeError, ValueError):
            pass


def _is_caption(item: dict[str, Any]) -> bool:
    if _item_class(item) == "caption":
        return True
    names = _style_names(item)
    return _latin_match(names, _LATIN_CAPTION) or _zh_match(names, _ZH_CAPTION)


def _normalize_page_number(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    page_number: dict[str, Any] = {}
    position = _normalize_align(raw.get("position"))
    if position in {"left", "center", "right"}:
        page_number["position"] = position
    if raw.get("format"):
        page_number["format"] = str(raw["format"])
    if raw.get("start") is not None:
        try:
            page_number["start"] = int(raw["start"])
        except (TypeError, ValueError):
            pass
    return page_number or {"position": "left"}


def _overlay_runs(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw = item.get("runs")
    runs = _assign_run_indexes(_normalize_runs(raw))
    if isinstance(raw, list):
        for dest, src in zip(runs, raw):
            if isinstance(src, dict) and src.get("footnote_id"):
                dest["footnote_id"] = str(src["footnote_id"])
    return runs


def _overlay_paragraph(block: dict[str, Any], item: dict[str, Any], warnings: list[str]) -> None:
    overlay_text = sanitize_text(item.get("text"), trim_edges=True)
    if not overlay_text:
        overlay_text = "".join(str(run.get("text") or "") for run in item.get("runs") or [])
        overlay_text = sanitize_text(overlay_text, trim_edges=True)
    block_text = sanitize_text(block.get("text"), trim_edges=True)
    if overlay_text and block_text and overlay_text != block_text:
        warnings.append(f"block {block.get('block_index')} text mismatch; style skipped")
        return

    runs = _overlay_runs(item)
    if runs:
        block["runs"] = runs
    align = _normalize_align(item.get("align"))
    if align:
        block["align"] = align
    list_type = str(item.get("list_type") or "").strip().lower()
    if list_type in {"bullet", "number"}:
        block["list_type"] = list_type
    elif item.get("has_numbering") or item.get("has_bullets"):
        block["list_type"] = "bullet" if item.get("has_bullets") else "number"
    if item.get("list_level") is not None:
        try:
            block["list_level"] = int(item["list_level"])
        except (TypeError, ValueError):
            pass
    heading_level = _heading_level(item)
    if heading_level is not None:
        block["heading_level"] = heading_level
    if _is_caption(item):
        block["type"] = "caption"
    images: list[dict[str, Any]] = []
    for index, raw in enumerate(item.get("images") or []):
        if isinstance(raw, dict):
            images.append(_normalize_image(raw, raw.get("image_index", index)))
    if images:
        block["images"] = images


def _overlay_table(block: dict[str, Any], item: dict[str, Any]) -> None:
    cells: list[dict[str, Any]] = []
    raw_cells = item.get("cells")
    if isinstance(raw_cells, list) and raw_cells and isinstance(raw_cells[0], dict):
        for raw in raw_cells:
            if not isinstance(raw, dict):
                continue
            try:
                row = int(raw["row"])
                col = int(raw["col"])
            except (KeyError, TypeError, ValueError):
                continue
            cell: dict[str, Any] = {
                "row": row,
                "col": col,
                "text": _normalize_word_cell(raw.get("text")),
            }
            align = _normalize_align(raw.get("align"))
            if align:
                cell["align"] = align
            runs = _overlay_runs(raw)
            if runs:
                cell["runs"] = runs
            cells.append(cell)
    elif isinstance(item.get("rows"), list):
        for row_index, row in enumerate(item["rows"]):
            cells_in_row = row if isinstance(row, (list, tuple)) else [row]
            for col_index, cell_raw in enumerate(cells_in_row):
                cells.append({
                    "row": row_index,
                    "col": col_index,
                    "text": _normalize_word_cell(cell_raw),
                })
    if cells:
        block["cells"] = cells


def _apply_image_block(block: dict[str, Any], item: dict[str, Any]) -> None:
    image = _normalize_image(item)
    block["type"] = "image"
    block["alt"] = image["alt"]
    block["text"] = image["alt"]
    for key in ("width_pt", "height_pt"):
        if key in image:
            block[key] = image[key]


def _apply_page_break_block(block: dict[str, Any]) -> None:
    block["type"] = "page_break"
    block.pop("text", None)


def _apply_textbox_block(block: dict[str, Any], item: dict[str, Any]) -> None:
    block["type"] = "textbox"
    text = sanitize_text(item.get("text"), trim_edges=True)
    if not text:
        text = "".join(str(run.get("text") or "") for run in item.get("runs") or [])
        text = sanitize_text(text, trim_edges=True)
    block["text"] = text
    runs = _overlay_runs(item)
    if runs:
        block["runs"] = runs
    _apply_geometry(block, item)


def _apply_chart_block(block: dict[str, Any], item: dict[str, Any]) -> None:
    block["type"] = "chart"
    block["chart_type"] = str(item.get("chart_type") or item.get("type") or "unknown")
    rows = item.get("rows")
    block["rows"] = rows if isinstance(rows, list) else []
    _apply_geometry(block, item)


def _ensure_typed_block(
    blocks: list[dict[str, Any]],
    block_map: dict[int, dict[str, Any]],
    index: int,
    item: dict[str, Any],
    kind: str,
) -> dict[str, Any]:
    block = block_map.get(index)
    if block is None:
        block = {"block_index": index, "type": kind}
        blocks.append(block)
        block_map[index] = block
    return block


def apply_fine_overlay(blocks: list[dict[str, Any]], data: dict[str, Any]) -> list[str]:
    """Attach live-walk style onto ToJSON blocks. Does not compact block_index."""
    warnings: list[str] = []
    items = _overlay_items(data)
    by_index: dict[int, dict[str, Any]] = {}
    sequential: list[dict[str, Any]] = []
    for item in items:
        if item.get("element_index") is not None:
            try:
                by_index[int(item["element_index"])] = item
                continue
            except (TypeError, ValueError):
                pass
        sequential.append(item)

    if by_index:
        block_map = {int(block["block_index"]): block for block in blocks}
        for index, item in by_index.items():
            kind = _item_class(item)
            block = block_map.get(index)
            if kind == "image":
                if block is None:
                    image_block = {"block_index": index, "type": "image"}
                    _apply_image_block(image_block, item)
                    blocks.append(image_block)
                    block_map[index] = image_block
                elif block.get("type") != "image":
                    _overlay_paragraph(block, {"images": [item], "text": block.get("text"), "runs": []}, warnings)
                    if "images" not in block:
                        block["images"] = [_normalize_image(item, 0)]
                else:
                    _apply_image_block(block, item)
                continue
            if kind == "page_break":
                block = _ensure_typed_block(blocks, block_map, index, item, "page_break")
                _apply_page_break_block(block)
                continue
            if kind == "textbox":
                text = sanitize_text(item.get("text"), trim_edges=True)
                runs = item.get("runs") or []
                if not text and not runs:
                    continue
                block = _ensure_typed_block(blocks, block_map, index, item, "textbox")
                _apply_textbox_block(block, item)
                continue
            if kind == "chart":
                block = _ensure_typed_block(blocks, block_map, index, item, "chart")
                _apply_chart_block(block, item)
                continue
            if kind == "caption" or _is_caption(item):
                if block is None:
                    block = _ensure_typed_block(blocks, block_map, index, item, "caption")
                _overlay_paragraph(block, item, warnings)
                block["type"] = "caption"
                continue
            if block is None:
                continue
            if block.get("type") == "table" or kind == "table":
                _overlay_table(block, item)
            else:
                _overlay_paragraph(block, item, warnings)
        _attach_caption_targets(blocks)
        blocks.sort(key=lambda block: int(block.get("block_index", 0)))
        return warnings

    overlay_iter = [item for item in sequential if _has_overlay_content(item)]
    offset = 0
    for block in blocks:
        if offset >= len(overlay_iter):
            break
        item = overlay_iter[offset]
        offset += 1
        kind = _item_class(item)
        if block.get("type") == "table" or kind == "table":
            _overlay_table(block, item)
        elif kind == "image" or block.get("type") == "image":
            _apply_image_block(block, item)
        else:
            _overlay_paragraph(block, item, warnings)
    _attach_caption_targets(blocks)
    return warnings


def _attach_caption_targets(blocks: list[dict[str, Any]]) -> None:
    by_index = {int(block.get("block_index", i)): block for i, block in enumerate(blocks)}
    ordered = sorted(by_index)
    for index in ordered:
        block = by_index[index]
        if block.get("type") != "caption":
            continue
        prev = None
        for candidate in reversed(ordered):
            if candidate < index:
                prev = by_index[candidate]
                break
        if prev and prev.get("type") in {"table", "image", "chart"}:
            block["target_block_index"] = prev.get("block_index")


def normalize_fine_sections(raw: Any) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return sections
    for index, section in enumerate(raw):
        if not isinstance(section, dict):
            continue
        try:
            section_index = int(section.get("section_index", index))
        except (TypeError, ValueError):
            section_index = index
        entry: dict[str, Any] = {"section_index": section_index, "header": [], "footer": []}
        break_type = _normalize_break_type(section.get("break_type"))
        if break_type:
            entry["break_type"] = break_type
        if section.get("different_first_page") is not None:
            entry["different_first_page"] = bool(section["different_first_page"])
        if section.get("odd_even_headers") is not None:
            entry["odd_even_headers"] = bool(section["odd_even_headers"])
        columns = _normalize_columns(section.get("columns"))
        if columns:
            entry["columns"] = columns
        for kind in ("header", "footer"):
            parts: list[dict[str, Any]] = []
            for part in section.get(kind) or []:
                if not isinstance(part, dict):
                    continue
                variant = str(part.get("variant") or "default").strip().lower()
                if variant not in _HEADER_VARIANTS:
                    continue
                text = sanitize_text(part.get("text"), trim_edges=True)
                runs = _overlay_runs(part)
                page_number = _normalize_page_number(part.get("page_number"))
                if not has_visible_text(text) and not runs and not page_number:
                    continue
                item: dict[str, Any] = {"variant": variant, "text": text, "runs": runs}
                align = _normalize_align(part.get("align"))
                if align:
                    item["align"] = align
                if page_number:
                    item["page_number"] = page_number
                parts.append(item)
            entry[kind] = parts
        sections.append(entry)
    return sections


def _note_ref_from_blocks(blocks: list[dict[str, Any]], footnote_id: str) -> dict[str, int] | None:
    for block in blocks:
        for run in block.get("runs") or []:
            if not isinstance(run, dict):
                continue
            if str(run.get("footnote_id") or "") == footnote_id:
                ref = {"block_index": int(block.get("block_index", 0))}
                if run.get("run_index") is not None:
                    ref["run_index"] = int(run["run_index"])
                return ref
    return None


def _note_ref_from_raw_body(raw_body: Any, footnote_id: str) -> dict[str, int] | None:
    if not isinstance(raw_body, list):
        return None
    for item in raw_body:
        if not isinstance(item, dict):
            continue
        for run_index, run in enumerate(item.get("runs") or []):
            if not isinstance(run, dict):
                continue
            if str(run.get("footnote_id") or "") != footnote_id:
                continue
            try:
                return {"block_index": int(item["element_index"]), "run_index": run_index}
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _comment_anchor_from_quote(blocks: list[dict[str, Any]], quote: str) -> dict[str, int] | None:
    if not quote:
        return None
    for block in blocks:
        text = str(block.get("text") or "")
        if quote in text:
            anchor = {"block_index": int(block.get("block_index", 0))}
            for run in block.get("runs") or []:
                if isinstance(run, dict) and quote in str(run.get("text") or ""):
                    if run.get("run_index") is not None:
                        anchor["run_index"] = int(run["run_index"])
                    break
            return anchor
    return None


def normalize_fine_notes(
    raw: Any,
    blocks: list[dict[str, Any]],
    *,
    kind: str,
    raw_body: Any = None,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return notes
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        text = sanitize_text(item.get("text"), trim_edges=True)
        runs = _overlay_runs(item)
        if not has_visible_text(text) and not runs:
            continue
        note_id = str(item.get("footnote_id") or item.get("id") or index)
        note: dict[str, Any] = {
            "footnote_id": note_id,
            "text": text,
            "runs": runs,
        }
        ref = _note_ref_from_blocks(blocks, note_id) or _note_ref_from_raw_body(raw_body, note_id)
        if ref:
            note.update(ref)
        notes.append(note)
    return notes


def normalize_fine_comments(raw: Any, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return comments
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        text = sanitize_text(item.get("text"), trim_edges=True)
        if not has_visible_text(text):
            continue
        comment: dict[str, Any] = {
            "comment_id": str(item.get("comment_id") or item.get("id") or index),
            "text": text,
        }
        anchor = _comment_anchor_from_quote(blocks, str(item.get("quote") or ""))
        if item.get("block_index") is not None:
            try:
                comment["block_index"] = int(item["block_index"])
            except (TypeError, ValueError):
                pass
        elif anchor:
            comment.update(anchor)
        if item.get("run_index") is not None:
            try:
                comment["run_index"] = int(item["run_index"])
            except (TypeError, ValueError):
                pass
        comments.append(comment)
    return comments


def parse_fine_sidecar(
    raw: dict[str, Any] | str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], dict[str, Any]]:
    """Return (blocks, sections, warnings, extras) from the combined ToJSON + walk sidecar."""
    from aiecs.tools.office_tool.word.parser.document import parse_document_json

    if isinstance(raw, str):
        import json

        data = json.loads(raw)
    else:
        data = raw if isinstance(raw, dict) else {}

    document = data.get("document") if isinstance(data.get("document"), dict) else data
    if "document" in data and ("sections" in data or "body" in data):
        document = data.get("document") or {}
    blocks = parse_document_json(document or {})
    warnings = apply_fine_overlay(blocks, data)
    sections = normalize_fine_sections(data.get("sections"))
    extras = {
        "footnotes": normalize_fine_notes(
            data.get("footnotes"), blocks, kind="footnote", raw_body=_overlay_items(data),
        ),
        "endnotes": normalize_fine_notes(
            data.get("endnotes"), blocks, kind="endnote", raw_body=_overlay_items(data),
        ),
        "comments": normalize_fine_comments(data.get("comments"), blocks),
    }
    return blocks, sections, warnings, extras
