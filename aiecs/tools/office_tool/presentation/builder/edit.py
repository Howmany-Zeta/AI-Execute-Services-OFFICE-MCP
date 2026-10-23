"""Builder script generation for office_edit_presentation (edit body only)."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.presentation.builder.notes import emit_notes_text
from aiecs.tools.office_tool.presentation.schemas.edit_ops import EditOperation

_PPT_EDIT_HELPERS = """
function _officeVisibleRuns(el) {
  var runs = [];
  if (!el) return runs;
  function walk(node) {
    if (!node) return;
    var cls = "";
    try { cls = String(node.GetClassType ? node.GetClassType() : "").toLowerCase(); } catch (e) { cls = ""; }
    if (cls === "run" || cls === "textrun") { runs.push(node); return; }
    var n = 0;
    try { n = node.GetElementsCount ? node.GetElementsCount() : 0; } catch (e2) { n = 0; }
    if (!n) {
      if (node.GetText || node.SetBold) runs.push(node);
      return;
    }
    for (var i = 0; i < n; i++) {
      var child = null;
      try { child = node.GetElement(i); } catch (e3) { child = null; }
      walk(child);
    }
  }
  walk(el);
  return runs;
}
function _officeShapeText(shape) {
  if (!shape) return "";
  try { if (shape.GetText) return String(shape.GetText() || ""); } catch (e) {}
  var content = null;
  try { content = shape.GetDocContent ? shape.GetDocContent() : null; } catch (e2) { content = null; }
  if (!content) try { content = shape.GetContent ? shape.GetContent() : null; } catch (e3) { content = null; }
  try { if (content && content.GetText) return String(content.GetText() || ""); } catch (e4) {}
  return "";
}
function _officeSetShapeText(shape, text) {
  if (!shape) return;
  try {
    var range = shape.GetTextRange ? shape.GetTextRange() : null;
    if (range && range.SetText) { range.SetText(text); return; }
  } catch (e0) {}
  var content = null;
  try { content = shape.GetDocContent ? shape.GetDocContent() : null; } catch (e) { content = null; }
  if (!content) try { content = shape.GetContent ? shape.GetContent() : null; } catch (e2) { content = null; }
  if (!content) return;
  try { if (content.RemoveAllElements) content.RemoveAllElements(); } catch (e3) {}
  var para = null;
  try { para = Api.CreateParagraph(); } catch (e4) { para = null; }
  if (para && para.AddText) {
    para.AddText(text);
    if (content.Push) { content.Push(para); return; }
    if (content.AddElement) { content.AddElement(para); return; }
  }
  var p0 = null;
  try { p0 = content.GetElement ? content.GetElement(0) : null; } catch (e5) { p0 = null; }
  if (p0) {
    try { if (p0.RemoveAllElements) p0.RemoveAllElements(); } catch (e6) {}
    if (p0.SetText) { p0.SetText(text); return; }
    if (p0.AddText) p0.AddText(text);
  }
}
function _officeFindByRole(slide, role) {
  if (!slide) return null;
  var aliases = { title: ["title", "ctrTitle"], body: ["body", "content"], subtitle: ["subtitle", "subTitle"] };
  var names = aliases[role] || [role];
  if (slide.GetDrawingsByPlaceholderType) {
    for (var ni = 0; ni < names.length; ni++) {
      var found = null;
      try { found = slide.GetDrawingsByPlaceholderType(names[ni]); } catch (e) { found = null; }
      if (found && found.length) return found[0];
    }
  }
  var shapes = [];
  try { shapes = slide.GetAllShapes ? slide.GetAllShapes() : []; } catch (e2) { shapes = []; }
  for (var si = 0; si < shapes.length; si++) {
    var ph = null;
    try { ph = shapes[si].GetPlaceholder ? shapes[si].GetPlaceholder() : null; } catch (e3) { ph = null; }
    if (!ph) continue;
    var t = "";
    try { t = String(ph.GetType ? ph.GetType() : (ph.GetPlaceholderType ? ph.GetPlaceholderType() : "")).toLowerCase(); } catch (e4) { t = ""; }
    for (var aj = 0; aj < names.length; aj++) {
      if (t === String(names[aj]).toLowerCase()) return shapes[si];
    }
  }
  var scored = [];
  for (var fi = 0; fi < shapes.length; fi++) {
    var ft = _officeShapeText(shapes[fi]);
    if (!ft) continue;
    var flen = String(ft).replace(/\s+/g, "").length;
    if (flen) scored.push({ shape: shapes[fi], n: flen });
  }
  scored.sort(function (a, b) { return b.n - a.n; });
  if (role === "title" && scored.length) return scored[0].shape;
  if (role === "subtitle" && scored.length > 1) return scored[1].shape;
  if (role === "body") {
    if (scored.length > 1) return scored[1].shape;
    if (scored.length) return scored[0].shape;
  }
  return null;
}
function _officeFindLayout(pres, name) {
  var masters = [];
  try { masters = pres.GetAllSlideMasters ? pres.GetAllSlideMasters() : []; } catch (e) { masters = []; }
  if ((!masters || !masters.length) && pres.GetMaster) {
    try { var one = pres.GetMaster(); if (one) masters = [one]; } catch (e2) {}
  }
  for (var mi = 0; mi < masters.length; mi++) {
    var layouts = [];
    try { layouts = masters[mi].GetAllLayouts ? masters[mi].GetAllLayouts() : []; } catch (e3) { layouts = []; }
    for (var li = 0; li < layouts.length; li++) {
      var n = "";
      try { n = String(layouts[li].GetName ? layouts[li].GetName() : ""); } catch (e4) { n = ""; }
      if (n === name) return layouts[li];
    }
  }
  try {
    var nSlides = pres.GetSlidesCount ? pres.GetSlidesCount() : 0;
    for (var si = 0; si < nSlides; si++) {
      var sl = pres.GetSlideByIndex ? pres.GetSlideByIndex(si) : null;
      var lay = sl && sl.GetLayout ? sl.GetLayout() : null;
      var ln = "";
      try { ln = String(lay && lay.GetName ? lay.GetName() : ""); } catch (e5) { ln = ""; }
      if (ln === name) return lay;
    }
  } catch (e6) {}
  return null;
}
"""


def _emit_resolve_host(op: EditOperation) -> tuple[str, list[str]]:
    if op.layout_name:
        name = escape_js(op.layout_name)
        lines = [
            "var layoutHost = null;",
            "var _master = pres.GetMaster ? pres.GetMaster() : null;",
            "var _layouts = _master && _master.GetAllLayouts ? _master.GetAllLayouts() : [];",
            "for (var li = 0; li < _layouts.length; li++) {",
            f'  if (String(_layouts[li].GetName()) === "{name}") {{ layoutHost = _layouts[li]; break; }}',
            "}",
        ]
        return "layoutHost", lines
    return f"pres.GetSlideByIndex({op.slide_index})", []


def _emit_resolve_shape(slide_var: str, op: EditOperation) -> tuple[str, list[str]]:
    """Return (shape_var, setup_lines) for shape resolution."""
    lines: list[str] = []
    if op.shape_index is not None:
        return f"{slide_var}.GetAllShapes()[{op.shape_index}]", lines
    if op.role:
        lines.append(f'var shape = _officeFindByRole({slide_var}, "{op.role}");')
        return "shape", lines
    if op.match_text:
        snippet = escape_js(op.match_text)
        lines.append(f"var shapes = {slide_var}.GetAllShapes();")
        lines.append("var shape = null;")
        lines.append("for (var si = 0; si < shapes.length; si++) {")
        lines.append(f'  if (_officeShapeText(shapes[si]).indexOf("{snippet}") >= 0) {{ shape = shapes[si]; break; }}')
        lines.append("}")
        return "shape", lines
    raise ValueError(f"{op.op} requires shape_index, match_text, or role")


def _pt_to_emu(value: float | None, default: float) -> int:
    return int((default if value is None else value) * 12700)


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    name = op.op

    if name == "set_text":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        lines.append(f'_officeSetShapeText({shape_var}, "{escape_js(op.text or "")}");')
    elif name == "set_title":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        lines.append(f'var titleShape = _officeFindByRole({slide}, "title");')
        lines.append(f'_officeSetShapeText(titleShape, "{escape_js(op.text or "")}");')
    elif name == "set_bullets":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        items_text = "\\n".join(str(item) for item in (op.items or []))
        lines.append(f'var bodyShape = _officeFindByRole({slide}, "body");')
        lines.append(f'_officeSetShapeText(bodyShape, "{escape_js(items_text)}");')
    elif name == "add_slide":
        after = op.after_index if op.after_index is not None else -1
        layout = escape_js(op.layout or "")
        lines.append(f"var addAfter = {after};")
        lines.append("var addFrom = addAfter < 0 ? pres.GetSlidesCount() - 1 : addAfter;")
        lines.append("if (addFrom < 0) addFrom = 0;")
        lines.append("var newSlide = pres.GetSlideByIndex(addFrom).Duplicate();")
        lines.append("if (newSlide) {")
        lines.append("  if (newSlide.RemoveAllObjects) newSlide.RemoveAllObjects();")
        lines.append(f'  var addLayout = _officeFindLayout(pres, "{layout}");')
        lines.append("  if (addLayout && newSlide.ApplyLayout) newSlide.ApplyLayout(addLayout);")
        lines.append("  var addDest = addAfter < 0 ? pres.GetSlidesCount() - 1 : addAfter + 1;")
        lines.append("  if (newSlide.MoveTo) newSlide.MoveTo(addDest);")
        if op.title:
            lines.append('  var tShape = _officeFindByRole(newSlide, "title");')
            lines.append(f'  _officeSetShapeText(tShape, "{escape_js(op.title)}");')
        if op.subtitle:
            lines.append('  var subShape = _officeFindByRole(newSlide, "subtitle");')
            lines.append(f'  _officeSetShapeText(subShape, "{escape_js(op.subtitle)}");')
        if op.items:
            items_text = "\\n".join(str(item) for item in op.items)
            lines.append('  var bodyShape = _officeFindByRole(newSlide, "body");')
            lines.append(f'  _officeSetShapeText(bodyShape, "{escape_js(items_text)}");')
        lines.append("}")
    elif name == "delete_slide":
        lines.append(f"var delSlide = pres.GetSlideByIndex({op.slide_index});")
        lines.append("if (delSlide && delSlide.Delete) { delSlide.Delete(); }")
        lines.append(f"else if (pres.RemoveSlides) {{ pres.RemoveSlides({op.slide_index}, {op.slide_index}); }}")
    elif name == "duplicate_slide":
        after = op.after_index if op.after_index is not None else op.slide_index
        lines.append(f"var dupSlide = pres.GetSlideByIndex({op.slide_index}).Duplicate();")
        lines.append(f"if (dupSlide && dupSlide.MoveTo) {{ dupSlide.MoveTo({after} + 1); }}")
    elif name == "move_slide":
        lines.append(f"var mvSlide = pres.GetSlideByIndex({op.from_index});")
        lines.append(f"if (mvSlide && mvSlide.MoveTo) {{ mvSlide.MoveTo({op.to_index}); }}")
    elif name == "set_notes":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        lines.extend(emit_notes_text(slide, op.text or ""))
    elif name == "replace_image":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        url = escape_js(op.url or "")
        lines.append(f"if ({shape_var}) {{")
        lines.append(f"  var imgW = {shape_var}.GetWidth ? {shape_var}.GetWidth() : 1000000;")
        lines.append(f"  var imgH = {shape_var}.GetHeight ? {shape_var}.GetHeight() : 1000000;")
        lines.append(f"  var imgX = {shape_var}.GetPosX ? {shape_var}.GetPosX() : 0;")
        lines.append(f"  var imgY = {shape_var}.GetPosY ? {shape_var}.GetPosY() : 0;")
        lines.append(f'  var imgNew = Api.CreateImage("{url}", imgW, imgH);')
        lines.append("  if (imgNew.SetPosition) imgNew.SetPosition(imgX, imgY);")
        lines.append(f"  if ({host}.AddObject) {host}.AddObject(imgNew);")
        lines.append(f"  if ({shape_var}.Delete) {shape_var}.Delete();")
        lines.append("}")
    elif name == "remove_shape":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{ {shape_var}.Delete(); }}")
    elif name == "set_run_format":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{")
        lines.append(f"  var formatContent = {shape_var}.GetDocContent ? {shape_var}.GetDocContent() : {shape_var};")
        lines.append("  var formatRuns = _officeVisibleRuns(formatContent);")
        lines.append(f"  var formatRun = formatRuns[{0 if op.run_index is None else op.run_index}];")
        lines.append("  if (formatRun) {")
        if op.bold is not None:
            lines.append(f"    formatRun.SetBold({str(op.bold).lower()});")
        if op.italic is not None:
            lines.append(f"    formatRun.SetItalic({str(op.italic).lower()});")
        if op.underline is not None:
            lines.append(f"    formatRun.SetUnderline({str(op.underline).lower()});")
        if op.font_name:
            lines.append(f'    formatRun.SetFontFamily("{escape_js(op.font_name)}");')
        if op.font_size_pt is not None:
            lines.append(f"    formatRun.SetFontSize({float(op.font_size_pt)});")
        lines.extend(["  }", "}"])
    elif name == "set_shape_geometry":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{")
        if op.x_pt is not None or op.y_pt is not None:
            x = _pt_to_emu(op.x_pt, 0)
            y = _pt_to_emu(op.y_pt, 0)
            lines.append(f"  if ({shape_var}.SetPosition) {{ {shape_var}.SetPosition({x}, {y}); }}")
        if op.width_pt is not None or op.height_pt is not None:
            w = _pt_to_emu(op.width_pt, 200)
            h = _pt_to_emu(op.height_pt, 80)
            lines.append(f"  if ({shape_var}.SetSize) {{ {shape_var}.SetSize({w}, {h}); }}")
        lines.append("}")
    elif name == "set_paragraph_format":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        shape_var, setup = _emit_resolve_shape(host, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{")
        lines.append(f"  var paraFmt = {shape_var}.GetDocContent ? {shape_var}.GetDocContent().GetElement(0) : {shape_var};")
        lines.append(f'  if (paraFmt && paraFmt.SetJc) {{ paraFmt.SetJc("{escape_js(op.align or "left")}"); }}')
        lines.append("}")
    elif name == "insert_textbox":
        host, host_setup = _emit_resolve_host(op)
        lines.extend(host_setup)
        w = _pt_to_emu(op.width_pt, 200)
        h = _pt_to_emu(op.height_pt, 80)
        x = _pt_to_emu(op.x_pt, 0)
        y = _pt_to_emu(op.y_pt, 0)
        lines.append(f"if ({host}) {{")
        lines.append(f'  var oBox = Api.CreateShape("rect", {w}, {h});')
        lines.append(f"  if (oBox.SetPosition) {{ oBox.SetPosition({x}, {y}); }}")
        if op.text:
            lines.append(f'  _officeSetShapeText(oBox, "{escape_js(op.text)}");')
        lines.append(f"  if ({host}.AddObject) {{ {host}.AddObject(oBox); }}")
        lines.append(f"  else if ({host}.AddShape) {{ {host}.AddShape(oBox); }}")
        lines.append("}")

    return lines


def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    lines = ["var pres = Api.GetPresentation();", _PPT_EDIT_HELPERS.strip()]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
