"""Builder script generation for office_create_presentation."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PresentationCreateOptions,
    SlideSpec,
)


def _emit_slide_content(slide_var: str, spec: SlideSpec) -> list[str]:
    lines: list[str] = []
    if spec.title:
        lines.append(f'var titleShape = {slide_var}.GetPlaceholder("title");')
        lines.append("if (titleShape) { titleShape.SetText(\"" + escape_js(spec.title) + "\"); }")
    if spec.subtitle:
        lines.append(f'var subShape = {slide_var}.GetPlaceholder("subtitle");')
        lines.append("if (subShape) { subShape.SetText(\"" + escape_js(spec.subtitle) + "\"); }")
    if spec.bullets:
        lines.append(f'var bodyShape = {slide_var}.GetPlaceholder("body");')
        lines.append("if (bodyShape) {")
        for item in spec.bullets:
            lines.append(f'  bodyShape.AddText("{escape_js(str(item))}\\n");')
        lines.append("}")
    if spec.notes:
        lines.append(f"{slide_var}.GetNotesPage().GetAllShapes()[0].SetText(\"" + escape_js(spec.notes) + "\");")
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
    lines = [f'builder.CreateFile("{output_ext}");', "var pres = Api.GetPresentation();"]
    if options.size:
        w = options.size.get("width", 9144000)
        h = options.size.get("height", 5143500)
        lines.append(f"pres.SetSizes({w}, {h});")
    for spec in slides:
        layout = escape_js(spec.layout)
        lines.append(f'var slide = pres.AddSlide("{layout}");')
        lines.extend(_emit_slide_content("slide", spec))
    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
