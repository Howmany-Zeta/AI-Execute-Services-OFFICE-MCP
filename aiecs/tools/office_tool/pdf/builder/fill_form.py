"""Builder script generation for office_fill_pdf_form (ADR-019)."""

from __future__ import annotations

import json
from typing import Any


def build_fill_form_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    Edit body: OpenFile injected by run_builder_on_source.
    SetValue per field — no SetFormsData batch API.
    """
    data_json = json.dumps({str(k): str(v) for k, v in data.items()})
    return "\n".join(
        [
            "var doc = Api.GetDocument();",
            f"var formData = {data_json};",
            "for (var k in formData) {",
            "  var f = doc.GetFormFieldByName(k);",
            "  if (f) { f.SetValue(formData[k]); }",
            "}",
        ]
    )
