"""Builder script generation for office_edit_pdf (edit body only)."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.pdf.schemas.edit_ops import EditOperation
from aiecs.tools.office_tool.pdf.schemas.page_spec import BlockSpec

_PDF_EDIT_HELPERS = """
function _officePdfPage(doc, i) {
  if (doc.GetPage) {
    try { var p = doc.GetPage(i); if (p) return p; } catch (e) {}
  }
  return doc.GetElement ? doc.GetElement(i) : null;
}
function _officePdfPageCount(doc) {
  if (doc.GetPagesCount) {
    try { var n = doc.GetPagesCount(); if (typeof n === "number") return n; } catch (e) {}
  }
  return doc.GetElementsCount ? doc.GetElementsCount() : 0;
}
function _officePdfJc(align) {
  return align === "justify" ? "both" : align;
}
function _officePdfPush(page, obj) {
  if (!page || !obj) return;
  if (page.Push) { page.Push(obj); return; }
  if (page.AddObject) { page.AddObject(obj); }
}
function _officePdfBlock(page, index) {
  if (page && page.GetElement) {
    try { var el = page.GetElement(index); if (el) return el; } catch (e) {}
  }
  if (page && page.GetAllDrawings) {
    try {
      var drawings = page.GetAllDrawings() || [];
      if (drawings[index]) return drawings[index];
    } catch (e) {}
  }
  if (page && page.GetAllAnnots) {
    try {
      var annots = page.GetAllAnnots() || [];
      if (annots[index]) return annots[index];
      if (annots.length === 1) return annots[0];
    } catch (e) {}
  }
  return null;
}
function _officePdfSetCell(el, row, col, text) {
  if (el && el.GetCell) {
    var cell = el.GetCell(row, col);
    if (cell && cell.GetContent) {
      var cellPara = cell.GetContent().GetElement(0);
      if (cellPara) {
        if (cellPara.SetText) cellPara.SetText(text);
        else if (cellPara.AddText) cellPara.AddText(text);
      }
    }
  }
  if (el && el.GetContents && el.SetContents) {
    var raw = String(el.GetContents() || "");
    if (raw.indexOf("<<<TABLE>>>") === 0) {
      var body = raw.slice(11);
      var rows = body.split("\\n");
      var cells = (rows[row] || "").split("\\t");
      cells[col] = text;
      rows[row] = cells.join("\\t");
      el.SetContents("<<<TABLE>>>" + rows.join("\\n"));
    }
  }
}
function _officePdfSetText(el, text) {
  if (!el) return;
  if (el.SetText) { el.SetText(text); return; }
  if (el.SetContents) { el.SetContents(text); return; }
  var content = el.GetContent ? el.GetContent() : (el.GetDocContent ? el.GetDocContent() : null);
  var para = content && content.GetElement ? content.GetElement(0) : el;
  if (para && para.SetText) { para.SetText(text); return; }
  if (para && para.AddText) { para.AddText(text); }
}
function _officePdfAddText(page, text) {
  var shape = Api.CreateShape("textRect", 5486400, 914400);
  var content = shape.GetContent ? shape.GetContent() : (shape.GetDocContent ? shape.GetDocContent() : null);
  var para = content && content.GetElement ? content.GetElement(0) : null;
  if (!para) { para = Api.CreateParagraph(); if (content && content.Push) content.Push(para); }
  if (para && para.AddText) para.AddText(text);
  return { shape: shape, para: para };
}
""".strip()


def _js_align(align: str | None) -> str | None:
    if not align:
        return None
    return "both" if align == "justify" else align


def _emit_align(paragraph_var: str, align: str | None) -> list[str]:
    jc = _js_align(align)
    if not jc or jc == "left":
        return []
    return [f"{paragraph_var}.SetJc('{jc}');"]


def _emit_run_style(run_var: str, *, bold: bool | None, font_name: str | None, font_size_pt: float | None) -> list[str]:
    lines: list[str] = []
    if bold:
        lines.append(f"if ({run_var} && {run_var}.SetBold) {run_var}.SetBold(true);")
    elif bold is False:
        lines.append(f"if ({run_var} && {run_var}.SetBold) {run_var}.SetBold(false);")
    if font_name:
        lines.append(f'if ({run_var} && {run_var}.SetFontFamily) {run_var}.SetFontFamily("{escape_js(font_name)}");')
    if font_size_pt is not None:
        lines.append(f"if ({run_var} && {run_var}.SetFontSize) {run_var}.SetFontSize({float(font_size_pt)});")
    return lines


def _emit_paragraph_block(block: BlockSpec) -> list[str]:
    lines = [
        f'var added = _officePdfAddText(page, "{escape_js(block.text or "")}");',
        "var oPara = added.para;",
        "var oRun = Api.CreateRun();",
    ]
    lines.extend(_emit_align("oPara", block.align))
    lines.append(f'oRun.AddText("{escape_js(block.text or "")}");')
    lines.extend(
        _emit_run_style(
            "oRun",
            bold=True if block.bold else None,
            font_name=block.font_name,
            font_size_pt=block.font_size_pt,
        )
    )
    lines.append("if (oPara && oPara.AddElement) { oPara.AddElement(oRun); }")
    lines.append("_officePdfPush(page, added.shape);")
    lines.extend(
        [
            f'var blockAnnot = Api.CreateFreeTextAnnot([20, 80, 400, 120]);',
            f'blockAnnot.SetContents("{escape_js(block.text or "")}");',
            "page.AddObject(blockAnnot);",
        ]
    )
    return lines


def _emit_block_on_page(block: BlockSpec) -> list[str]:
    if block.type == "table" and block.rows:
        cols = max((len(r) for r in block.rows), default=1)
        lines = [f"var oTable = Api.CreateTable({cols}, {len(block.rows)});"]
        for ri, row in enumerate(block.rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'oTable.GetCell({ri}, {ci}).GetContent().GetElement(0).AddText("{escape_js(str(cell))}");'
                )
        lines.append("_officePdfPush(page, oTable);")
        payload = "\\n".join("\\t".join(escape_js(str(cell)) for cell in row) for row in block.rows)
        lines.extend(
            [
                "var tableAnnot = Api.CreateFreeTextAnnot([20, 140, 420, 200]);",
                f'tableAnnot.SetContents("<<<TABLE>>>{payload}");',
                "page.AddObject(tableAnnot);",
            ]
        )
        return lines
    return _emit_paragraph_block(block)


def _emit_add_paragraph(op: EditOperation) -> list[str]:
    lines = [
        f"var page = _officePdfPage(doc, {op.page_index});",
        f'var added = _officePdfAddText(page, "{escape_js(op.text or "")}");',
        "var oPara = added.para;",
        "var oRun = Api.CreateRun();",
    ]
    lines.extend(_emit_align("oPara", op.align))
    lines.append(f'oRun.AddText("{escape_js(op.text or "")}");')
    lines.extend(
        _emit_run_style(
            "oRun",
            bold=op.bold,
            font_name=op.font_name,
            font_size_pt=op.font_size_pt,
        )
    )
    lines.append("if (oPara && oPara.AddElement) { oPara.AddElement(oRun); }")
    lines.append("_officePdfPush(page, added.shape);")
    lines.extend(
        [
            f'var paraAnnot = Api.CreateFreeTextAnnot([20, 40, 400, 80]);',
            f'paraAnnot.SetContents("{escape_js(op.text or "")}");',
            "page.AddObject(paraAnnot);",
        ]
    )
    return lines


def _emit_add_page(op: EditOperation) -> list[str]:
    after = op.after_index if op.after_index is not None else -1
    if after < 0:
        insert_at = "_officePdfPageCount(doc)"
    else:
        insert_at = str(after + 1)
    lines = [
        f"var insertAt = {insert_at};",
        "var page = doc.AddPage(insertAt);",
        "if (!page) { page = _officePdfPage(doc, insertAt); }",
    ]
    for block in op.blocks or []:
        lines.extend(_emit_block_on_page(block))
    return lines


def _emit_set_block_text(op: EditOperation) -> list[str]:
    lines = [
        f"var page = _officePdfPage(doc, {op.page_index});",
        f"var blockEl = _officePdfBlock(page, {op.block_index});",
        "if (blockEl) {",
    ]
    if op.rows:
        for ri, row in enumerate(op.rows):
            for ci, cell in enumerate(row):
                lines.append(
                    f'  var cell_{ri}_{ci} = blockEl.GetCell({ri}, {ci});'
                )
                lines.append(
                    f'  if (cell_{ri}_{ci} && cell_{ri}_{ci}.GetContent) {{'
                )
                lines.append(
                    f'    var cellPara_{ri}_{ci} = cell_{ri}_{ci}.GetContent().GetElement(0);'
                )
                lines.append(
                    f'    if (cellPara_{ri}_{ci}) {{ cellPara_{ri}_{ci}.SetText("{escape_js(str(cell))}"); }}'
                )
                lines.append("  }")
    else:
        lines.append(f'  _officePdfSetText(blockEl, "{escape_js(op.text or "")}");')
    lines.append("}")
    return lines


def _emit_set_cell_text(op: EditOperation) -> list[str]:
    return [
        f"var page = _officePdfPage(doc, {op.page_index});",
        f"var tableEl = _officePdfBlock(page, {op.block_index});",
        "if (tableEl && !(tableEl.GetCell || (tableEl.GetContents && String(tableEl.GetContents()).indexOf('<<<TABLE>>>') === 0))) { tableEl = null; }",
        "if (!tableEl && page && page.GetAllAnnots) {",
        "  var tableAnnots = page.GetAllAnnots() || [];",
        "  for (var ti = 0; ti < tableAnnots.length; ti++) {",
        "    if (String(tableAnnots[ti].GetContents() || '').indexOf('<<<TABLE>>>') === 0) { tableEl = tableAnnots[ti]; break; }",
        "  }",
        "}",
        "if (tableEl) {",
        f'  _officePdfSetCell(tableEl, {op.row}, {op.col}, "{escape_js(op.text or "")}");',
        "}",
    ]


def _emit_set_paragraph_format(op: EditOperation) -> list[str]:
    lines = [
        f"var page = _officePdfPage(doc, {op.page_index});",
        f"var formatEl = _officePdfBlock(page, {op.block_index});",
    ]
    if op.row is not None and op.col is not None:
        lines.extend(
            [
                f"if (formatEl && formatEl.GetCell) {{ formatEl = formatEl.GetCell({op.row}, {op.col}); }}",
                "if (formatEl && formatEl.GetContent) { formatEl = formatEl.GetContent().GetElement(0); }",
            ]
        )
    lines.append("if (formatEl) {")
    if op.align:
        jc = _js_align(op.align)
        lines.append(f"  if (formatEl.SetJc) {{ formatEl.SetJc('{jc}'); }}")
    if op.bold is not None or op.font_name or op.font_size_pt is not None:
        lines.append("  var formatRun = formatEl;")
        lines.append(
            "  try { if (formatEl.GetElement && formatEl.GetElementsCount && formatEl.GetElementsCount() > 0) { formatRun = formatEl.GetElement(0); } } catch (e) {}"
        )
        lines.extend(
            [
                f"  {line}"
                for line in _emit_run_style(
                    "formatRun",
                    bold=op.bold,
                    font_name=op.font_name,
                    font_size_pt=op.font_size_pt,
                )
            ]
        )
    lines.append("}")
    return lines


def _image_src(op: EditOperation) -> str:
    if op.content_base64:
        return f"data:image/png;base64,{op.content_base64}"
    return op.url or ""


def _emit_replace_image(op: EditOperation) -> list[str]:
    src = escape_js(_image_src(op))
    image_index = 0 if op.image_index is None else op.image_index
    lines = [
        f"var page = _officePdfPage(doc, {op.page_index});",
        "var target = null;",
        "var posX = 0;",
        "var posY = 0;",
        "var imgW = 200;",
        "var imgH = 150;",
    ]
    if op.block_index is not None:
        lines.append(
            f"if (page && page.GetElement) {{ target = page.GetElement({op.block_index}); }}"
        )
    lines.extend(
        [
            "if (!target && page && page.GetAllDrawings) {",
            "  var drawings = page.GetAllDrawings();",
            f"  if (drawings && drawings[{image_index}]) {{ target = drawings[{image_index}]; }}",
            "}",
            "if (target) {",
            "  if (target.GetPosX) { try { posX = target.GetPosX(); } catch (e) {} }",
            "  if (target.GetPosY) { try { posY = target.GetPosY(); } catch (e) {} }",
            "  if (target.GetWidth) { try { imgW = target.GetWidth(); } catch (e) {} }",
            "  if (target.GetHeight) { try { imgH = target.GetHeight(); } catch (e) {} }",
            "  if (target.Delete) { target.Delete(); }",
            "}",
            f'var oImage = Api.CreateImage("{src}", imgW, imgH);',
            "if (oImage.SetPosition) { oImage.SetPosition(posX, posY); }",
            "_officePdfPush(page, oImage);",
        ]
    )
    return lines


def _emit_set_bookmark(op: EditOperation) -> list[str]:
    bookmark_id = escape_js(op.bookmark_id or "")
    lines = [
        f'var bookmarkId = "{bookmark_id}";',
        "var bookmark = null;",
        "if (doc.GetBookmark) { try { bookmark = doc.GetBookmark(bookmarkId); } catch (e) { bookmark = null; } }",
    ]
    if op.text is not None:
        lines.append(
            f'if (bookmark && bookmark.SetText) {{ bookmark.SetText("{escape_js(op.text)}"); }}'
        )
    if op.page_index is not None and op.block_index is not None:
        lines.extend(
            [
                "if (!bookmark) {",
                f"  var page = _officePdfPage(doc, {op.page_index});",
                f"  var para = page && page.GetElement ? page.GetElement({op.block_index}) : null;",
                "  var range = null;",
                "  if (para && para.GetRange) { try { range = para.GetRange(); } catch (e) {} }",
                "  if (range && range.AddBookmark) { range.AddBookmark(bookmarkId); }",
                "  else if (para && para.AddBookmark) { para.AddBookmark(bookmarkId); }",
                "  else if (doc.GetRange && para && para.GetText) {",
                "    try { range = doc.GetRange(0, String(para.GetText()).length); if (range && range.AddBookmark) { range.AddBookmark(bookmarkId); } } catch (e) {}",
                "  }",
                "}",
            ]
        )
    return lines


def _emit_delete_bookmark(op: EditOperation) -> list[str]:
    bookmark_id = escape_js(op.bookmark_id or "")
    return [
        f'var bookmarkId = "{bookmark_id}";',
        "if (doc.DeleteBookmark) { doc.DeleteBookmark(bookmarkId); }",
        "else if (doc.GetBookmark) {",
        "  var bookmark = null;",
        "  try { bookmark = doc.GetBookmark(bookmarkId); } catch (e) { bookmark = null; }",
        "  if (bookmark && bookmark.Delete) { bookmark.Delete(); }",
        "}",
    ]


def _emit_set_annotation(op: EditOperation) -> list[str]:
    lines = [
        f"var page = _officePdfPage(doc, {op.page_index});",
        "var annots = page && page.GetAllAnnots ? page.GetAllAnnots() : [];",
        f"var annot = annots && annots[{op.annotation_index}] ? annots[{op.annotation_index}] : null;",
        "if (annot) {",
    ]
    if op.text is not None:
        lines.append(f'  if (annot.SetContents) {{ annot.SetContents("{escape_js(op.text)}"); }}')
    if op.rect:
        rect = op.rect
        x = rect.get("x", 0)
        y = rect.get("y", 0)
        width = rect.get("width", 100)
        height = rect.get("height", 20)
        lines.append(
            f"  if (annot.SetRect) {{ annot.SetRect([{x}, {y}, {x + width}, {y + height}]); }}"
        )
    if op.kind:
        lines.append(f'  if (annot.SetType) {{ annot.SetType("{escape_js(op.kind)}"); }}')
    lines.append("}")
    return lines


def _emit_operation(op: EditOperation) -> list[str]:
    if op.op == "add_paragraph":
        return _emit_add_paragraph(op)
    if op.op == "set_page_text":
        lines = [
            f"var page = _officePdfPage(doc, {op.page_index});",
            "while (page && page.GetElementsCount && page.GetElementsCount() > 0) { page.RemoveElement(0); }",
        ]
        for block in op.blocks or []:
            lines.extend(_emit_block_on_page(block))
        return lines
    if op.op == "add_page":
        return _emit_add_page(op)
    if op.op == "delete_page":
        return [f"if (doc.RemovePage) {{ doc.RemovePage({op.page_index}); }} else {{ doc.RemoveElement({op.page_index}); }}"]
    if op.op == "rotate_page":
        return [
            f"var page = _officePdfPage(doc, {op.page_index});",
            f"if (page.SetRotation) {{ page.SetRotation({op.degrees}); }} else {{ page.Rotate({op.degrees}); }}",
        ]
    if op.op == "add_annotation":
        rect = op.rect or {}
        x = rect.get("x", 0)
        y = rect.get("y", 0)
        w = rect.get("width", 100)
        h = rect.get("height", 20)
        return [
            f"var page = _officePdfPage(doc, {op.page_index});",
            f"var annot = Api.CreateFreeTextAnnot([{x}, {y}, {x + w}, {y + h}]);",
            f'annot.SetContents("{escape_js(op.text or "")}");',
            "page.AddObject(annot);",
        ]
    if op.op == "set_block_text":
        return _emit_set_block_text(op)
    if op.op == "set_cell_text":
        return _emit_set_cell_text(op)
    if op.op == "set_paragraph_format":
        return _emit_set_paragraph_format(op)
    if op.op == "replace_image":
        return _emit_replace_image(op)
    if op.op == "set_bookmark":
        return _emit_set_bookmark(op)
    if op.op == "delete_bookmark":
        return _emit_delete_bookmark(op)
    if op.op == "set_annotation":
        return _emit_set_annotation(op)
    return []


def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    lines = ["var doc = Api.GetDocument();", _PDF_EDIT_HELPERS]
    for op in operations:
        lines.append("try {")
        lines.extend(_emit_operation(op))
        lines.append("} catch (e) {}")
    return "\n".join(lines)
