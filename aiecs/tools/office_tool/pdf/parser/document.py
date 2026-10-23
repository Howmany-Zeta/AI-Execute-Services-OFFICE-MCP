"""Parse ONLYOFFICE PDF sidecar JSON into pages[] / blocks[]."""

from __future__ import annotations

import json
from typing import Any


PDF_PAGE_EXTRACT_BODY = r"""var doc = Api.GetDocument();
function _pdfPageCount(d) {
  if (d.GetPagesCount) {
    try { var n = d.GetPagesCount(); if (typeof n === "number" && n > 0) return n; } catch (e) {}
  }
  return d.GetElementsCount ? d.GetElementsCount() : 0;
}
function _pdfPage(d, i) {
  if (d.GetPage) {
    try { var p = d.GetPage(i); if (p) return p; } catch (e) {}
  }
  return d.GetElement ? d.GetElement(i) : null;
}
function _pdfStr(v) { return v === undefined || v === null ? "" : String(v); }
function _pdfToPt(v) {
  if (typeof v !== "number") return null;
  return Math.abs(v) > 1000 ? v / 12700 : v;
}
function _pdfAlign(el) {
  if (!el || !el.GetJc) return "";
  var jc = el.GetJc();
  if (jc === "both" || jc === "justify") return "justify";
  if (jc === "left" || jc === "center" || jc === "right") return jc;
  return "";
}
function _pdfParaStyle(el) {
  var style = {};
  var align = _pdfAlign(el);
  if (align) style.align = align;
  var run = null;
  try {
    if (el && el.GetElement && el.GetElementsCount && el.GetElementsCount() > 0) run = el.GetElement(0);
  } catch (e) { run = null; }
  var boldSrc = (run && run.GetBold) ? run : el;
  if (boldSrc && boldSrc.GetBold) {
    try { var b = boldSrc.GetBold(); if (b !== undefined && b !== null) style.bold = !!b; } catch (e) {}
  }
  var fontSrc = (run && run.GetFontFamily) ? run : el;
  if (fontSrc && fontSrc.GetFontFamily) {
    try { var fn = fontSrc.GetFontFamily(); if (fn) style.font_name = _pdfStr(fn); } catch (e) {}
  }
  var sizeSrc = (run && run.GetFontSize) ? run : el;
  if (sizeSrc && sizeSrc.GetFontSize) {
    try { var sz = sizeSrc.GetFontSize(); if (typeof sz === "number") style.font_size_pt = sz; } catch (e) {}
  }
  return style;
}
function _pdfApplyStyle(target, style) {
  if (style.align) target.align = style.align;
  if (style.bold !== undefined) target.bold = style.bold;
  if (style.font_name) target.font_name = style.font_name;
  if (style.font_size_pt !== undefined) target.font_size_pt = style.font_size_pt;
}
function _pdfCellText(cell) {
  if (!cell || !cell.GetContent) return { text: "", para: null };
  var content = cell.GetContent();
  if (content && content.GetText) return { text: _pdfStr(content.GetText()), para: content.GetElement ? content.GetElement(0) : null };
  if (content && content.GetElement) {
    var cellEl = content.GetElement(0);
    if (cellEl && cellEl.GetText) return { text: _pdfStr(cellEl.GetText()), para: cellEl };
  }
  return { text: "", para: null };
}
function _pdfImageInfo(el, index) {
  var alt = "";
  if (el.GetDescription) { try { alt = _pdfStr(el.GetDescription()); } catch (e) {} }
  if (!alt && el.GetTitle) { try { alt = _pdfStr(el.GetTitle()); } catch (e) {} }
  if (!alt && el.GetName) { try { alt = _pdfStr(el.GetName()); } catch (e) {} }
  var info = { image_index: index, alt: alt };
  var w = null;
  var h = null;
  if (el.GetWidth) { try { w = _pdfToPt(el.GetWidth()); } catch (e) {} }
  if (el.GetHeight) { try { h = _pdfToPt(el.GetHeight()); } catch (e) {} }
  if (w !== null) info.width_pt = w;
  if (h !== null) info.height_pt = h;
  return info;
}
function _pdfAnnotRect(annot) {
  var r = null;
  if (annot.GetRect) { try { r = annot.GetRect(); } catch (e) {} }
  if (!r) return null;
  if (Object.prototype.toString.call(r) === "[object Array]") {
    var x1 = r[0] || 0, y1 = r[1] || 0, x2 = r[2] || 0, y2 = r[3] || 0;
    return { x: x1, y: y1, width: Math.abs(x2 - x1), height: Math.abs(y2 - y1) };
  }
  if (r.width !== undefined || r.height !== undefined) {
    return { x: r.x || 0, y: r.y || 0, width: r.width || 0, height: r.height || 0 };
  }
  var rx1 = r.x1 !== undefined ? r.x1 : (r.x || 0);
  var ry1 = r.y1 !== undefined ? r.y1 : (r.y || 0);
  var rx2 = r.x2 !== undefined ? r.x2 : rx1;
  var ry2 = r.y2 !== undefined ? r.y2 : ry1;
  return { x: rx1, y: ry1, width: Math.abs(rx2 - rx1), height: Math.abs(ry2 - ry1) };
}
function _pdfDegrees(page) {
  var deg = 0;
  if (page.GetRotation) {
    try { deg = page.GetRotation(); } catch (e) { deg = 0; }
  } else if (page.GetRotate) {
    try { deg = page.GetRotate(); } catch (e) { deg = 0; }
  }
  if (typeof deg !== "number") deg = 0;
  deg = ((Math.round(deg / 90) * 90) % 360 + 360) % 360;
  return deg;
}
var out = { pages: [], bookmarks: [], widgets_api_available: false };
var pageCount = _pdfPageCount(doc);
if (pageCount > 0) {
  var probePage = _pdfPage(doc, 0);
  out.widgets_api_available = !!(probePage && probePage.GetAllWidgets);
}
if (doc.GetAllBookmarksNames) {
  try {
    var names = doc.GetAllBookmarksNames();
    if (names) {
      for (var b = 0; b < names.length; b++) {
        var name = _pdfStr(names[b]);
        var text = "";
        if (doc.GetBookmark) {
          try {
            var bm = doc.GetBookmark(name);
            if (bm && bm.GetText) text = _pdfStr(bm.GetText());
          } catch (e) {}
        }
        out.bookmarks.push({ bookmark_id: name, name: name, text: text });
      }
    }
  } catch (e) {}
}
for (var i = 0; i < pageCount; i++) {
  var page = _pdfPage(doc, i);
  var blocks = [];
  var elCount = 0;
  try { elCount = (page && page.GetElementsCount) ? page.GetElementsCount() : 0; } catch (e) { elCount = 0; }
  for (var j = 0; j < elCount; j++) {
    var el = null;
    try { el = page.GetElement(j); } catch (e) { continue; }
    var cls = el && el.GetClassType ? el.GetClassType() : "";
    var lcls = _pdfStr(cls).toLowerCase();
    if (cls === "table" && el.GetRowsCount && el.GetRow) {
      var rows = [];
      var cells = [];
      var rowCount = el.GetRowsCount();
      for (var ri = 0; ri < rowCount; ri++) {
        var row = el.GetRow(ri);
        var rowCells = [];
        var cellCount = row.GetCellsCount ? row.GetCellsCount() : 0;
        for (var ci = 0; ci < cellCount; ci++) {
          var extracted = _pdfCellText(row.GetCell(ci));
          rowCells.push(extracted.text);
          var cellOut = { row: ri, col: ci, text: extracted.text };
          if (extracted.para) _pdfApplyStyle(cellOut, _pdfParaStyle(extracted.para));
          cells.push(cellOut);
        }
        rows.push(rowCells);
      }
      var tableBlock = { block_index: j, type: "table", rows: rows, cells: cells };
      blocks.push(tableBlock);
    } else if (lcls === "image" || lcls.indexOf("image") >= 0) {
      var imageBlock = _pdfImageInfo(el, 0);
      imageBlock.block_index = j;
      imageBlock.type = "image";
      blocks.push(imageBlock);
    } else {
      var txt = el && el.GetText ? el.GetText() : "";
      var paraBlock = { block_index: j, type: "paragraph", text: _pdfStr(txt) };
      _pdfApplyStyle(paraBlock, _pdfParaStyle(el));
      blocks.push(paraBlock);
    }
  }
  if (!blocks.length && page && page.GetText) {
    try {
      var pageText = page.GetText();
      if (pageText) blocks.push({ block_index: 0, type: "paragraph", text: _pdfStr(pageText) });
    } catch (e) {}
  }
  var formFields = [];
  if (page && page.GetAllWidgets) {
    var widgets = null;
    try { widgets = page.GetAllWidgets(); } catch (e) { widgets = null; }
    if (widgets) {
      for (var w = 0; w < widgets.length; w++) {
        var widget = widgets[w];
        formFields.push({
          page_index: i,
          name: widget.GetName ? widget.GetName() : "",
          type: widget.GetClassType ? widget.GetClassType() : "text",
          value: widget.GetValue ? widget.GetValue() : ""
        });
      }
    }
  }
  var images = [];
  if (page && page.GetAllDrawings) {
    try {
      var drawings = page.GetAllDrawings();
      if (drawings) {
        for (var d = 0; d < drawings.length; d++) {
          var drawing = drawings[d];
          var dTxt = "";
          try {
            if (drawing.GetText) dTxt = _pdfStr(drawing.GetText());
            if (!dTxt) {
              var dContent = drawing.GetContent ? drawing.GetContent() : (drawing.GetDocContent ? drawing.GetDocContent() : null);
              if (dContent && dContent.GetText) dTxt = _pdfStr(dContent.GetText());
              else if (dContent && dContent.GetElement) {
                var dEl = dContent.GetElement(0);
                if (dEl && dEl.GetText) dTxt = _pdfStr(dEl.GetText());
              }
            }
          } catch (e) { dTxt = ""; }
          if (drawing.GetRowsCount && drawing.GetRow) {
            var dRows = [];
            var dCells = [];
            var dRowCount = drawing.GetRowsCount();
            for (var dri = 0; dri < dRowCount; dri++) {
              var dRow = drawing.GetRow(dri);
              var dRowCells = [];
              var dCellCount = dRow.GetCellsCount ? dRow.GetCellsCount() : 0;
              for (var dci = 0; dci < dCellCount; dci++) {
                var dExtracted = _pdfCellText(dRow.GetCell(dci));
                dRowCells.push(dExtracted.text);
                dCells.push({ row: dri, col: dci, text: dExtracted.text });
              }
              dRows.push(dRowCells);
            }
            blocks.push({ block_index: blocks.length, type: "table", rows: dRows, cells: dCells });
          } else if (dTxt) {
            var dBlock = { block_index: blocks.length, type: "paragraph", text: dTxt };
            _pdfApplyStyle(dBlock, _pdfParaStyle(drawing));
            blocks.push(dBlock);
          } else {
            images.push(_pdfImageInfo(drawing, images.length));
          }
        }
      }
    } catch (e) {}
  }
  var pageOut = { page_index: i, degrees: _pdfDegrees(page), blocks: blocks };
  if (typeof drawings !== "undefined" && drawings) pageOut.drawing_count = drawings.length;
  if (formFields.length) pageOut.form_fields = formFields;
  if (images.length) pageOut.images = images;
  var annotations = [];
  if (page && page.GetAllAnnots) {
    try {
      var annots = page.GetAllAnnots();
      if (annots) {
        for (var a = 0; a < annots.length; a++) {
          var annot = annots[a];
          var annotOut = {
            annotation_index: a,
            kind: annot.GetClassType ? annot.GetClassType() : "unknown",
            text: annot.GetContents ? annot.GetContents() : ""
          };
          var rect = _pdfAnnotRect(annot);
          if (rect) annotOut.rect = rect;
          annotations.push(annotOut);
        }
      }
    } catch (e) {}
  }
  if (annotations.length) pageOut.annotations = annotations;
  for (var ai = 0; ai < annotations.length; ai++) {
    var aText = _pdfStr(annotations[ai].text);
    if (aText.indexOf("<<<TABLE>>>") === 0) {
      var tableRows = [];
      var tableCells = [];
      var rawRows = aText.slice(11).split("\n");
      for (var tri = 0; tri < rawRows.length; tri++) {
        var rawCells = rawRows[tri].split("\t");
        tableRows.push(rawCells);
        for (var tci = 0; tci < rawCells.length; tci++) {
          tableCells.push({ row: tri, col: tci, text: rawCells[tci] });
        }
      }
      blocks.push({ block_index: blocks.length, type: "table", rows: tableRows, cells: tableCells });
    } else if (aText) {
      blocks.push({ block_index: blocks.length, type: "paragraph", text: aText });
    }
  }
  pageOut.blocks = blocks;
  out.pages.push(pageOut);
}
var jsonStr = JSON.stringify(out);"""


