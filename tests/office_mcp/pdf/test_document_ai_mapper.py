"""DocumentLayout mapper tests."""

from aiecs.tools.office_tool.pdf.parser.document_ai import layout_to_pages
from aiecs.tools.office_tool.core.projectors import structure_to_markdown


def test_layout_headings_tables_lists():
    document = {
        "documentLayout": {
            "blocks": [
                {
                    "pageSpan": {"pageStart": 1, "pageEnd": 1},
                    "textBlock": {"text": "Title", "type": "heading-1"},
                },
                {
                    "pageSpan": {"pageStart": 1, "pageEnd": 1},
                    "tableBlock": {
                        "bodyRows": [
                            {"cells": [{"blocks": [{"textBlock": {"text": "A"}}]}, {"blocks": [{"textBlock": {"text": "B"}}]}]}
                        ]
                    },
                },
                {
                    "pageSpan": {"pageStart": 2, "pageEnd": 2},
                    "listBlock": {"listEntries": [{"blocks": [{"textBlock": {"text": "item"}}]}]},
                },
            ]
        }
    }
    pages = layout_to_pages(document)
    assert len(pages) == 2
    assert pages[0]["blocks"][0]["type"] == "heading1"
    assert pages[0]["blocks"][1]["type"] == "table"
    assert pages[1]["blocks"][0]["type"] == "list"
    md = structure_to_markdown(pages)
    assert "# Title" in md
    assert "item" in md
