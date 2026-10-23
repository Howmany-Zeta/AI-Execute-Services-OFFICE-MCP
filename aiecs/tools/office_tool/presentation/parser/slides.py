"""
Parse ONLYOFFICE SlidesToJSON output into slides[] and layouts[] (ADR-016).
"""

from __future__ import annotations

import json
import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text
from aiecs.tools.office_tool.word.parser.structured import _normalize_runs

_ALIGN_OK = frozenset({"left", "center", "right", "justify"})

_PICTURE_TYPES = frozenset({"image", "picture", "pic"})
_TEXTBOX_TYPES = frozenset({"textbox", "txbox", "text_box"})

_SLIDES_EXTRACT_HELPERS = r"""
function _str(v) { return (v === undefined || v === null) ? "" : String(v); }
function _safeCall(obj, name) {
  if (!obj || typeof obj[name] !== "function") return undefined;
  try { return obj[name](); } catch (e) { return undefined; }
}
function placeholderType(shape) {
  var ph = _safeCall(shape, "GetPlaceholder");
  if (!ph) return "";
  var t = _safeCall(ph, "GetType");
  if (t === undefined) t = _safeCall(ph, "GetPlaceholderType");
  return t ? _str(t) : "";
}
function shapeText(shape) {
  if (!shape) return "";
  var content = null;
  if (shape.GetDocContent) content = _safeCall(shape, "GetDocContent");
  if (!content && shape.GetContent) content = _safeCall(shape, "GetContent");
  if (content) {
    var t = _safeCall(content, "GetText");
    if (t) return _str(t);
  }
  return _str(_safeCall(shape, "GetText"));
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
  return undefined;
}
function emuToPt(v) {
  if (typeof v !== "number") return undefined;
  if (Math.abs(v) > 1000) return v / 12700.0;
  return v;
}
function extractRun(run) {
  if (!run) return null;
  var out = { text: _str(_safeCall(run, "GetText")) };
  var bold = _safeCall(run, "GetBold");
  if (bold !== undefined) out.bold = !!bold;
  var italic = _safeCall(run, "GetItalic");
  if (italic !== undefined) out.italic = !!italic;
  var underline = _safeCall(run, "GetUnderline");
  if (underline !== undefined && underline !== null) {
    var s = String(underline).toLowerCase();
    out.underline = !(s === "false" || s === "none" || underline === false);
  }
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
  if (font) out.font_name = _str(font);
  var size = _safeCall(run, "GetFontSize");
  if (typeof size === "number") out.font_size_pt = size;
  var color = _safeCall(run, "GetColor");
  var chex = _colorToHex(color);
  if (chex) out.font_color = chex;
  return out;
}
function extractRunsFromContent(content) {
  var runs = [];
  if (!content) return runs;
  var n = 0;
  try { n = content.GetElementsCount ? content.GetElementsCount() : 0; } catch (e) { n = 0; }
  if (!n) {
    var t = _safeCall(content, "GetText");
    if (t) runs.push({ text: _str(t) });
    return runs;
  }
  for (var i = 0; i < n; i++) {
    var para = null;
    try { para = content.GetElement(i); } catch (e2) { para = null; }
    if (!para) continue;
    var pn = 0;
    try { pn = para.GetElementsCount ? para.GetElementsCount() : 0; } catch (e3) { pn = 0; }
    if (!pn) {
      var pt = _safeCall(para, "GetText");
      if (pt) runs.push({ text: _str(pt) });
      continue;
    }
    for (var j = 0; j < pn; j++) {
      var child = null;
      try { child = para.GetElement(j); } catch (e4) { child = null; }
      if (!child) continue;
      var run = extractRun(child);
      if (run) runs.push(run);
    }
  }
  return runs;
}
function firstAlign(content) {
  if (!content || !content.GetElement) return undefined;
  try {
    var para = content.GetElement(0);
    var jc = _safeCall(para, "GetJc");
    return jc !== undefined ? _str(jc) : undefined;
  } catch (e) { return undefined; }
}
function dumpShape(shape) {
  var cls = _str(_safeCall(shape, "GetClassType")).toLowerCase();
  var preset = _str(_safeCall(shape, "GetGeometryType") || _safeCall(shape, "GetPresetGeom") || _safeCall(shape, "GetGeometryPreset"));
  var txBox = _safeCall(shape, "IsTxBox");
  if (txBox === undefined) txBox = _safeCall(shape, "GetTxBox");
  if (txBox === undefined) txBox = _safeCall(shape, "IsTextBox");
  var content = null;
  if (shape.GetDocContent) content = _safeCall(shape, "GetDocContent");
  if (!content && shape.GetContent) content = _safeCall(shape, "GetContent");
  var runs = extractRunsFromContent(content);
  var align = firstAlign(content);
  var out = {
    class_type: cls,
    is_picture: cls === "image" || cls === "picture" || cls === "pic" || cls === "drawing" || !!_safeCall(shape, "GetImage") || !!_safeCall(shape, "GetOleObject"),
    is_textbox: preset.toLowerCase() === "textbox" || preset.toLowerCase() === "txbox" || txBox === true,
    placeholder_type: placeholderType(shape),
    text: shapeText(shape),
    runs: runs
  };
  if (align) out.align = align;
  var x = emuToPt(_safeCall(shape, "GetPosX") || _safeCall(shape, "GetX") || _safeCall(shape, "GetLeft"));
  var y = emuToPt(_safeCall(shape, "GetPosY") || _safeCall(shape, "GetY") || _safeCall(shape, "GetTop"));
  var w = emuToPt(_safeCall(shape, "GetWidth"));
  var h = emuToPt(_safeCall(shape, "GetHeight"));
  if (x !== undefined) out.x_pt = x;
  if (y !== undefined) out.y_pt = y;
  if (w !== undefined) out.width_pt = w;
  if (h !== undefined) out.height_pt = h;
  return out;
}
function collectLayoutShapes(pres, layoutNames) {
  var items = [];
  var warning = "";
  var layouts = null;
  try {
    var master = pres.GetMaster ? pres.GetMaster() : null;
    if (master && master.GetAllLayouts) layouts = master.GetAllLayouts();
    else if (master && master.GetLayoutsCount) {
      layouts = [];
      var n = master.GetLayoutsCount();
      for (var i = 0; i < n; i++) layouts.push(master.GetLayout(i));
    }
  } catch (e) { layouts = null; }
  if (!layouts || !layouts.length) {
    return { items: items, warning: "layout shapes unavailable" };
  }
  var wanted = {};
  for (var wi = 0; wi < layoutNames.length; wi++) wanted[layoutNames[wi]] = true;
  for (var li = 0; li < layouts.length; li++) {
    var layout = layouts[li];
    var name = _str(_safeCall(layout, "GetName") || _safeCall(layout, "GetLayoutName"));
    if (!name || !wanted[name]) continue;
    var dumped = [];
    var arr = null;
    try { arr = layout.GetAllShapes ? layout.GetAllShapes() : null; } catch (e2) { arr = null; }
    if (arr) {
      for (var si = 0; si < arr.length; si++) dumped.push(dumpShape(arr[si]));
    }
    items.push({ layout_name: name, shapes: dumped });
  }
  return { items: items, warning: warning };
}
function notesText(slide) {
  var page = _safeCall(slide, "GetNotesPage");
  if (!page) return "";
  var t = _safeCall(page, "GetBodyShapeText");
  if (t) return _str(t);
  var body = _safeCall(page, "GetBodyShape");
  if (body) {
    var st = shapeText(body);
    if (st) return st;
  }
  var shapes = null;
  try { shapes = page.GetAllShapes ? page.GetAllShapes() : null; } catch (e) { shapes = null; }
  if (shapes && shapes.length) return shapeText(shapes[0]);
  return "";
}
function slideLayoutName(slide) {
  var lo = _safeCall(slide, "GetLayout");
  if (!lo) return "";
  return _str(_safeCall(lo, "GetName") || _safeCall(lo, "GetLayoutName") || _safeCall(lo, "GetTitle"));
}
function slideList(tojson) {
  if (!tojson) return [];
  if (typeof Array !== "undefined" && Array.isArray && Array.isArray(tojson)) return tojson;
  if (tojson.slides && tojson.slides.length) return tojson.slides;
  if (tojson.Slides && tojson.Slides.length) return tojson.Slides;
  return [];
}
function collectLayouts(tojson, slides) {
  var names = [];
  var seen = {};
  function add(n) {
    n = _str(n);
    if (n && !seen[n]) { seen[n] = true; names.push(n); }
  }
  if (tojson && tojson.layouts) {
    for (var i = 0; i < tojson.layouts.length; i++) add(tojson.layouts[i]);
  }
  if (tojson && tojson.layoutNames) {
    for (var j = 0; j < tojson.layoutNames.length; j++) add(tojson.layoutNames[j]);
  }
  for (var k = 0; k < slides.length; k++) {
    if (slides[k]) add(slides[k].layout);
  }
  return names;
}
"""

