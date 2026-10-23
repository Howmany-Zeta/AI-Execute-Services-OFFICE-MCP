"""Builder script generation for office_create_presentation."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.presentation.builder.notes import emit_notes_text
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PresentationCreateOptions,
    SlideSpec,
)


def _emit_slide_content(slide_var: str, spec: SlideSpec) -> list[str]:
    lines: list[str] = []
    if spec.title:
        lines.append(f'var titleShape = null;')
        lines.append(f'try {{ titleShape = {slide_var}.GetPlaceholder ? {slide_var}.GetPlaceholder("title") : null; }} catch (ePh) {{ titleShape = null; }}')
        lines.append("if (titleShape && titleShape.SetText) { titleShape.SetText(\"" + escape_js(spec.title) + "\"); }")
    if spec.subtitle:
        lines.append(f'var subShape = null;')
        lines.append(f'try {{ subShape = {slide_var}.GetPlaceholder ? {slide_var}.GetPlaceholder("subtitle") : null; }} catch (ePh2) {{ subShape = null; }}')
        lines.append("if (subShape && subShape.SetText) { subShape.SetText(\"" + escape_js(spec.subtitle) + "\"); }")
    if spec.bullets:
        lines.append(f'var bodyShape = null;')
        lines.append(f'try {{ bodyShape = {slide_var}.GetPlaceholder ? {slide_var}.GetPlaceholder("body") : null; }} catch (ePh3) {{ bodyShape = null; }}')
        lines.append("if (bodyShape) {")
        lines.append("  try { if (bodyShape.Clear) bodyShape.Clear(); } catch (eCl) {}")
        for item in spec.bullets:
            lines.append(f'  try {{ if (bodyShape.AddText) bodyShape.AddText("{escape_js(str(item))}\\n"); }} catch (eAt) {{}}')
        lines.append("}")
    if spec.notes:
        lines.extend(emit_notes_text(slide_var, spec.notes))
    for shape in spec.shapes or []:
        if shape.type == "image" and shape.url:
            lines.append(f'var img = Api.CreateImage("{escape_js(shape.url)}", {shape.size.width if shape.size else 100}, {shape.size.height if shape.size else 100});')
            lines.append(f"{slide_var}.AddObject(img);")
        elif shape.text:
            lines.append(f'var tb = {slide_var}.AddTextbox();')
            lines.append(f'tb.SetText("{escape_js(shape.text)}");')
    return lines


def build_create_script(
    slides: list[SlideSpec],
    *,
    output_ext: str,
    options: PresentationCreateOptions,
) -> str:
    lines = [
        f'builder.CreateFile("{output_ext}");',
        "var pres = Api.GetPresentation();",
        "function _officeFindLayout(pres, name) {",
        "  var masters = [];",
        "  try { masters = pres.GetAllSlideMasters ? pres.GetAllSlideMasters() : []; } catch (e) { masters = []; }",
        "  if ((!masters || !masters.length) && pres.GetMaster) {",
        "    try { var one = pres.GetMaster(); if (one) masters = [one]; } catch (e2) {}",
        "  }",
        "  for (var mi = 0; mi < masters.length; mi++) {",
        "    var layouts = [];",
        "    try { layouts = masters[mi].GetAllLayouts ? masters[mi].GetAllLayouts() : []; } catch (e3) { layouts = []; }",
        "    for (var li = 0; li < layouts.length; li++) {",
        "      var n = '';",
        "      try { n = String(layouts[li].GetName ? layouts[li].GetName() : ''); } catch (e4) { n = ''; }",
        "      if (n === name) return layouts[li];",
        "    }",
        "  }",
        "  return null;",
        "}",
    ]
    if options.size:
        w = options.size.get("width", 9144000)
        h = options.size.get("height", 5143500)
        lines.append(f"pres.SetSizes({w}, {h});")
    for i, spec in enumerate(slides):
        layout = escape_js(spec.layout)
        if i == 0:
            lines.append("var slide = pres.GetSlideByIndex(0);")
            lines.append("if (!slide) slide = pres.AddSlide();")
        else:
            lines.append("var slide = pres.GetSlideByIndex(0).Duplicate();")
            lines.append("if (slide && slide.RemoveAllObjects) slide.RemoveAllObjects();")
            lines.append("if (slide && slide.MoveTo) slide.MoveTo(pres.GetSlidesCount() - 1);")
        lines.append(f'var lay = _officeFindLayout(pres, "{layout}");')
        lines.append("if (lay && slide.ApplyLayout) slide.ApplyLayout(lay);")
        lines.extend(_emit_slide_content("slide", spec))
    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
