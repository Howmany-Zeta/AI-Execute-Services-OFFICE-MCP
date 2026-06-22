"""Builder script generation for office_create_word."""

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.word.schemas.section_spec import SectionSpec, WordCreateOptions

# Page dimensions in twips (1/1440 inch). Portrait orientation.
_PAGE_SIZE_TWIPS: dict[str, tuple[int, int]] = {
    "A4": (11906, 16838),
    "Letter": (12240, 15840),
}


def _emit_create_options(doc_var: str, options: WordCreateOptions) -> list[str]:
    lines: list[str] = []
    if options.title:
        lines.append(f'{doc_var}.GetCore().SetTitle("{escape_js(options.title)}");')
    if options.page_size:
        width, height = _PAGE_SIZE_TWIPS[options.page_size]
        lines.append(f"var section = {doc_var}.GetFinalSection();")
        lines.append(f"section.SetPageSize({width}, {height}, true);")
    return lines


def _emit_section(spec: SectionSpec) -> list[str]:
    lines: list[str] = []
    stype = spec.type

    if stype == "page_break":
        lines.append("var pageBreakPara = Api.CreateParagraph();")
        lines.append("var pageBreakRun = Api.CreateRun();")
        lines.append("pageBreakRun.AddPageBreak();")
        lines.append("pageBreakPara.AddElement(pageBreakRun);")
        lines.append("doc.Push(pageBreakPara);")
        return lines

    if stype == "table":
        rows = spec.rows or []
        cols = max((len(r) for r in rows), default=1)
        lines.append(f"var oTable = Api.CreateTable({cols}, {len(rows)});")
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                lines.append(f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");')
        lines.append("doc.Push(oTable);")
        return lines

    if stype == "bullets":
        for item in spec.items or []:
            lines.append("var oPara = Api.CreateParagraph();")
            lines.append(f'oPara.AddText("\u2022 {escape_js(str(item))}");')
            lines.append("doc.Push(oPara);")
        return lines

    lines.append("var oPara = Api.CreateParagraph();")
    lines.append("var oRun = Api.CreateRun();")
    text = escape_js(spec.text or "")
    lines.append(f'oRun.AddText("{text}");')
    if spec.bold:
        lines.append("oRun.SetBold(true);")
    lines.append("oPara.AddElement(oRun);")
    if stype.startswith("heading"):
        level = stype[-1]
        lines.append(f'oPara.SetStyle("Heading {level}");')
    lines.append("doc.Push(oPara);")
    return lines


def build_create_script(
    sections: list[SectionSpec],
    *,
    output_ext: str,
    options: WordCreateOptions,
) -> str:
    lines = [f'builder.CreateFile("{output_ext}");', "var doc = Api.GetDocument();"]
    lines.extend(_emit_create_options("doc", options))
    if options.add_toc:
        lines.append("doc.AddTableOfContents({});")
    for spec in sections:
        lines.extend(_emit_section(spec))
    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
