"""
Builder sidecar extraction and normalization for presentation structured reads.

JS dumps a shape tree with EMU geometry. Python flattens, converts units,
assigns shape_id, and fails the whole read when coordinates or canvas are missing.
"""

from __future__ import annotations

import re
from typing import Any

from aiecs.tools.office_tool.core.text_sanitize import has_visible_text, sanitize_text
from aiecs.tools.office_tool.word.parser.structured import _align, _normalize_runs, _to_hex_color

EMU_PER_PT = 12700.0

STRUCTURED_PRESENTATION_EXTRACT_BODY = r"""
function _str(v) { return (v === undefined || v === null) ? "" : String(v); }
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
    if (t.toLowerCase() === "none") return "none";
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
  var r = color.r !== undefined ? color.r : _safeCall(color, "GetR");
  var g = color.g !== undefined ? color.g : _safeCall(color, "GetG");
  var b = color.b !== undefined ? color.b : _safeCall(color, "GetB");
  if (r !== undefined && g !== undefined && b !== undefined) {
    return "#" + _hex2(r) + _hex2(g) + _hex2(b);
  }
  return undefined;
}
function _emu(shape, names) {
  for (var i = 0; i < names.length; i++) {
    var v = _safeCall(shape, names[i]);
    if (typeof v === "number") return v;
  }
  return null;
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
    try { para = content.GetElement(i); } catch (e) { para = null; }
    if (!para) continue;
    var pn = 0;
    try { pn = para.GetElementsCount ? para.GetElementsCount() : 0; } catch (e2) { pn = 0; }
    if (!pn) {
      var pt = _safeCall(para, "GetText");
      if (pt) runs.push({ text: _str(pt) });
      continue;
    }
    for (var j = 0; j < pn; j++) {
      var child = null;
      try { child = para.GetElement(j); } catch (e3) { child = null; }
      if (!child) continue;
      var cls = _str(_safeCall(child, "GetClassType")).toLowerCase();
      if (cls === "hyperlink") {
        var hn = 0;
        try { hn = child.GetElementsCount ? child.GetElementsCount() : 0; } catch (e4) { hn = 0; }
        for (var k = 0; k < hn; k++) {
          var hr = extractRun(child.GetElement(k));
          if (hr) runs.push(hr);
        }
      } else {
        var run = extractRun(child);
        if (run) runs.push(run);
      }
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
function childShapes(shape) {
  if (!shape || typeof shape.GetAllShapes !== "function") return null;
  try {
    var kids = shape.GetAllShapes();
    if (kids && kids.length > 0) return kids;
    return [];
  } catch (e) {
    return null;
  }
}
function placeholderType(shape) {
  var ph = _safeCall(shape, "GetPlaceholder");
  if (!ph) return "";
  var t = _safeCall(ph, "GetType");
  if (t === undefined) t = _safeCall(ph, "GetPlaceholderType");
  return t ? _str(t) : "";
}
function extractStyle(shape, content) {
  var style = {};
  var fill = _safeCall(shape, "GetFill");
  if (fill !== undefined && fill !== null) {
    var fillType = _str(_safeCall(fill, "GetType")).toLowerCase();
    if (fillType === "none" || fillType === "nofill") style.fill = "none";
    else {
      var fc = _colorToHex(fill);
      if (!fc) fc = _colorToHex(_safeCall(fill, "GetSolidFill") || _safeCall(fill, "GetColor"));
      if (fc) style.fill = fc;
    }
  }
  var stroke = _safeCall(shape, "GetStroke");
  if (stroke !== undefined && stroke !== null) {
    var stType = _str(_safeCall(stroke, "GetType")).toLowerCase();
    if (stType === "none" || stType === "noline") {
      style.line_color = "none";
      style.line_dash = "none";
    } else {
      var lc = _colorToHex(_safeCall(stroke, "GetColor"));
      if (lc) style.line_color = lc;
      var lw = _safeCall(stroke, "GetWidth");
      if (typeof lw === "number") style.line_width_emu = lw;
      var dash = _safeCall(stroke, "GetPrstDash");
      if (dash === undefined) dash = _safeCall(stroke, "GetDashType");
      if (dash !== undefined && dash !== null) style.line_dash_raw = _str(dash);
    }
  }
  if (content) {
    var runs = extractRunsFromContent(content);
    if (runs.length) {
      var r0 = runs[0];
      if (r0.font_name) style.font_name = r0.font_name;
      if (r0.font_size_pt !== undefined) style.font_size_pt = r0.font_size_pt;
      if (r0.font_color) style.font_color = r0.font_color;
      if (r0.bold !== undefined) style.bold = r0.bold;
      if (r0.italic !== undefined) style.italic = r0.italic;
    }
    var al = firstAlign(content);
    if (al) style.align = al;
  }
  return style;
}
function dumpShape(shape) {
  var cls = _str(_safeCall(shape, "GetClassType")).toLowerCase();
  var kids = childShapes(shape);
  var isGroup = cls === "group" || cls === "groupshape" || cls === "grpsp";
  var content = null;
  if (shape.GetDocContent) content = _safeCall(shape, "GetDocContent");
  if (!content && shape.GetContent) content = _safeCall(shape, "GetContent");
  var runs = extractRunsFromContent(content);
  var text = "";
  if (runs.length) {
    var parts = [];
    for (var i = 0; i < runs.length; i++) parts.push(runs[i].text || "");
    text = parts.join("");
  } else {
    text = _str(_safeCall(shape, "GetText"));
  }
  var preset = _str(_safeCall(shape, "GetGeometryType") || _safeCall(shape, "GetPresetGeom") || _safeCall(shape, "GetGeometryPreset"));
  var txBox = _safeCall(shape, "IsTxBox");
  if (txBox === undefined) txBox = _safeCall(shape, "GetTxBox");
  if (txBox === undefined) txBox = _safeCall(shape, "IsTextBox");
  var out = {
    class_type: cls,
    is_group: isGroup,
    is_connector: cls === "connector" || cls === "cxnsp" || !!_safeCall(shape, "IsConnector"),
    is_picture: cls === "image" || cls === "picture" || cls === "pic" || !!_safeCall(shape, "GetImage"),
    is_chart: cls === "chart",
    is_table: cls === "table",
    is_ole: cls === "ole" || cls === "oleobject",
    is_textbox: preset.toLowerCase() === "textbox" || preset.toLowerCase() === "txbox" || txBox === true,
    preset: preset,
    placeholder_type: placeholderType(shape),
    x_emu: _emu(shape, ["GetPosX", "GetX", "GetLeft"]),
    y_emu: _emu(shape, ["GetPosY", "GetY", "GetTop"]),
    width_emu: _emu(shape, ["GetWidth"]),
    height_emu: _emu(shape, ["GetHeight"]),
    text: text,
    runs: runs,
    style: extractStyle(shape, content)
  };
  if (kids && kids.length > 0) {
    out.children = [];
    for (var c = 0; c < kids.length; c++) out.children.push(dumpShape(kids[c]));
  } else if (isGroup) {
    out.unexpanded_group = true;
    if (!out.text) {
      var childTexts = [];
      if (kids && kids.length === 0) {
        /* keep empty */
      }
      out.text = childTexts.join("\n");
    }
  }
  return out;
}

var pres = Api.GetPresentation();
var slidesOut = [];
var slideCount = 0;
try { slideCount = pres.GetSlidesCount(); } catch (e) { slideCount = 0; }
var canvasW = _safeCall(pres, "GetWidth");
var canvasH = _safeCall(pres, "GetHeight");
for (var si = 0; si < slideCount; si++) {
  var slide = pres.GetSlideByIndex(si);
  var width = canvasW;
  var height = canvasH;
  if (typeof width !== "number") width = _safeCall(slide, "GetWidth");
  if (typeof height !== "number") height = _safeCall(slide, "GetHeight");
  var roots = [];
  var shapes = null;
  try { shapes = slide && slide.GetAllShapes ? slide.GetAllShapes() : null; } catch (e2) { shapes = null; }
  if (shapes) {
    for (var i = 0; i < shapes.length; i++) roots.push(dumpShape(shapes[i]));
  }
  slidesOut.push({
    slide_index: si + 1,
    width_emu: typeof width === "number" ? width : null,
    height_emu: typeof height === "number" ? height : null,
    shapes: roots
  });
}
var jsonStr = JSON.stringify({ slides: slidesOut });
"""