def pdf_page_extract_body(page_range: tuple[int, int] | None = None) -> str:
    """Sidecar extract; optional inclusive page_range limits the page walk."""
    loop = "for (var i = 0; i < pageCount; i++) {"
    if page_range:
        start, end = (int(page_range[0]), int(page_range[1]))
        loop = f"for (var i = {start}; i < pageCount && i <= {end}; i++) {{"
    return PDF_PAGE_EXTRACT_BODY.replace("for (var i = 0; i < pageCount; i++) {", loop, 1)


_ALIGN_MAP = {
    "left": "left",
    "center": "center",
    "right": "right",
    "justify": "justify",
    "both": "justify",
}

_FORM_TYPE_MAP = {
    "text": "text",
    "textfield": "text",
    "textbox": "text",
    "checkbox": "checkbox",
    "check": "checkbox",
    "radiobutton": "radiobutton",
    "radio": "radiobutton",
    "combobox": "combobox",
    "combo": "combobox",
    "listbox": "listbox",
    "list": "listbox",
    "button": "button",
    "signature": "signature",
    "sign": "signature",
}

_DEGREES = (0, 90, 180, 270)


def _as_dict(raw: dict | str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    return raw if isinstance(raw, dict) else {}


def _normalize_align(value: Any) -> str | None:
    if value is None:
        return None
    return _ALIGN_MAP.get(str(value).strip().lower())


def _normalize_degrees(value: Any) -> int:
    try:
        deg = int(round(float(value) / 90.0) * 90) % 360
    except (TypeError, ValueError):
        return 0
    return deg if deg in _DEGREES else 0


def _compact_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    for token in ("annotation", "annot", "field", "form", "_"):
        raw = raw.replace(token, "")
    return raw.replace("-", "")


def _normalize_form_type(value: Any) -> str:
    return _FORM_TYPE_MAP.get(_compact_type(value), "unknown")


def _normalize_annot_kind(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    compact = _compact_type(raw)
    if "highlight" in compact:
        return "highlight"
    if "freetext" in compact or compact in {"freetext", "freetext"}:
        return "freetext"
    return raw


def _normalize_rect(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict):
        if isinstance(raw, (list, tuple)) and len(raw) >= 4:
            x1, y1, x2, y2 = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
            return {"x": x1, "y": y1, "width": abs(x2 - x1), "height": abs(y2 - y1)}
        return None
    try:
        if "width" in raw or "height" in raw:
            return {
                "x": float(raw.get("x") or 0),
                "y": float(raw.get("y") or 0),
                "width": float(raw.get("width") or 0),
                "height": float(raw.get("height") or 0),
            }
        x1 = float(raw.get("x1", raw.get("x") or 0))
        y1 = float(raw.get("y1", raw.get("y") or 0))
        x2 = float(raw.get("x2", x1))
        y2 = float(raw.get("y2", y1))
        return {"x": x1, "y": y1, "width": abs(x2 - x1), "height": abs(y2 - y1)}
    except (TypeError, ValueError):
        return None


def _apply_style(target: dict[str, Any], raw: dict[str, Any]) -> None:
    align = _normalize_align(raw.get("align"))
    if align:
        target["align"] = align
    if raw.get("bold") is not None:
        target["bold"] = bool(raw["bold"])
    font_name = str(raw.get("font_name") or "").strip()
    if font_name:
        target["font_name"] = font_name
    if raw.get("font_size_pt") is not None:
        try:
            target["font_size_pt"] = float(raw["font_size_pt"])
        except (TypeError, ValueError):
            pass


def _cells_from_rows(rows: list[Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        cells_in_row = row if isinstance(row, (list, tuple)) else [row]
        for col_index, cell_raw in enumerate(cells_in_row):
            cells.append({"row": row_index, "col": col_index, "text": "" if cell_raw is None else str(cell_raw)})
    return cells


def _rows_from_cells(cells: list[dict[str, Any]]) -> list[list[str]]:
    if not cells:
        return []
    max_row = max(cell["row"] for cell in cells)
    max_col = max(cell["col"] for cell in cells)
    rows = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for cell in cells:
        rows[cell["row"]][cell["col"]] = cell.get("text") or ""
    return rows


def _normalize_cell(raw: dict[str, Any]) -> dict[str, Any] | None:
    try:
        row = int(raw["row"])
        col = int(raw["col"])
    except (KeyError, TypeError, ValueError):
        return None
    cell = {"row": row, "col": col, "text": "" if raw.get("text") is None else str(raw.get("text"))}
    _apply_style(cell, raw)
    return cell


def _normalize_block(raw: dict[str, Any], index: int) -> dict[str, Any]:
    block_type = str(raw.get("type") or "paragraph").strip().lower()
    block: dict[str, Any] = {
        "block_index": raw.get("block_index", index),
        "type": block_type,
    }
    if block_type == "table":
        cells: list[dict[str, Any]] = []
        for item in raw.get("cells") or []:
            if isinstance(item, dict):
                cell = _normalize_cell(item)
                if cell:
                    cells.append(cell)
        rows = raw.get("rows")
        if not cells and isinstance(rows, list):
            cells = _cells_from_rows(rows)
        if not isinstance(rows, list) and cells:
            rows = _rows_from_cells(cells)
        block["rows"] = rows if isinstance(rows, list) else []
        block["cells"] = cells
        return block
    if block_type == "image":
        block["alt"] = str(raw.get("alt") or "")
        block["text"] = block["alt"]
        for key in ("width_pt", "height_pt"):
            if raw.get(key) is not None:
                try:
                    block[key] = float(raw[key])
                except (TypeError, ValueError):
                    pass
        if raw.get("image_index") is not None:
            try:
                block["image_index"] = int(raw["image_index"])
            except (TypeError, ValueError):
                pass
        return block
    block["text"] = "" if raw.get("text") is None else str(raw.get("text"))
    _apply_style(block, raw)
    return block


def _normalize_form_field(raw: dict[str, Any], page_index: int) -> dict[str, Any]:
    field = {
        "page_index": raw.get("page_index", page_index),
        "name": str(raw.get("name") or ""),
        "type": _normalize_form_type(raw.get("type") or "text"),
        "value": raw.get("value") if raw.get("value") is not None else "",
    }
    try:
        field["page_index"] = int(field["page_index"])
    except (TypeError, ValueError):
        field["page_index"] = page_index
    return field


def _normalize_annotation(raw: dict[str, Any], index: int) -> dict[str, Any]:
    annot = {
        "annotation_index": raw.get("annotation_index", index),
        "kind": _normalize_annot_kind(raw.get("kind") or "unknown"),
        "text": "" if raw.get("text") is None else str(raw.get("text")),
    }
    try:
        annot["annotation_index"] = int(annot["annotation_index"])
    except (TypeError, ValueError):
        annot["annotation_index"] = index
    rect = _normalize_rect(raw.get("rect"))
    if rect:
        annot["rect"] = rect
    return annot


def _normalize_image(raw: dict[str, Any], index: int) -> dict[str, Any]:
    image = {
        "image_index": raw.get("image_index", index),
        "alt": str(raw.get("alt") or ""),
    }
    try:
        image["image_index"] = int(image["image_index"])
    except (TypeError, ValueError):
        image["image_index"] = index
    for key in ("width_pt", "height_pt"):
        if raw.get(key) is not None:
            try:
                image[key] = float(raw[key])
            except (TypeError, ValueError):
                pass
    return image


def _normalize_page(raw: dict[str, Any], index: int) -> dict[str, Any]:
    page_index = raw.get("page_index", index)
    try:
        page_index = int(page_index)
    except (TypeError, ValueError):
        page_index = index
    blocks_raw = raw.get("blocks") or []
    blocks = [_normalize_block(b, i) for i, b in enumerate(blocks_raw) if isinstance(b, dict)]
    page: dict[str, Any] = {
        "page_index": page_index,
        "degrees": _normalize_degrees(raw.get("degrees")),
        "blocks": blocks,
    }
    form_fields = [
        _normalize_form_field(item, page_index)
        for item in raw.get("form_fields") or []
        if isinstance(item, dict)
    ]
    if form_fields:
        page["form_fields"] = form_fields
    annotations = [
        _normalize_annotation(item, i)
        for i, item in enumerate(raw.get("annotations") or [])
        if isinstance(item, dict)
    ]
    if annotations:
        page["annotations"] = annotations
    images = [
        _normalize_image(item, i)
        for i, item in enumerate(raw.get("images") or [])
        if isinstance(item, dict)
    ]
    if images:
        page["images"] = images
    return page


def _normalize_bookmark(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("bookmark_id") or raw.get("name") or "").strip()
    if not name:
        return None
    return {
        "bookmark_id": name,
        "name": str(raw.get("name") or name),
        "text": "" if raw.get("text") is None else str(raw.get("text")),
    }


def sidecar_bookmarks(raw: dict | str | None) -> list[dict[str, Any]]:
    data = _as_dict(raw)
    bookmarks: list[dict[str, Any]] = []
    for item in data.get("bookmarks") or []:
        if isinstance(item, dict):
            bookmark = _normalize_bookmark(item)
            if bookmark:
                bookmarks.append(bookmark)
        elif isinstance(item, str) and item.strip():
            bookmarks.append({"bookmark_id": item, "name": item, "text": ""})
    return bookmarks


def parse_document_json(raw: dict | str) -> list[dict[str, Any]]:
    """Sidecar JSON { pages: [...] } → normalized pages[]."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    pages_raw = data.get("pages") if isinstance(data, dict) else data
    if not isinstance(pages_raw, list):
        return []

    return [_normalize_page(p, i) for i, p in enumerate(pages_raw) if isinstance(p, dict)]


def apply_page_range(
    pages: list[dict[str, Any]],
    page_range: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    if not page_range:
        return pages
    start, end = page_range
    return [p for p in pages if start <= p.get("page_index", 0) <= end]


def word_count_from_pages(pages: list[dict[str, Any]]) -> int:
    import re

    parts: list[str] = []
    for page in pages:
        for block in page.get("blocks") or []:
            if block.get("text"):
                parts.append(str(block["text"]))
            for row in block.get("rows") or []:
                parts.extend(str(cell) for cell in row if cell)
    text = " ".join(parts)
    return len(re.findall(r"\S+", text)) if text else 0
