"""Builder helpers for slide notes pages."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js


def emit_notes_text(slide_var: str, text: str) -> list[str]:
    """Set notes text; add a textbox when the notes page has no shapes."""
    escaped = escape_js(text)
    return [
        f"var notesPage = {slide_var}.GetNotesPage();",
        "var notesShapes = notesPage.GetAllShapes();",
        "if (notesShapes.length > 0) {",
        f'  notesShapes[0].SetText("{escaped}");',
        "} else {",
        f'  var notesTb = notesPage.AddTextbox(); notesTb.SetText("{escaped}");',
        "}",
    ]
