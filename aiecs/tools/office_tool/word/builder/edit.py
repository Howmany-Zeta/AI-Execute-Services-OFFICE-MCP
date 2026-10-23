"""Builder script generation for office_edit_word."""

import json

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.word.schemas.edit_ops import EditOperation

_VISIBLE_RUN_HELPER = """
function _officeVisibleRuns(el) {
  var runs = [];
  if (!el) return runs;
  function walk(node) {
    if (!node) return;
    var cls = "";
    try { cls = String(node.GetClassType ? node.GetClassType() : "").toLowerCase(); } catch (e) { cls = ""; }
    if (cls.indexOf("drawing") >= 0 || cls.indexOf("shape") >= 0 || cls === "image" || cls === "oleobject") return;
    if (cls === "run" || cls === "textrun") { runs.push(node); return; }
    var n = 0;
    try { n = node.GetElementsCount ? node.GetElementsCount() : 0; } catch (e2) { n = 0; }
    if (!n) {
      if (node.GetText || node.SetBold) runs.push(node);
      return;
    }
    for (var i = 0; i < n; i++) {
      var child = null;
      try { child = node.GetElement(i); } catch (e3) { child = null; }
      walk(child);
    }
  }
  walk(el);
  return runs;
}
function _officeBindPara(blockTarget, row, col) {
  if (!blockTarget) return null;
  if (row === null || col === null) return blockTarget;
  try {
    var cell = blockTarget.GetCell(row, col);
    if (cell && cell.GetContent) return cell.GetContent().GetElement(0);
  } catch (e) {}
  return blockTarget;
}
"""


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


def _emit_page_break_paragraph(var_prefix: str, *, section: bool, break_arg: str = "section") -> list[str]:
    lines = [
        f"var {var_prefix}Para = Api.CreateParagraph();",
        f"var {var_prefix}Run = Api.CreateRun();",
    ]
    if section:
        lines.append(
            f'try {{ {var_prefix}Run.AddBreak("{break_arg}"); }}'
            f' catch (eBr1) {{ try {{ {var_prefix}Run.AddBreak("section"); }}'
            f" catch (eBr2) {{ try {{ {var_prefix}Run.AddPageBreak(); }} catch (eBr3) {{}} }} }}"
        )
    else:
        lines.append(f"{var_prefix}Run.AddPageBreak();")
    lines.append(f"{var_prefix}Para.AddElement({var_prefix}Run);")
    return lines


def _heading_level_value(op: EditOperation) -> int:
    if op.heading_level is not None:
        return op.heading_level
    if op.style_name:
        digits = "".join(ch for ch in op.style_name if ch.isdigit())
        if digits:
            return max(1, min(6, int(digits[0])))
    return 1


def _image_src(op: EditOperation) -> str:
    if op.content_base64:
        return f"data:image/png;base64,{op.content_base64}"
    return op.url or ""


