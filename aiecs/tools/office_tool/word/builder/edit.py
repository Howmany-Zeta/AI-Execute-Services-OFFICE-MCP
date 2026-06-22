"""Builder script generation for office_edit_word."""

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation


def _locator_snippet(op: EditOperation) -> str:
    if op.match_text:
        return escape_js(op.match_text)
    if op.heading_path:
        return escape_js(op.heading_path[-1])
    if op.text:
        return escape_js(op.text[:80])
    return ""


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    name = op.op

    if name == "search_replace":
        lines.append(
            f'doc.SearchAndReplace({{"searchString": "{escape_js(op.search_string or "")}", '
            f'"replaceString": "{escape_js(op.replace_string or "")}"}});'
        )
    elif name == "set_block_text":
        snippet = _locator_snippet(op)
        lines.append(f'var search = doc.Search("{snippet}");')
        lines.append("if (search.length > 0) { search[0].SetText(\"" + escape_js(op.text or "") + "\"); }")
    elif name == "set_heading":
        snippet = _locator_snippet(op)
        level = 1
        if op.style_name and op.style_name[-1].isdigit():
            level = int(op.style_name[-1])
        lines.append(f'var search = doc.Search("{snippet}");')
        lines.append("if (search.length > 0) {")
        lines.append(f'  search[0].SetText("{escape_js(op.text or "")}");')
        lines.append(f'  search[0].SetStyle("Heading {level}");')
        lines.append("}")
    elif name == "insert_paragraph":
        lines.append("var oPara = Api.CreateParagraph();")
        lines.append(f'oPara.AddText("{escape_js(op.text or "")}");')
        if op.after == "start":
            lines.append("doc.InsertContent([oPara], true);")
        else:
            lines.append("doc.Push(oPara);")
    elif name == "insert_bullets":
        for item in op.items or []:
            lines.append("var oPara = Api.CreateParagraph();")
            lines.append(f'oPara.AddText("\u2022 {escape_js(str(item))}");')
            lines.append("doc.Push(oPara);")
    elif name == "insert_table":
        rows = op.rows or []
        cols = max((len(r) for r in rows), default=1)
        lines.append(f"var oTable = Api.CreateTable({cols}, {len(rows)});")
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.append("doc.Push(oTable);")
    elif name == "delete_block":
        snippet = _locator_snippet(op)
        lines.append(f'var search = doc.Search("{snippet}");')
        lines.append("if (search.length > 0) { search[0].Delete(); }")
    elif name == "apply_style":
        snippet = _locator_snippet(op)
        style = escape_js(op.style_name or "Normal")
        lines.append(f'var search = doc.Search("{snippet}");')
        lines.append(f'if (search.length > 0) {{ search[0].SetStyle("{style}"); }}')
    elif name == "add_page_break":
        lines.append("var pageBreakPara = Api.CreateParagraph();")
        lines.append("var pageBreakRun = Api.CreateRun();")
        lines.append("pageBreakRun.AddPageBreak();")
        lines.append("pageBreakPara.AddElement(pageBreakRun);")
        lines.append("doc.Push(pageBreakPara);")
    elif name == "insert_toc":
        lines.append("doc.MoveCursorToStart();")
        lines.append("doc.AddTableOfContents({});")

    return lines


def build_edit_script(operations: list[EditOperation], *, file_ext: str) -> str:
    lines = ["var doc = Api.GetDocument();"]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