_SLIDES_EXTRACT_TAIL = r"""
var toSlides = slideList(tojson);
var slidesOut = [];
for (var si = start; si <= last; si++) {
  var slide = pres.GetSlideByIndex(si);
  var meta = toSlides[si - start] || {};
  var roots = [];
  var shapes = null;
  try { shapes = slide && slide.GetAllShapes ? slide.GetAllShapes() : null; } catch (e2) { shapes = null; }
  if (shapes) {
    for (var i = 0; i < shapes.length; i++) roots.push(dumpShape(shapes[i]));
  }
  var notes = notesText(slide);
  if (!notes) notes = _str(meta.notes || meta.notesText);
  slidesOut.push({
    slide_index: si,
    layout: _str(meta.layout || meta.layoutName || meta.layout_name || slideLayoutName(slide)),
    title: _str(meta.title),
    notes: notes,
    shapes: roots
  });
}
var layoutNames = collectLayouts(tojson, slidesOut);
var layoutPack = collectLayoutShapes(pres, layoutNames);
var jsonStr = JSON.stringify({
  layouts: layoutNames,
  slides: slidesOut,
  layout_shapes: layoutPack.items,
  layout_shapes_warning: layoutPack.warning
});
"""


def build_slides_extract_body(start: int = 0, end: int | None = None) -> str:
    """Builder extract body: SlidesToJSON + GetAllShapes (ADR-016 / ADR-045)."""
    if end is None:
        range_setup = (
            f"var start = {start};\n"
            "var last = pres.GetSlidesCount() - 1;\n"
            "var tojson = null;\n"
            f"try {{ tojson = pres.SlidesToJSON({start}, last, false, false, false, false); }}"
            " catch (e) { tojson = null; }"
        )
    else:
        range_setup = (
            f"var start = {start};\n"
            f"var last = {end};\n"
            "var tojson = null;\n"
            f"try {{ tojson = pres.SlidesToJSON({start}, {end}, false, false, false, false); }}"
            " catch (e) { tojson = null; }"
        )
    return (
        _SLIDES_EXTRACT_HELPERS
        + "var pres = Api.GetPresentation();\n"
        + range_setup
        + _SLIDES_EXTRACT_TAIL
    )


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text)) if text else 0


