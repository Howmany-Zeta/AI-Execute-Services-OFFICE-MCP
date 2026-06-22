"""Builder script generation for office_edit_presentation (edit body only)."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.presentation.schemas.edit_ops import EditOperation


def _emit_resolve_shape(slide_var: str, op: EditOperation) -> tuple[str, list[str]]:
    """Return (shape_var, setup_lines) for shape resolution."""
    lines: list[str] = []
    if op.shape_index is not None:
        return f"{slide_var}.GetAllShapes()[{op.shape_index}]", lines
    if op.role:
        lines.append(f'var shape = {slide_var}.GetPlaceholder("{op.role}");')
        return "shape", lines
    if op.match_text:
        snippet = escape_js(op.match_text)
        lines.append(f"var shapes = {slide_var}.GetAllShapes();")
        lines.append("var shape = null;")
        lines.append("for (var si = 0; si < shapes.length; si++) {")
        lines.append(f'  if (shapes[si].GetText().indexOf("{snippet}") >= 0) {{ shape = shapes[si]; break; }}')
        lines.append("}")
        return "shape", lines
    return f"{slide_var}.GetAllShapes()[0]", lines


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    name = op.op

    if name == "set_text":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        shape_var, setup = _emit_resolve_shape(slide, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{ {shape_var}.SetText(\"{escape_js(op.text or '')}\"); }}")
    elif name == "set_title":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        lines.append(f'var titleShape = {slide}.GetPlaceholder("title");')
        lines.append(f'if (titleShape) {{ titleShape.SetText("{escape_js(op.text or "")}"); }}')
    elif name == "set_bullets":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        lines.append(f'var bodyShape = {slide}.GetPlaceholder("body");')
        lines.append("if (bodyShape) { bodyShape.Clear();")
        for item in op.items or []:
            lines.append(f'  bodyShape.AddText("{escape_js(str(item))}\\n");')
        lines.append("}")
    elif name == "add_slide":
        after = op.after_index if op.after_index is not None else -1
        layout = escape_js(op.layout or "")
        lines.append(f'var newSlide = pres.AddSlide("{layout}", {after});')
        if op.title:
            lines.append(f'var tShape = newSlide.GetPlaceholder("title");')
            lines.append(f'if (tShape) {{ tShape.SetText("{escape_js(op.title)}"); }}')
    elif name == "delete_slide":
        lines.append(f"pres.RemoveSlide({op.slide_index});")
    elif name == "duplicate_slide":
        after = op.after_index if op.after_index is not None else op.slide_index
        lines.append(f"pres.DuplicateSlide({op.slide_index}, {after});")
    elif name == "move_slide":
        lines.append(f"pres.MoveSlide({op.from_index}, {op.to_index});")
    elif name == "set_notes":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        lines.append(f'{slide}.GetNotesPage().GetAllShapes()[0].SetText("{escape_js(op.text or "")}");')
    elif name == "replace_image":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        shape_var, setup = _emit_resolve_shape(slide, op)
        lines.extend(setup)
        lines.append(f'if ({shape_var}) {{ {shape_var}.SetImage("{escape_js(op.url or "")}"); }}')
    elif name == "remove_shape":
        slide = f"pres.GetSlideByIndex({op.slide_index})"
        shape_var, setup = _emit_resolve_shape(slide, op)
        lines.extend(setup)
        lines.append(f"if ({shape_var}) {{ {shape_var}.Delete(); }}")

    return lines


def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    lines = ["var pres = Api.GetPresentation();"]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
