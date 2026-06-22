"""Parse ONLYOFFICE PDF sidecar JSON into pages[] / blocks[]."""

from __future__ import annotations

import json
from typing import Any


PDF_PAGE_EXTRACT_BODY = """var doc = Api.GetDocument();
var out = { pages: [] };
for (var i = 0; i < doc.GetElementsCount(); i++) {
  var page = doc.GetElement(i);
  var blocks = [];
  var elCount = page.GetElementsCount ? page.GetElementsCount() : 0;
  for (var j = 0; j < elCount; j++) {
    var el = page.GetElement(j);
    var txt = el.GetText ? el.GetText() : "";
    blocks.push({ block_index: j, type: "paragraph", text: txt });
  }
  var formFields = [];
  if (doc.GetAllForms && doc.GetAllForms()) {
    var forms = doc.GetAllForms();
    for (var f = 0; f < forms.length; f++) {
      formFields.push({ name: forms[f].GetName(), type: "text", value: forms[f].GetValue() });
    }
  }
  out.pages.push({ page_index: i, blocks: blocks, form_fields: formFields });
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
    text = " ".join(parts)
    return len(re.findall(r"\S+", text)) if text else 0