_WORD_COUNT_RE = re.compile(r"\S+")
_DASH_TO_DASH = frozenset({"dash", "sysdash", "dot", "dashdot"})
_TITLE_PH = frozenset({"title", "ctrtitle"})
_FOOTER_PH = frozenset({"ftr", "dt", "sldnum"})
_TEXT_SHAPE_KINDS = frozenset({"shape", "textbox"})


class PresentationStructuredError(ValueError):
    """Presentation structured read cannot return a partial slides payload."""


def emu_to_pt(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value) / EMU_PER_PT
    except (TypeError, ValueError):
        return None


def map_line_dash(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"none", "noline", "no_line"}:
        return "none"
    if text == "solid":
        return "solid"
    compact = text.replace("_", "").replace("-", "")
    if compact in _DASH_TO_DASH:
        return "dash"
    return None


def _class_type(shape: dict[str, Any]) -> str:
    return str(shape.get("class_type") or shape.get("class") or "").strip().lower()


def _is_textbox_attr(shape: dict[str, Any]) -> bool:
    if shape.get("is_textbox") is True or shape.get("tx_box") is True:
        return True
    preset = str(shape.get("preset") or shape.get("geometry_preset") or "").strip().lower()
    return preset in {"textbox", "txbox", "text_box"}


def shape_kind(shape: dict[str, Any]) -> str:
    children = shape.get("children")
    expanded = isinstance(children, list) and len(children) > 0
    unexpanded_group = bool(shape.get("unexpanded_group")) or (
        (shape.get("is_group") or _class_type(shape) in {"group", "groupshape", "grpsp"}) and not expanded
    )
    if unexpanded_group:
        return "group"
    cls = _class_type(shape)
    if shape.get("is_connector") or cls in {"connector", "cxnsp"}:
        return "connector"
    if shape.get("is_picture") or cls in {"image", "picture", "pic"}:
        return "picture"
    if shape.get("is_chart") or shape.get("is_table") or shape.get("is_ole") or cls in {
        "chart",
        "table",
        "ole",
        "oleobject",
    }:
        return "other"
    if _is_textbox_attr(shape):
        return "textbox"
    return "shape"


