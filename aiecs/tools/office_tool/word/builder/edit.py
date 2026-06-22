"""Builder script generation for office_edit_word."""

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation


def _search_snippet(op: EditOperation) -> str:
    """Text snippet for doc.Search when block_index is not used."""
    if op.match_text:
        return escape_js(op.match_text)
    if op.heading_path:
        return escape_js(op.heading_path[-1])
    if op.after and op.after not in ("start", "end"):
        return escape_js(op.after)
    return ""


def _has_insert_locator(op: EditOperation) -> bool:
    return (
        op.block_index is not None
        or bool(op.heading_path)
        or bool(op.match_text)
        or op.after == "start"
        or (op.after is not None and op.after not in ("start", "end"))
    )


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


def _emit_insert_element(op: EditOperation, element_var: str) -> list[str]:
    """Insert a pre-built element variable at op locator (start / after block / end)."""
    if op.after == "start":
        return [f"doc.InsertContent([{element_var}], true);"]

    if op.block_index is not None:
        return [f"doc.AddElement({op.block_index + 1}, {element_var});"]

    if not _has_insert_locator(op) or op.after == "end":
        return [f"doc.Push({element_var});"]

    locator = EditOperation.model_construct(
        op=op.op,
        block_index=op.block_index,
        heading_path=op.heading_path,
        match_text=op.match_text,
        after=op.after if op.after not in ("start", "end") else None,
    )
    lines = _bind_block_target(locator)[0]
    lines.append("if (blockTarget) {")
    lines.append("  var insertIdx = -1;")
    lines.append("  for (var i = 0; i < doc.GetElementsCount(); i++) {")
    lines.append("    if (doc.GetElement(i) === blockTarget) { insertIdx = i; break; }")
    lines.append("  }")
    lines.append(f"  if (insertIdx >= 0) {{ doc.AddElement(insertIdx + 1, {element_var}); }}")
    lines.append(f"  else {{ doc.Push({element_var}); }}")
    lines.append("} else {")
    lines.append(f"  doc.Push({element_var});")
    lines.append("}")
    return lines


def _emit_insert_many_at_index(op: EditOperation, element_vars: list[str]) -> list[str]:
    """Insert multiple elements after block_index or search-resolved block."""
    if not element_vars:
        return []

    if op.after == "start":
        return [f"doc.InsertContent([{', '.join(element_vars)}], true);"]

    if not _has_insert_locator(op) or op.after == "end":
        return [f"doc.Push({var});" for var in element_vars]

    if op.block_index is not None:
        lines: list[str] = []
        for offset, var in enumerate(element_vars):
            lines.append(f"doc.AddElement({op.block_index + 1 + offset}, {var});")
        return lines

    locator = EditOperation.model_construct(
        op=op.op,
        block_index=op.block_index,
        heading_path=op.heading_path,
        match_text=op.match_text,
        after=op.after if op.after not in ("start", "end") else None,
    )
    lines = _bind_block_target(locator)[0]
    lines.append("if (blockTarget) {")
    lines.append("  var insertIdx = -1;")
    lines.append("  for (var i = 0; i < doc.GetElementsCount(); i++) {")
    lines.append("    if (doc.GetElement(i) === blockTarget) { insertIdx = i; break; }")
    lines.append("  }")
    lines.append("  if (insertIdx >= 0) {")
    for offset, var in enumerate(element_vars):
        lines.append(f"    doc.AddElement(insertIdx + 1 + {offset}, {var});")
    lines.append("  } else {")
    for var in element_vars:
        lines.append(f"    doc.Push({var});")
    lines.append("  }")
    lines.append("} else {")
    for var in element_vars:
        lines.append(f"  doc.Push({var});")
    lines.append("}")
    return lines


def _emit_search_replace(op: EditOperation) -> list[str]:
    search = escape_js(op.search_string or "")
    replace = escape_js(op.replace_string or "")
    use_subtree = op.scope == "subtree" or bool(op.heading_path) or op.block_index is not None or op.match_text

    if not use_subtree:
        return [
            f'doc.SearchAndReplace({{"searchString": "{search}", '
            f'"replaceString": "{replace}"}});'
        ]

    locator = EditOperation.model_construct(
        op="search_replace",
        block_index=op.block_index,
        heading_path=op.heading_path,
        match_text=op.match_text,
    )
    lines = _bind_block_target(locator)[0]
    lines.append("if (blockTarget) {")
    lines.append("  var _txt = blockTarget.GetText();")
    lines.append(f'  blockTarget.SetText(_txt.split("{search}").join("{replace}"));')
    lines.append("} else {")
    lines.append(
        f'  doc.SearchAndReplace({{"searchString": "{search}", "replaceString": "{replace}"}});'
    )
    lines.append("}")
    return lines


def _emit_page_break_paragraph(var_prefix: str, *, section: bool) -> list[str]:
    lines = [
        f"var {var_prefix}Para = Api.CreateParagraph();",
        f"var {var_prefix}Run = Api.CreateRun();",
    ]
    if section:
        lines.append(f'{var_prefix}Run.AddBreak("section");')
    else:
        lines.append(f"{var_prefix}Run.AddPageBreak();")
    lines.append(f"{var_prefix}Para.AddElement({var_prefix}Run);")
    return lines


def _emit_operation(op: EditOperation) -> list[str]:
    lines: list[str] = []
    name = op.op

    if name == "search_replace":
        lines.extend(_emit_search_replace(op))
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
        lines.extend(_emit_insert_element(op, "oPara"))
    elif name == "insert_bullets":
        bullet_vars: list[str] = []
        for idx, item in enumerate(op.items or []):
            var = f"oBulletPara{idx}"
            bullet_vars.append(var)
            lines.append(f"var {var} = Api.CreateParagraph();")
            lines.append(f'{var}.AddText("\u2022 {escape_js(str(item))}");')
        lines.extend(_emit_insert_many_at_index(op, bullet_vars))
    elif name == "insert_table":
        rows = op.rows or []
        cols = max((len(r) for r in rows), default=1)
        lines.append(f"var oTable = Api.CreateTable({cols}, {len(rows)});")
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.extend(_emit_insert_element(op, "oTable"))
    elif name == "delete_block":
        lines.extend(_bind_block_target(op)[0])
        lines.append("if (blockTarget) { blockTarget.Delete(); }")
    elif name == "apply_style":
        style = escape_js(op.style_name or "Normal")
        lines.extend(_bind_block_target(op)[0])
        lines.append(f'if (blockTarget) {{ blockTarget.SetStyle("{style}"); }}')
    elif name == "add_page_break":
        lines.extend(_emit_page_break_paragraph("pageBreak", section=False))
        lines.extend(_emit_insert_element(op, "pageBreakPara"))
    elif name == "insert_section_break":
        lines.extend(_emit_page_break_paragraph("sectionBreak", section=True))
        lines.extend(_emit_insert_element(op, "sectionBreakPara"))
    elif name == "insert_toc":
        lines.append("doc.MoveCursorToStart();")
        lines.append("doc.AddTableOfContents({});")

    return lines


def build_edit_script(operations: list[EditOperation], *, file_ext: str) -> str:
    lines = ["var doc = Api.GetDocument();"]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