def _infer_role(shape: dict[str, Any]) -> str | None:
    placeholder = (shape.get("placeholder_type") or shape.get("placeholderType") or "").lower()
    if placeholder == "title" or shape.get("role") == "title":
        return "title"
    if placeholder in ("body", "content") or shape.get("role") == "body":
        return "body"
    if placeholder == "subtitle" or shape.get("role") == "subtitle":
        return "subtitle"
    return shape.get("role")


def _shape_text(raw: dict[str, Any]) -> str:
    text = raw.get("text") or raw.get("content") or ""
    if isinstance(text, list):
        return " ".join(sanitize_text(t, trim_edges=True) for t in text if has_visible_text(t))
    return sanitize_text(text, trim_edges=True)


def _is_picture(raw: dict[str, Any]) -> bool:
    if raw.get("is_picture") is True:
        return True
    if str(raw.get("type") or "").strip().lower() == "image":
        return True
    return str(raw.get("class_type") or "").strip().lower() in _PICTURE_TYPES


def _is_textbox(raw: dict[str, Any]) -> bool:
    if raw.get("is_textbox") is True:
        return True
    if raw.get("placeholder_type") or raw.get("placeholderType"):
        return True
    return str(raw.get("type") or "").strip().lower() in _TEXTBOX_TYPES


def _classify_type(raw: dict[str, Any], text: str) -> str | None:
    if _is_picture(raw):
        return "image"
    if has_visible_text(text):
        return "text"
    if _is_textbox(raw):
        return "shape"
    return None


def _normalize_shape(raw: dict[str, Any], shape_index: int) -> dict[str, Any] | None:
    text = _shape_text(raw)
    shape_type = _classify_type(raw, text)
    if shape_type is None:
        return None
    shape: dict[str, Any] = {
        "shape_index": shape_index,
        "type": shape_type,
        "text": text,
    }
    placeholder = raw.get("placeholder_type") or raw.get("placeholderType")
    if placeholder:
        shape["placeholder_type"] = placeholder
    role = _infer_role(raw)
    if role:
        shape["role"] = role
    runs = _normalize_runs(raw.get("runs"))
    if runs:
        for index, run in enumerate(runs):
            run["run_index"] = index
        shape["runs"] = runs
    align = str(raw.get("align") or "").strip().lower()
    if align == "both":
        align = "justify"
    if align in _ALIGN_OK:
        shape["align"] = align
    for key in ("x_pt", "y_pt", "width_pt", "height_pt"):
        if raw.get(key) is None:
            continue
        try:
            shape[key] = float(raw[key])
        except (TypeError, ValueError):
            pass
    return shape