def _emit_run_format(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    row = "null" if op.row is None else str(op.row)
    col = "null" if op.col is None else str(op.col)
    run_index = 0 if op.run_index is None else op.run_index
    lines.append(f"var formatPara = _officeBindPara(blockTarget, {row}, {col});")
    lines.append("if (formatPara) {")
    lines.append("  var formatRuns = _officeVisibleRuns(formatPara);")
    lines.append(f"  var formatRun = formatRuns[{run_index}];")
    lines.append("  if (formatRun) {")
    if op.bold is not None:
        lines.append(f"    formatRun.SetBold({str(op.bold).lower()});")
    if op.italic is not None:
        lines.append(f"    formatRun.SetItalic({str(op.italic).lower()});")
    if op.underline is not None:
        underline = "true" if op.underline else "false"
        lines.append(f"    formatRun.SetUnderline({underline});")
    if op.font_name:
        lines.append(f'    formatRun.SetFontFamily("{escape_js(op.font_name)}");')
    if op.font_size_pt is not None:
        lines.append(f"    formatRun.SetFontSize({float(op.font_size_pt)});")
    if op.strike is not None:
        lines.append(f"    formatRun.SetStrikeout({str(op.strike).lower()});")
    if op.highlight is not None:
        if op.highlight == "none":
            lines.append('    formatRun.SetHighlight("none");')
        else:
            lines.append(f'    formatRun.SetHighlight("{escape_js(op.highlight)}");')
    if op.font_color:
        color = op.font_color.lstrip("#")
        if len(color) == 6:
            red = int(color[0:2], 16)
            green = int(color[2:4], 16)
            blue = int(color[4:6], 16)
            lines.append(f"    formatRun.SetColor(Api.CreateColorFromRGB({red}, {green}, {blue}));")
    lines.append("  }")
    lines.append("}")
    return lines


def _emit_paragraph_format(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    row = "null" if op.row is None else str(op.row)
    col = "null" if op.col is None else str(op.col)
    lines.append(f"var paraFmt = _officeBindPara(blockTarget, {row}, {col});")
    lines.append("if (paraFmt) {")
    if op.align:
        lines.append(f'  paraFmt.SetJc("{escape_js(op.align)}");')
    if op.style_name:
        lines.append(f'  paraFmt.SetStyle("{escape_js(op.style_name)}");')
    lines.append("}")
    return lines


def _emit_set_list(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    list_type = "bullet" if op.list_type == "bullet" else "numbered"
    level = 0 if op.list_level is None else op.list_level
    lines.append("if (blockTarget) {")
    lines.append(f'  var numbering = doc.CreateNumbering("{list_type}");')
    lines.append(f"  var numLevel = numbering.GetLevel({level});")
    lines.append("  blockTarget.SetNumbering(numLevel);")
    lines.append("}")
    return lines


def _emit_set_cell_text(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    lines.append(f"  var cell = blockTarget.GetCell({op.row}, {op.col});")
    lines.append("  if (cell && cell.GetContent) {")
    lines.append("    var cellPara = cell.GetContent().GetElement(0);")
    lines.append(f'    if (cellPara) {{ cellPara.SetText("{escape_js(op.text or "")}"); }}')
    lines.append("  }")
    lines.append("}")
    return lines


def _emit_table_row_col(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    if op.op == "insert_table_row":
        lines.append(f"  if (blockTarget.AddRow) {{ blockTarget.AddRow({op.row}); }}")
    elif op.op == "delete_table_row":
        lines.append(f"  var delRow = null;")
        lines.append(f"  try {{ delRow = blockTarget.GetRow({op.row}); }} catch (eGR) {{ delRow = null; }}")
        lines.append("  try {")
        lines.append("    if (delRow && blockTarget.RemoveRow) { blockTarget.RemoveRow(delRow); }")
        lines.append(f"    else if (blockTarget.RemoveRow) {{ blockTarget.RemoveRow({op.row}); }}")
        lines.append("    else if (delRow && delRow.Delete) { delRow.Delete(); }")
        lines.append("  } catch (eRR) {}")
    elif op.op == "insert_table_column":
        lines.append(f"  if (blockTarget.AddColumn) {{ blockTarget.AddColumn({op.col}); }}")
    elif op.op == "delete_table_column":
        lines.append(f"  var delCell = null;")
        lines.append(f"  try {{ delCell = blockTarget.GetCell(0, {op.col}); }} catch (eGC) {{ delCell = null; }}")
        lines.append("  try {")
        lines.append("    if (delCell && blockTarget.RemoveColumn) { blockTarget.RemoveColumn(delCell); }")
        lines.append(f"    else if (blockTarget.RemoveColumn) {{ blockTarget.RemoveColumn({op.col}); }}")
        lines.append("  } catch (eRC) {}")
    lines.append("}")
    return lines


def _emit_header_footer(op: EditOperation) -> list[str]:
    section_index = 0 if op.section_index is None else op.section_index
    getter = "GetHeader" if op.op == "set_header" else "GetFooter"
    variant = op.variant or "default"
    api_variant = "title" if variant == "first" else variant
    lines = [
        "var sections = doc.GetSections ? doc.GetSections() : [];",
        f"var section = sections[{section_index}] || (doc.GetFinalSection ? doc.GetFinalSection() : null);",
        "if (section) {",
    ]
    if variant == "first":
        lines.append("  if (section.SetTitlePage) { section.SetTitlePage(true); }")
    if variant == "even":
        lines.append("  if (section.SetEvenAndOddHdFtr) { section.SetEvenAndOddHdFtr(true); }")
        lines.append("  else if (section.SetEvenAndOddHdrFtr) { section.SetEvenAndOddHdrFtr(true); }")
    lines.extend([
        f'  var hfPart = null;',
        f'  try {{ hfPart = section.{getter}("{api_variant}", true); }} catch (eHf1) {{ hfPart = null; }}',
        f'  if (!hfPart) {{ try {{ hfPart = section.{getter}("{api_variant}"); }} catch (eHf2) {{ hfPart = null; }} }}',
        "  if (hfPart) {",
        "    var hfPara = null;",
        "    try { hfPara = hfPart.GetElement(0); } catch (eHf3) { hfPara = null; }",
        "    if (!hfPara) { hfPara = Api.CreateParagraph(); if (hfPart.Push) { hfPart.Push(hfPara); } }",
        f'    try {{ hfPara.SetText("{escape_js(op.text or "")}"); }} catch (eHf4) {{ if (hfPara.AddText) hfPara.AddText("{escape_js(op.text or "")}"); }}',
    ])
    if op.page_number is not None:
        position = op.page_number.position or "left"
        lines.append("    hfPara.AddPageNumber();")
        lines.append(f'    hfPara.SetJc("{escape_js(position)}");')
        if op.page_number.start is not None:
            lines.append(f"    section.SetStartPageNumber({int(op.page_number.start)});")
    lines.extend(["  }", "}"])
    return lines


def _emit_set_section(op: EditOperation) -> list[str]:
    section_index = 0 if op.section_index is None else op.section_index
    lines = [
        "var sections = doc.GetSections ? doc.GetSections() : [];",
        f"var section = sections[{section_index}] || (doc.GetFinalSection ? doc.GetFinalSection() : null);",
        "if (section) {",
    ]
    if op.columns is not None:
        lines.append(f"  if (section.SetEqualColumns) {{ section.SetEqualColumns({int(op.columns)}, 720); }}")
    if op.different_first_page is not None:
        lines.append(f"  if (section.SetTitlePage) {{ section.SetTitlePage({str(op.different_first_page).lower()}); }}")
    if op.odd_even_headers is not None:
        flag = str(op.odd_even_headers).lower()
        lines.append(f"  if (section.SetEvenAndOddHdFtr) {{ section.SetEvenAndOddHdFtr({flag}); }}")
        lines.append(f"  else if (section.SetEvenAndOddHdrFtr) {{ section.SetEvenAndOddHdrFtr({flag}); }}")
    lines.append("}")
    return lines


def _section_break_arg(op: EditOperation) -> str:
    if op.break_type is None:
        return "section"
    mapping = {
        "next": "nextPage",
        "continuous": "continuous",
        "even": "evenPage",
        "odd": "oddPage",
    }
    return mapping.get(op.break_type, "section")


def _pt_to_emu(value: float | None, default: float) -> int:
    return int((default if value is None else value) * 12700)


def _emit_insert_footnote(op: EditOperation) -> list[str]:
    note_type = op.type or "footnote"
    create = "AddEndnote" if note_type == "endnote" else "AddFootnote"
    lines = _bind_block_target(op)[0]
    run_index = 0 if op.run_index is None else op.run_index
    lines.append("if (blockTarget) {")
    lines.append("  var noteRuns = _officeVisibleRuns(blockTarget);")
    lines.append(f"  var noteRun = noteRuns[{run_index}];")
    lines.append(f"  var note = noteRun && noteRun.{create} ? noteRun.{create}() : (blockTarget.{create} ? blockTarget.{create}() : null);")
    lines.append("  if (note) {")
    if op.footnote_id:
        lines.append(f'    if (note.SetId) {{ note.SetId("{escape_js(op.footnote_id)}"); }}')
    lines.append(f'    if (note.SetText) {{ note.SetText("{escape_js(op.text or "")}"); }}')
    lines.append("    else if (note.GetContent) {")
    lines.append("      var notePara = note.GetContent().GetElement(0);")
    lines.append(f'      if (notePara) {{ notePara.SetText("{escape_js(op.text or "")}"); }}')
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    return lines


def _emit_footnote_by_id(op: EditOperation) -> list[str]:
    getter = "GetAllEndnotes" if op.type == "endnote" else "GetAllFootnotes"
    lines = [
        f"var notes = doc.{getter} ? doc.{getter}() : [];",
        "for (var ni = 0; ni < notes.length; ni++) {",
        f'  var nid = notes[ni].GetId ? String(notes[ni].GetId()) : String(ni);',
        f'  if (nid === "{escape_js(op.footnote_id or "")}") {{',
    ]
    if op.op == "delete_footnote":
        lines.append("    if (notes[ni].Delete) { notes[ni].Delete(); }")
    else:
        lines.append(f'    if (notes[ni].SetText) {{ notes[ni].SetText("{escape_js(op.text or "")}"); }}')
        lines.append("    else if (notes[ni].GetContent) {")
        lines.append("      var np = notes[ni].GetContent().GetElement(0);")
        lines.append(f'      if (np) {{ np.SetText("{escape_js(op.text or "")}"); }}')
        lines.append("    }")
    lines.extend(["    break;", "  }", "}"])
    return lines


def _emit_insert_comment(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    lines.append(f'  if (blockTarget.AddComment) {{ blockTarget.AddComment("{escape_js(op.text or "")}"); }}')
    lines.append(f'  else if (doc.AddComment) {{ doc.AddComment("{escape_js(op.text or "")}"); }}')
    lines.append("}")
    return lines


def _emit_comment_by_id(op: EditOperation) -> list[str]:
    lines = [
        "var comments = doc.GetAllComments ? doc.GetAllComments() : [];",
        "for (var ci = 0; ci < comments.length; ci++) {",
        '  var cid = comments[ci].GetId ? String(comments[ci].GetId()) : String(ci);',
        f'  if (cid === "{escape_js(op.comment_id or "")}") {{',
    ]
    if op.op == "delete_comment":
        lines.append("    if (comments[ci].Delete) { comments[ci].Delete(); }")
    else:
        lines.append(f'    if (comments[ci].SetText) {{ comments[ci].SetText("{escape_js(op.text or "")}"); }}')
        lines.append(f'    else if (comments[ci].SetContents) {{ comments[ci].SetContents("{escape_js(op.text or "")}"); }}')
    lines.extend(["    break;", "  }", "}"])
    return lines


def _emit_insert_caption(op: EditOperation) -> list[str]:
    lines = ["var oCaption = Api.CreateParagraph();"]
    lines.append(f'oCaption.AddText("{escape_js(op.text or "")}");')
    lines.append('if (oCaption.SetStyle) { oCaption.SetStyle("Caption"); }')
    if op.target_block_index is not None:
        lines.append(f"doc.AddElement({op.target_block_index + 1}, oCaption);")
    else:
        lines.extend(_emit_insert_element(op, "oCaption"))
    return lines


def _emit_insert_chart(op: EditOperation) -> list[str]:
    rows = op.rows or []
    series = [[str(cell) for cell in row] for row in rows]
    width = _pt_to_emu(op.width_pt, 400)
    height = _pt_to_emu(op.height_pt, 300)
    lines = [
        f'var oChart = Api.CreateChart("{escape_js(op.chart_type or "bar")}", {json.dumps(series)}, [], [], {width}, {height});',
        "var oChartPara = Api.CreateParagraph();",
        "if (oChartPara.AddDrawing) { oChartPara.AddDrawing(oChart); }",
        "else { oChartPara.AddElement(oChart); }",
    ]
    lines.extend(_emit_insert_element(op, "oChartPara"))
    return lines


def _emit_set_chart_data(op: EditOperation) -> list[str]:
    rows = op.rows or []
    series = [[str(cell) for cell in row] for row in rows]
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    lines.append(f"  if (blockTarget.SetChartData) {{ blockTarget.SetChartData({json.dumps(series)}); }}")
    if op.chart_type:
        lines.append(f'  if (blockTarget.SetChartType) {{ blockTarget.SetChartType("{escape_js(op.chart_type)}"); }}')
    lines.append("}")
    return lines


def _emit_insert_textbox(op: EditOperation) -> list[str]:
    width = _pt_to_emu(op.width_pt, 200)
    height = _pt_to_emu(op.height_pt, 80)
    x = _pt_to_emu(op.x_pt, 0)
    y = _pt_to_emu(op.y_pt, 0)
    lines = [
        f'var oBox = Api.CreateShape("rect", {width}, {height});',
        f"if (oBox.SetPosition) {{ oBox.SetPosition({x}, {y}); }}",
        f'if (oBox.SetText) {{ oBox.SetText("{escape_js(op.text or "")}"); }}',
        "var oBoxPara = Api.CreateParagraph();",
        "if (oBoxPara.AddDrawing) { oBoxPara.AddDrawing(oBox); }",
        "else { oBoxPara.AddElement(oBox); }",
    ]
    lines.extend(_emit_insert_element(op, "oBoxPara"))
    return lines


def _emit_set_textbox_geometry(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    if op.x_pt is not None or op.y_pt is not None:
        x = _pt_to_emu(op.x_pt, 0)
        y = _pt_to_emu(op.y_pt, 0)
        lines.append(f"  if (blockTarget.SetPosition) {{ blockTarget.SetPosition({x}, {y}); }}")
    if op.width_pt is not None or op.height_pt is not None:
        w = _pt_to_emu(op.width_pt, 200)
        h = _pt_to_emu(op.height_pt, 80)
        lines.append(f"  if (blockTarget.SetSize) {{ blockTarget.SetSize({w}, {h}); }}")
    lines.append("}")
    return lines


def _emit_insert_image(op: EditOperation) -> list[str]:
    src = escape_js(_image_src(op))
    width = int((op.width_pt or 200) * 12700)
    height = int((op.height_pt or 150) * 12700)
    lines = [
        f'var oImage = Api.CreateImage("{src}", {width}, {height});',
        "var oImagePara = Api.CreateParagraph();",
        "if (oImagePara.AddDrawing) { oImagePara.AddDrawing(oImage); }",
        "else if (oImagePara.AddImage) { oImagePara.AddImage(oImage); }",
        "else { oImagePara.AddElement(oImage); }",
    ]
    lines.extend(_emit_insert_element(op, "oImagePara"))
    return lines


def _emit_replace_image(op: EditOperation) -> list[str]:
    src = escape_js(_image_src(op))
    image_index = 0 if op.image_index is None else op.image_index
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    lines.append(f'  if (blockTarget.SetImage) {{ blockTarget.SetImage("{src}"); }}')
    lines.append("  else {")
    lines.append("    var replaced = 0;")
    lines.append("    var childCount = 0;")
    lines.append("    try { childCount = blockTarget.GetElementsCount(); } catch (e) { childCount = 0; }")
    lines.append("    for (var ci = 0; ci < childCount; ci++) {")
    lines.append("      var child = blockTarget.GetElement(ci);")
    lines.append("      var cls = child && child.GetClassType ? String(child.GetClassType()).toLowerCase() : \"\";")
    lines.append("      if (cls.indexOf(\"image\") >= 0 || cls.indexOf(\"drawing\") >= 0 || (child && child.SetImage)) {")
    lines.append(f"        if (replaced === {image_index} && child.SetImage) {{ child.SetImage(\"{src}\"); break; }}")
    lines.append("        replaced++;")
    lines.append("      }")
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    return lines


def _emit_hyperlink(op: EditOperation) -> list[str]:
    lines = _bind_block_target(op)[0]
    lines.append("if (blockTarget) {")
    lines.append("  var linkRuns = _officeVisibleRuns(blockTarget);")
    lines.append(f"  var linkRun = linkRuns[{op.run_index}];")
    lines.append("  if (linkRun) {")
    if op.op == "set_hyperlink":
        lines.append(f'    if (linkRun.SetHyperlink) {{ linkRun.SetHyperlink("{escape_js(op.url or "")}"); }}')
        lines.append(
            f'    else {{ var hl = Api.CreateHyperlink("{escape_js(op.url or "")}", linkRun.GetText ? linkRun.GetText() : ""); '
            "if (hl) { blockTarget.AddElement(hl); } }"
        )
    else:
        lines.append("    if (linkRun.RemoveHyperlink) { linkRun.RemoveHyperlink(); }")
        lines.append('    else if (linkRun.SetHyperlink) { linkRun.SetHyperlink(""); }')
    lines.append("  }")
    lines.append("}")
    return lines


def _emit_move_block(op: EditOperation) -> list[str]:
    lines = [f"var moveSrc = doc.GetElement({op.block_index});"]
    if op.to_block_index is not None:
        lines.append(f"var moveDest = {op.to_block_index};")
    else:
        snippet = escape_js((op.heading_path or [""])[-1])
        lines.append(f'var moveSearch = doc.Search("{snippet}");')
        lines.append("var moveDest = -1;")
        lines.append("if (moveSearch.length > 0) {")
        lines.append("  for (var mi = 0; mi < doc.GetElementsCount(); mi++) {")
        lines.append("    if (doc.GetElement(mi) === moveSearch[0]) { moveDest = mi; break; }")
        lines.append("  }")
        lines.append("}")
    lines.append("if (moveSrc && moveDest >= 0) {")
    lines.append(f"  var fromIdx = {op.block_index};")
    lines.append("  if (doc.RemoveElement) { doc.RemoveElement(fromIdx); } else { moveSrc.Delete(); }")
    lines.append("  if (moveDest > fromIdx) { moveDest -= 1; }")
    lines.append("  doc.AddElement(moveDest, moveSrc);")
    lines.append("}")
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
        level = _heading_level_value(op)
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
        lines.extend(
            _emit_page_break_paragraph("sectionBreak", section=True, break_arg=_section_break_arg(op))
        )
        lines.extend(_emit_insert_element(op, "sectionBreakPara"))
    elif name == "insert_toc":
        lines.append("doc.MoveCursorToStart();")
        lines.append("doc.AddTableOfContents({});")
    elif name == "set_run_format":
        lines.extend(_emit_run_format(op))
    elif name == "set_paragraph_format":
        lines.extend(_emit_paragraph_format(op))
    elif name == "set_list":
        lines.extend(_emit_set_list(op))
    elif name == "set_cell_text":
        lines.extend(_emit_set_cell_text(op))
    elif name in ("insert_table_row", "delete_table_row", "insert_table_column", "delete_table_column"):
        lines.extend(_emit_table_row_col(op))
    elif name == "delete_table":
        lines.extend(_bind_block_target(op)[0])
        lines.append("if (blockTarget) { blockTarget.Delete(); }")
    elif name in ("set_header", "set_footer"):
        lines.extend(_emit_header_footer(op))
    elif name == "insert_image":
        lines.extend(_emit_insert_image(op))
    elif name == "replace_image":
        lines.extend(_emit_replace_image(op))
    elif name in ("set_hyperlink", "remove_hyperlink"):
        lines.extend(_emit_hyperlink(op))
    elif name == "move_block":
        lines.extend(_emit_move_block(op))
    elif name == "set_section":
        lines.extend(_emit_set_section(op))
    elif name == "insert_footnote":
        lines.extend(_emit_insert_footnote(op))
    elif name in ("set_footnote_text", "delete_footnote"):
        lines.extend(_emit_footnote_by_id(op))
    elif name == "insert_comment":
        lines.extend(_emit_insert_comment(op))
    elif name in ("set_comment", "delete_comment"):
        lines.extend(_emit_comment_by_id(op))
    elif name == "insert_caption":
        lines.extend(_emit_insert_caption(op))
    elif name == "insert_chart":
        lines.extend(_emit_insert_chart(op))
    elif name == "set_chart_data":
        lines.extend(_emit_set_chart_data(op))
    elif name == "insert_textbox":
        lines.extend(_emit_insert_textbox(op))
    elif name == "set_textbox_geometry":
        lines.extend(_emit_set_textbox_geometry(op))

    return lines


def build_edit_script(operations: list[EditOperation], *, file_ext: str) -> str:
    lines = ["var doc = Api.GetDocument();", _VISIBLE_RUN_HELPER.strip()]
    for op in operations:
        lines.extend(_emit_operation(op))
    return "\n".join(lines)
