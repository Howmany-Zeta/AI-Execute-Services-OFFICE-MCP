"""Parse ONLYOFFICE PDF sidecar JSON into pages[] / blocks[]."""

from __future__ import annotations

import json
from typing import Any


PDF_PAGE_EXTRACT_BODY = """var doc = Api.GetDocument();
var out = { pages: [], widgets_api_available: false };
if (doc.GetElementsCount() > 0) {
  var probePage = doc.GetElement(0);
  out.widgets_api_available = !!(probePage && probePage.GetAllWidgets);
}
for (var i = 0; i < doc.GetElementsCount(); i++) {
  var page = doc.GetElement(i);
  var blocks = [];
  var elCount = page.GetElementsCount ? page.GetElementsCount() : 0;
  for (var j = 0; j < elCount; j++) {
    var el = page.GetElement(j);
    var cls = el.GetClassType ? el.GetClassType() : "";
    if (cls === "table" && el.GetRowsCount && el.GetRow) {
      var rows = [];
      var rowCount = el.GetRowsCount();
      for (var ri = 0; ri < rowCount; ri++) {
        var row = el.GetRow(ri);
        var rowCells = [];
        var cellCount = row.GetCellsCount ? row.GetCellsCount() : 0;
        for (var ci = 0; ci < cellCount; ci++) {
          var cell = row.GetCell(ci);
          var cellText = "";
          if (cell && cell.GetContent) {
            var content = cell.GetContent();
            if (content && content.GetText) {
              cellText = content.GetText();
            } else if (content && content.GetElement) {
              var cellEl = content.GetElement(0);
              if (cellEl && cellEl.GetText) {
                cellText = cellEl.GetText();
              }
            }
          }
          rowCells.push(cellText);
        }
        rows.push(rowCells);
      }
      blocks.push({ block_index: j, type: "table", rows: rows });
    } else {
      var txt = el.GetText ? el.GetText() : "";
      blocks.push({ block_index: j, type: "paragraph", text: txt });
    }
  }
  var formFields = [];
  if (page.GetAllWidgets) {
    var widgets = page.GetAllWidgets();
    if (widgets) {
      for (var w = 0; w < widgets.length; w++) {
        var widget = widgets[w];
        formFields.push({
          name: widget.GetName ? widget.GetName() : "",
          type: widget.GetClassType ? widget.GetClassType() : "text",
          value: widget.GetValue ? widget.GetValue() : ""
        });
      }
    }
  }
  var pageOut = { page_index: i, blocks: blocks };
  if (formFields.length) {
    pageOut.form_fields = formFields;
  }
  var annotations = [];
  if (page.GetAllAnnots) {
    var annots = page.GetAllAnnots();
    if (annots) {
      for (var a = 0; a < annots.length; a++) {
        var annot = annots[a];
        annotations.push({
          kind: annot.GetClassType ? annot.GetClassType() : "unknown",
          text: annot.GetContents ? annot.GetContents() : ""
        });
      }
    }
  }
  if (annotations.length) {
    pageOut.annotations = annotations;
  }
  out.pages.push(pageOut);
}
var jsonStr = JSON.stringify(out);"""


def _normalize_page(raw: dict[str, Any], index: int) -> dict[str, Any]:
    blocks = raw.get("blocks") or []
    page: dict[str, Any] = {
        "page_index": raw.get("page_index", index),
        "blocks": blocks,
    }
    if raw.get("form_fields"):
        page["form_fields"] = raw["form_fields"]
    if raw.get("annotations"):
        page["annotations"] = raw["annotations"]
    return page


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
