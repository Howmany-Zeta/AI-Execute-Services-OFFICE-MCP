"""Builder helpers for slide notes pages."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js


def emit_notes_text(slide_var: str, text: str) -> list[str]:
    """Set notes once: body shape if a notes page exists, else AddNotesText."""
    escaped = escape_js(text)
    return [
        f"var notesPage = {slide_var}.GetNotesPage();",
        "if (!notesPage && " + slide_var + ".AddNotesText) {",
        f'  {slide_var}.AddNotesText("{escaped}");',
        f"  notesPage = {slide_var}.GetNotesPage();",
        "}",
        f'if (notesPage && notesPage.AddBodyShapeText) {{ notesPage.AddBodyShapeText("{escaped}"); }}',
        f'else if (notesPage && notesPage.GetBodyShape) {{ var notesBody = notesPage.GetBodyShape(); _officeSetShapeText(notesBody, "{escaped}"); }}',
        f'else if ({slide_var}.AddNotesText) {{ {slide_var}.AddNotesText("{escaped}"); }}',
    ]
