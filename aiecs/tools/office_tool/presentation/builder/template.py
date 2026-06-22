"""Builder script generation for office_apply_template_presentation."""

from __future__ import annotations

from typing import Any

from aiecs.tools.office_tool.core.builder_js import escape_js


def build_template_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    Edit body: OpenFile injected by run_builder_on_source.
    Replace {{key}} globally and slide_{N}_ prefixed keys per slide.
    """
    lines = ["var pres = Api.GetPresentation();", "var slideCount = pres.GetSlidesCount();", ""]

    global_keys = {k: v for k, v in data.items() if not str(k).startswith("slide_")}
    slide_keys: dict[int, dict[str, Any]] = {}
    for key, value in data.items():
        key_str = str(key)
        if key_str.startswith("slide_"):
            parts = key_str.split("_", 2)
            if len(parts) >= 3 and parts[1].isdigit():
                slide_num = int(parts[1])
                field = parts[2]
                slide_keys.setdefault(slide_num, {})[field] = value

    lines.append("function replaceInShape(shape, replacements) {")
    lines.append("  if (!shape) return;")
    lines.append("  var txt = shape.GetText();")
    lines.append("  for (var k in replacements) {")
    lines.append('    var search = "{{" + k + "}}";')
    lines.append("    while (txt.indexOf(search) >= 0) { txt = txt.split(search).join(replacements[k]); }")
    lines.append("  }")
    lines.append("  shape.SetText(txt);")
    lines.append("}")
    lines.append("")

    repl_obj = ", ".join(f'"{escape_js(str(k))}": "{escape_js(str(v))}"' for k, v in global_keys.items())
    if repl_obj:
        lines.append(f"var globalRepl = {{{repl_obj}}};")
        lines.append("for (var i = 0; i < slideCount; i++) {")
        lines.append("  var slide = pres.GetSlideByIndex(i);")
        lines.append("  var shapes = slide.GetAllShapes();")
        lines.append("  for (var j = 0; j < shapes.length; j++) { replaceInShape(shapes[j], globalRepl); }")
        lines.append("}")
        lines.append("")

    for slide_num, fields in sorted(slide_keys.items()):
        slide_idx = slide_num - 1
        repl_obj = ", ".join(f'"{escape_js(str(k))}": "{escape_js(str(v))}"' for k, v in fields.items())
        lines.append(f"{{ var slide = pres.GetSlideByIndex({slide_idx});")
        lines.append(f"  var repl = {{{repl_obj}}};")
        lines.append("  var shapes = slide.GetAllShapes();")
        lines.append("  for (var j = 0; j < shapes.length; j++) { replaceInShape(shapes[j], repl); }")
        lines.append("}")

    return "\n".join(lines)
