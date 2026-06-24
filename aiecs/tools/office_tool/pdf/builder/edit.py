"""Builder script generation for office_edit_pdf (edit body only)."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.pdf.schemas.edit_ops import EditOperation
from aiecs.tools.office_tool.pdf.schemas.page_spec import BlockSpec


def _emit_align(paragraph_var: str, align: str | None) -> list[str]:
    if align == "center":
        return [f"{paragraph_var}.SetJc('center');"]
    if align == "right":
        return [f"{paragraph_var}.SetJc('right');"]
    return []


def _emit_block_on_page(block: BlockSpec) -> list[str]:
    if block.type == "table" and block.rows:
        cols = max((len(r) for r in block.rows), default=1)
        lines = [f"var oTable = Api.CreateTable({cols}, {len(block.rows)});"]
        for ri, row in enumerate(block.rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.append("page.Push(oTable);")
        return lines

    lines = ["var oPara = Api.CreateParagraph();", "var oRun = Api.CreateRun();"]
    lines.extend(_emit_align("oPara", block.align))
    lines.append(f'oRun.AddText("{escape_js(block.text or "")}");')
    lines.append("oPara.AddElement(oRun);")
    lines.append("page.Push(oPara);")
    return lines


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    if op.op == "add_paragraph":
        lines.append(f"var page = doc.GetElement({op.page_index});")
        lines.append("var oPara = Api.CreateParagraph();")
        lines.extend(_emit_align("oPara", op.align))
        lines.append(f'oPara.AddText("{escape_js(op.text or "")}");')
        lines.append("page.Push(oPara);")
    elif op.op == "set_page_text":
        lines.append(f"var page = doc.GetElement({op.page_index});")
        lines.append("while (page.GetElementsCount() > 0) { page.RemoveElement(0); }")
        for block in op.blocks or []:
            lines.extend(_emit_block_on_page(block))
    elif op.op == "add_page":
        after = op.after_index if op.after_index is not None else -1
        lines.append(f"doc.AddPage({after});")
        if op.blocks:
            lines.append("var page = doc.GetElement(doc.GetElementsCount() - 1);")
            for block in op.blocks:
                lines.extend(_emit_block_on_page(block))
    elif op.op == "delete_page":
        lines.append(f"doc.RemoveElement({op.page_index});")
    elif op.op == "rotate_page":
        lines.append(f"var page = doc.GetElement({op.page_index});")
        lines.append(f"page.Rotate({op.degrees});")
    elif op.op == "add_annotation":
        rect = op.rect or {}
        lines.append(f"var page = doc.GetElement({op.page_index});")
        lines.append(
            f'page.AddAnnotation("{escape_js(op.kind or "freetext")}", '
            f'"{escape_js(op.text or "")}", {rect.get("x", 0)}, {rect.get("y", 0)}, '
            f'{rect.get("width", 100)}, {rect.get("height", 20)});'
        )
    return lines


def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    lines = ["var doc = Api.GetDocument();"]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
