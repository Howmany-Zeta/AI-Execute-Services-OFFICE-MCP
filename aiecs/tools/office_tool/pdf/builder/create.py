"""Builder script generation for office_create_pdf (ADR-017)."""

from __future__ import annotations

import json

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.pdf.schemas.page_spec import BlockSpec, PageSpec, PdfCreateOptions


def _emit_block(block: BlockSpec) -> list[str]:
    lines: list[str] = []
    if block.type == "table" and block.rows:
        cols = max((len(r) for r in block.rows), default=1)
        lines.append(f"var oTable = Api.CreateTable({cols}, {len(block.rows)});")
        for ri, row in enumerate(block.rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.append("page.Push(oTable);")
        return lines

    lines.append("var oPara = Api.CreateParagraph();")
    lines.append("var oRun = Api.CreateRun();")
    lines.append(f'oRun.AddText("{escape_js(block.text or "")}");')
    if block.bold:
        lines.append("oRun.SetBold(true);")
    if block.align == "center":
        lines.append("oPara.SetJc('center');")
    elif block.align == "right":
        lines.append("oPara.SetJc('right');")
    lines.append("oPara.AddElement(oRun);")
    lines.append("page.Push(oPara);")
    return lines


def build_create_script(
    pages: list[PageSpec],
    *,
    output_ext: str,
    options: PdfCreateOptions,
) -> str:
    create_ext = "docx" if options.create_mode == "via_docx" else "pdf"
    save_ext = output_ext or "pdf"
    lines = [f'builder.CreateFile("{create_ext}");', "var doc = Api.GetDocument();"]

    for pi, page_spec in enumerate(pages):
        if pi > 0:
            lines.append("doc.AddPage();")
        lines.append("var page = doc.GetElement(doc.GetElementsCount() - 1);")
        for block in page_spec.blocks:
            lines.extend(_emit_block(block))

    lines.append(f'builder.SaveFile("{save_ext}", "output.{save_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
