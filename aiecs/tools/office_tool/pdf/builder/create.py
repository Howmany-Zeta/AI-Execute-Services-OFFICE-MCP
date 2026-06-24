"""Builder script generation for office_create_pdf (ADR-017)."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.pdf.schemas.page_spec import BlockSpec, PageSpec, PdfCreateOptions

# Portrait page dimensions: twips for Word section API; points for native PDF AddPage.
_PAGE_SIZE_TWIPS: dict[str, tuple[int, int]] = {
    "A4": (11906, 16838),
    "Letter": (12240, 15840),
}
_PAGE_SIZE_POINTS: dict[str, tuple[int, int]] = {
    "A4": (595, 842),
    "Letter": (612, 792),
}


def _emit_page_size_section(doc_var: str, page_size: str) -> list[str]:
    width, height = _PAGE_SIZE_TWIPS[page_size]
    return [
        f"var section = {doc_var}.GetFinalSection();",
        f"section.SetPageSize({width}, {height}, true);",
    ]


def _emit_native_page_open(page_index: int, page_size: str | None) -> list[str]:
    lines: list[str] = []
    if page_index == 0:
        if page_size:
            width, height = _PAGE_SIZE_POINTS[page_size]
            lines.append("doc.RemoveElement(0);")
            lines.append(f"doc.AddPage(0, {width}, {height});")
    elif page_size:
        width, height = _PAGE_SIZE_POINTS[page_size]
        lines.append(f"doc.AddPage(doc.GetElementsCount(), {width}, {height});")
    else:
        lines.append("doc.AddPage();")
    lines.append("var page = doc.GetElement(doc.GetElementsCount() - 1);")
    return lines


def _emit_block(block: BlockSpec, *, push_target: str = "page") -> list[str]:
    lines: list[str] = []
    if block.type == "table" and block.rows:
        cols = max((len(r) for r in block.rows), default=1)
        lines.append(f"var oTable = Api.CreateTable({cols}, {len(block.rows)});")
        for ri, row in enumerate(block.rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.append(f"{push_target}.Push(oTable);")
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
    lines.append(f"{push_target}.Push(oPara);")
    return lines


def _emit_page_break() -> list[str]:
    return [
        "var pageBreakPara = Api.CreateParagraph();",
        "var pageBreakRun = Api.CreateRun();",
        "pageBreakRun.AddPageBreak();",
        "pageBreakPara.AddElement(pageBreakRun);",
        "doc.Push(pageBreakPara);",
    ]


def build_create_script(
    pages: list[PageSpec],
    *,
    output_ext: str,
    options: PdfCreateOptions,
) -> str:
    create_ext = "docx" if options.create_mode == "via_docx" else "pdf"
    save_ext = output_ext or "pdf"
    lines = [f'builder.CreateFile("{create_ext}");', "var doc = Api.GetDocument();"]

    if options.page_size and options.create_mode == "via_docx":
        lines.extend(_emit_page_size_section("doc", options.page_size))

    if options.create_mode == "via_docx":
        for pi, page_spec in enumerate(pages):
            if pi > 0:
                lines.extend(_emit_page_break())
            for block in page_spec.blocks:
                lines.extend(_emit_block(block, push_target="doc"))
    else:
        for pi, page_spec in enumerate(pages):
            lines.extend(_emit_native_page_open(pi, options.page_size))
            for block in page_spec.blocks:
                lines.extend(_emit_block(block, push_target="page"))

    lines.append(f'builder.SaveFile("{save_ext}", "output.{save_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
