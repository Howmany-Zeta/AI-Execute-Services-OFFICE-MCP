"""Builder script generation for office_fill_pdf_form (ADR-019)."""

from __future__ import annotations

import json
from typing import Any

from aiecs.tools.office_tool.core.builder_js import escape_js

_PDF_PAGE_HELPER = """
function _officePdfPage(doc, i) {
  if (doc.GetPage) {
    try { var p = doc.GetPage(i); if (p) return p; } catch (e) {}
  }
  return doc.GetElement ? doc.GetElement(i) : null;
}
""".strip()


def build_fill_form_script(
    data: dict[str, Any],
    *,
    file_ext: str,
    fields: list | None = None,
) -> str:
    """
    Edit body: OpenFile injected by run_builder_on_source.
    SetValue per field — no SetFormsData batch API.
    """
    data_json = json.dumps({str(k): v for k, v in data.items()})
    lines = [
        "var doc = Api.GetDocument();",
        _PDF_PAGE_HELPER,
        f"var formData = {data_json};",
        "for (var k in formData) {",
        "  var f = doc.GetFormFieldByName(k);",
        "  if (f) { f.SetValue(formData[k]); }",
        "}",
    ]
    for field in fields or []:
        name = escape_js(getattr(field, "name", ""))
        page_index = int(getattr(field, "page_index", 0))
        value_json = json.dumps(getattr(field, "value", ""))
        lines.extend(
            [
                f"var page = _officePdfPage(doc, {page_index});",
                "if (page && page.GetAllWidgets) {",
                "  var widgets = page.GetAllWidgets();",
                "  if (widgets) {",
                "    for (var w = 0; w < widgets.length; w++) {",
                "      var widget = widgets[w];",
                f'      if ((widget.GetName ? widget.GetName() : "") === "{name}") {{',
                f"        widget.SetValue({value_json});",
                "        break;",
                "      }",
                "    }",
                "  }",
                "}",
            ]
        )
    return "\n".join(lines)