def flatten_shapes(raw_shapes: Any) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        children = node.get("children")
        if isinstance(children, list) and children:
            for child in children:
                walk(child)
            return
        flat.append(node)

    if isinstance(raw_shapes, list):
        for shape in raw_shapes:
            walk(shape)
    return flat


def _missing_coord(shape: dict[str, Any]) -> bool:
    for key in ("x", "y", "width", "height"):
        if shape.get(key) is None:
            return True
    return False


def _placeholder(shape: dict[str, Any]) -> str:
    return str(shape.get("placeholder_type") or "").strip().lower()


def _element_type_fields(shape: dict[str, Any]) -> dict[str, Any]:
    ph = _placeholder(shape)
    if ph in _TITLE_PH:
        return {"type": "heading", "level": 1}
    if ph == "hdr":
        return {"type": "header"}
    if ph in _FOOTER_PH:
        return {"type": "footer"}
    return {"type": "paragraph"}


def _normalize_style(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    style: dict[str, Any] = {}
    if "fill" in raw and raw["fill"] is not None:
        fill = raw["fill"]
        if str(fill).lower() in {"none", "nofill"}:
            style["fill"] = "none"
        else:
            color = _to_hex_color(fill)
            if color:
                style["fill"] = color
    if "line_color" in raw and raw["line_color"] is not None:
        line_color = raw["line_color"]
        if str(line_color).lower() in {"none", "noline"}:
            style["line_color"] = "none"
        else:
            color = _to_hex_color(line_color)
            if color:
                style["line_color"] = color
    if raw.get("line_width_emu") is not None:
        converted = emu_to_pt(raw.get("line_width_emu"))
        if converted is not None:
            style["line_width_pt"] = converted
    elif raw.get("line_width_pt") is not None:
        try:
            style["line_width_pt"] = float(raw["line_width_pt"]) / EMU_PER_PT
        except (TypeError, ValueError):
            pass
    dash_raw = raw.get("line_dash_raw", raw.get("line_dash"))
    mapped = map_line_dash(dash_raw)
    if mapped is not None:
        style["line_dash"] = mapped
    if raw.get("font_name"):
        style["font_name"] = str(raw["font_name"])
    if raw.get("font_size_pt") is not None:
        try:
            style["font_size_pt"] = float(raw["font_size_pt"])
        except (TypeError, ValueError):
            pass
    if raw.get("font_color") is not None:
        color = _to_hex_color(raw["font_color"])
        if color and color != "none":
            style["font_color"] = color
    for key in ("bold", "italic"):
        if key in raw and raw[key] is not None:
            style[key] = bool(raw[key])
    align = _align({"align": raw.get("align")})
    if align:
        style["align"] = align
    return style


def _shape_text(raw: dict[str, Any], kind: str) -> str:
    text = raw.get("text")
    if text is not None:
        return sanitize_text(text, trim_edges=True)
    if kind == "group":
        children = raw.get("child_texts") or []
        if isinstance(children, list):
            parts = [sanitize_text(t, trim_edges=True) for t in children if has_visible_text(t)]
            return "\n".join(parts)
    return ""


def _normalize_flat_shape(raw: dict[str, Any], slide_index: int, n: int) -> dict[str, Any]:
    kind = shape_kind(raw)
    x = emu_to_pt(raw.get("x_emu", raw.get("x")))
    y = emu_to_pt(raw.get("y_emu", raw.get("y")))
    width = emu_to_pt(raw.get("width_emu", raw.get("width")))
    height = emu_to_pt(raw.get("height_emu", raw.get("height")))
    shape: dict[str, Any] = {
        "shape_id": f"s{slide_index}-{n}",
        "kind": kind,
        "text": _shape_text(raw, kind),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }
    if _missing_coord(shape):
        raise PresentationStructuredError("presentation shape is missing x, y, width, or height")
    style = _normalize_style(raw.get("style") or {})
    if style:
        shape["style"] = style
    ph = raw.get("placeholder_type")
    if ph:
        shape["placeholder_type"] = ph
    runs = _normalize_runs(raw.get("runs"))
    if runs:
        shape["runs"] = runs
        joined = "".join(str(run.get("text") or "") for run in runs)
        if joined:
            shape["text"] = joined
    return shape


def normalize_presentation_structured(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Flatten presentation sidecar JSON into elements + slides.

    Raises PresentationStructuredError when any shape or canvas is incomplete.
    """
    data = raw if isinstance(raw, dict) else {}
    slides_raw = data.get("slides")
    if not isinstance(slides_raw, list):
        raise PresentationStructuredError("presentation sidecar has no slides")

    slides: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []

    for raw_slide in slides_raw:
        if not isinstance(raw_slide, dict):
            continue
        try:
            slide_index = int(raw_slide.get("slide_index") or (len(slides) + 1))
        except (TypeError, ValueError):
            slide_index = len(slides) + 1
        width_pt = emu_to_pt(raw_slide.get("width_emu", raw_slide.get("width_pt")))
        height_pt = emu_to_pt(raw_slide.get("height_emu", raw_slide.get("height_pt")))
        if width_pt is None or height_pt is None:
            raise PresentationStructuredError("presentation canvas is missing width_pt or height_pt")

        flat = flatten_shapes(raw_slide.get("shapes") or [])
        shapes: list[dict[str, Any]] = []
        for offset, raw_shape in enumerate(flat, start=1):
            shape = _normalize_flat_shape(raw_shape, slide_index, offset)
            visible = has_visible_text(shape.get("text"))
            if visible or shape["kind"] not in _TEXT_SHAPE_KINDS:
                shapes.append(shape)
            if visible:
                element = {
                    "slide": slide_index,
                    "slide_index": slide_index,
                    "text": shape["text"],
                    **_element_type_fields(raw_shape),
                }
                runs = shape.get("runs")
                if runs:
                    element["runs"] = runs
                elements.append(element)

        slides.append({
            "slide_index": slide_index,
            "width_pt": width_pt,
            "height_pt": height_pt,
            "shapes": shapes,
        })

    return {"elements": elements, "slides": slides}


def presentation_title_from_elements(elements: list[dict[str, Any]]) -> str:
    for element in elements:
        if element.get("type") == "heading" and element.get("text"):
            return str(element["text"])
    for element in elements:
        if element.get("text"):
            return str(element["text"])[:200]
    return ""


def word_count_from_presentation(elements: list[dict[str, Any]]) -> int:
    return sum(len(_WORD_COUNT_RE.findall(str(el.get("text") or ""))) for el in elements)