def _normalize_slide(raw: dict[str, Any], slide_index: int) -> dict[str, Any]:
    if raw.get("slide_index") is not None:
        try:
            slide_index = int(raw["slide_index"])
        except (TypeError, ValueError):
            pass
    layout = raw.get("layout") or raw.get("layoutName") or raw.get("layout_name") or ""
    shapes_raw = raw.get("shapes") or raw.get("spTree") or raw.get("content") or []
    shapes: list[dict[str, Any]] = []
    if isinstance(shapes_raw, list):
        for si, s in enumerate(shapes_raw):
            if not isinstance(s, dict):
                continue
            shape = _normalize_shape(s, si)
            if shape is not None:
                shapes.append(shape)

    title = sanitize_text(raw.get("title") or "", trim_edges=True)
    if not title:
        for sh in shapes:
            if sh.get("role") == "title" and has_visible_text(sh.get("text")):
                title = sh["text"]
                break

    slide: dict[str, Any] = {
        "slide_index": slide_index,
        "title": title,
        "layout": layout,
        "shapes": shapes,
    }
    notes = sanitize_text(raw.get("notes") or raw.get("notesText") or "", trim_edges=True)
    if notes:
        slide["notes"] = notes
    return slide


def _iter_slides_raw(data: dict | list) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    if isinstance(data, dict):
        for key in ("slides", "Slides", "content"):
            val = data.get(key)
            if isinstance(val, list):
                return [s for s in val if isinstance(s, dict)]
        if "layout" in data or "shapes" in data:
            return [data]
    return []


def parse_slides_json(raw: dict | str) -> tuple[list[dict[str, Any]], list[str]]:
    """
    SlidesToJSON parse → (slides[], layouts[]).
    layouts[] is deduplicated layout names from slides (ADR-016 enum source).
    """
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    layouts_from_meta: list[str] = []
    if isinstance(data, dict):
        meta_layouts = data.get("layouts") or data.get("layoutNames")
        if isinstance(meta_layouts, list):
            layouts_from_meta = [str(x) for x in meta_layouts if x]

    slides_raw = _iter_slides_raw(data)
    slides = [_normalize_slide(s, i) for i, s in enumerate(slides_raw)]

    layout_set: list[str] = []
    seen: set[str] = set()
    for name in layouts_from_meta:
        if name and name not in seen:
            seen.add(name)
            layout_set.append(name)
    for slide in slides:
        layout = slide.get("layout") or ""
        if layout and layout not in seen:
            seen.add(layout)
            layout_set.append(layout)

    return slides, layout_set


def normalize_layout_shapes(data: dict[str, Any], layouts: list[str]) -> dict[str, Any]:
    extras: dict[str, Any] = {"layout_shapes": []}
    raw_items = data.get("layout_shapes")
    allowed = set(layouts)
    if isinstance(raw_items, list):
        items: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("layout_name") or item.get("name") or "")
            if not name or name not in allowed:
                continue
            shapes: list[dict[str, Any]] = []
            for index, raw in enumerate(item.get("shapes") or []):
                if not isinstance(raw, dict):
                    continue
                shape = _normalize_shape(raw, index)
                if shape is not None:
                    shapes.append(shape)
            items.append({"layout_name": name, "shapes": shapes})
        extras["layout_shapes"] = items
    warning = str(data.get("layout_shapes_warning") or "").strip()
    if warning:
        extras["_warnings"] = [warning]
    return extras


def slides_to_outline(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return {slide_index, title} only."""
    return [{"slide_index": s.get("slide_index", i), "title": s.get("title", "")} for i, s in enumerate(slides)]


def slides_to_text(slides: list[dict[str, Any]]) -> str:
    """Join slides with \\n--- slide N ---\\n separators."""
    parts: list[str] = []
    for slide in slides:
        idx = slide.get("slide_index", 0)
        parts.append(f"--- slide {idx + 1} ---")
        if has_visible_text(slide.get("title")):
            parts.append(str(slide["title"]))
        for shape in slide.get("shapes") or []:
            text = shape.get("text") or ""
            if has_visible_text(text):
                parts.append(text)
        if has_visible_text(slide.get("notes")):
            parts.append(f"[notes] {slide['notes']}")
    return "\n".join(parts)


def apply_slide_range(
    slides: list[dict[str, Any]],
    slide_range: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    """Inclusive filter by slide_index."""
    if not slide_range:
        return slides
    start, end = slide_range
    return [s for s in slides if start <= s.get("slide_index", 0) <= end]


def word_count_from_slides(slides: list[dict[str, Any]]) -> int:
    parts: list[str] = []
    for slide in slides:
        if slide.get("title"):
            parts.append(str(slide["title"]))
        for shape in slide.get("shapes") or []:
            if shape.get("text"):
                parts.append(str(shape["text"]))
        if slide.get("notes"):
            parts.append(str(slide["notes"]))
    return _count_words(" ".join(parts))
