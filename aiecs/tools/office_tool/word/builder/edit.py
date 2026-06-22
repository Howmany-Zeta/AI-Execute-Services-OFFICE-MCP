"""Builder script generation for office_edit_word."""

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation


def _search_snippet(op: EditOperation) -> str:
    """Text snippet for doc.Search when block_index is not used."""
    if op.match_text:
        return escape_js(op.match_text)
    if op.heading_path:
        return escape_js(op.heading_path[-1])
    return ""


def _bind_block_target(op: EditOperation) -> tuple[list[str], str]:
    """
    Resolve edit target to a JS variable holding the block element.

    block_index maps to doc.GetElement(block_index) — aligned with fine read
    blocks[] order from ToJSON body traversal (0-based top-level elements).
    """
    lines: list[str] = []
    if op.block_index is not None:
        lines.append(f"var blockTarget = doc.GetElement({op.block_index});")
        return lines, "blockTarget"

    snippet = _search_snippet(op)
    if snippet:
        lines.append(f'var search = doc.Search("{snippet}");')
        lines.append("var blockTarget = search.length > 0 ? search[0] : null;")
        return lines, "blockTarget"

    lines.append("var blockTarget = null;")
    return lines, "blockTarget"


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    name = op.op

    if name == "search_replace":
        lines.append(
            f'doc.SearchAndReplace({{"searchString": "{escape_js(op.search_string or "")}", '
            f'"replaceString": "{escape_js(op.replace_string or "")}"}});'
        )
    elif name == "set_block_text":
        lines.extend(_bind_block_target(op)[0])
        lines.append(
            'if (blockTarget) { blockTarget.SetText("' + escape_js(op.text or "") + '"); }'
        )
    elif name == "set_heading":
        level = 1
        if op.style_name and op.style_name[-1].isdigit():
            level = int(op.style_name[-1])
        lines.extend(_bind_block_target(op)[0])
        lines.append("if (blockTarget) {")
        lines.append(f'  blockTarget.SetText("{escape_js(op.text or "")}");')
        lines.append(f'  blockTarget.SetStyle("Heading {level}");')
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
        lines.extend(_bind_block_target(op)[0])
        lines.append("if (blockTarget) { blockTarget.Delete(); }")
    elif name == "apply_style":
        style = escape_js(op.style_name or "Normal")
        lines.extend(_bind_block_target(op)[0])
        lines.append(f'if (blockTarget) {{ blockTarget.SetStyle("{style}"); }}')
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
