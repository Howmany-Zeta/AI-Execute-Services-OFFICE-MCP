"""Fixtures for PDF structured Document AI mapping and oversize fallback."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.clients.documentai_client import (
    ONLINE_MAX_BYTES,
    ONLINE_MAX_PAGES,
    DocumentAIOnlineLimitError,
)
from aiecs.tools.office_tool.legacy.read_document import office_read_document
from aiecs.tools.office_tool.pdf.parser.structured import (
    builder_pages_to_elements,
    layout_to_elements,
)


NESTED_LAYOUT = {
    "documentLayout": {
        "blocks": [
            {
                "pageSpan": {"pageStart": 1, "pageEnd": 2},
                "textBlock": {
                    "type": "textBlock",
                    "text": "PARENT SHOULD NOT APPEAR",
                    "blocks": [
                        {
                            "pageSpan": {"pageStart": 1, "pageEnd": 1},
                            "textBlock": {"type": "heading-2", "text": "H2"},
                        },
                        {
                            "pageSpan": {"pageStart": 1, "pageEnd": 1},
                            "textBlock": {"type": "heading", "text": "H"},
                        },
                        {
                            "pageSpan": {"pageStart": 1, "pageEnd": 1},
                            "textBlock": {"type": "title", "text": "T"},
                        },
                        {
                            "pageSpan": {"pageStart": 1, "pageEnd": 1},
                            "textBlock": {"type": "subtitle", "text": "Sub"},
                        },
                        {
                            "pageSpan": {"pageStart": 1, "pageEnd": 1},
                            "textBlock": {"type": "header", "text": "Hdr"},
                        },
                        {
                            "pageSpan": {"pageStart": 2, "pageEnd": 2},
                            "textBlock": {"type": "footer", "text": "Ftr"},
                        },
                    ],
                },
            },
            {
                "pageSpan": {"pageStart": 2, "pageEnd": 2},
                "listBlock": {
                    "listEntries": [
                        {"blocks": [
                            {"textBlock": {"text": "one"}},
                            {"textBlock": {"text": "one-b"}},
                        ]},
                        {"blocks": [{"textBlock": {"text": "two"}}]},
                    ]
                },
            },
            {
                "pageSpan": {"pageStart": 3, "pageEnd": 4},
                "tableBlock": {
                    "caption": "Table cap",
                    "bodyRows": [
                        {"cells": [
                            {"blocks": [{"textBlock": {"text": "A"}}]},
                            {"blocks": [{"textBlock": {"text": "B"}}]},
                        ]}
                    ],
                },
            },
            {
                "pageSpan": {"pageStart": 4, "pageEnd": 4},
                "textBlock": {"type": "figure", "text": "", "annotations": {}},
            },
            {
                "pageSpan": {"pageStart": 4, "pageEnd": 4},
                "textBlock": {
                    "type": "figure",
                    "text": "",
                    "annotations": {"description": "A cat"},
                },
            },
            {
                "textBlock": {"type": "paragraph", "text": "no span"},
            },
        ]
    }
}


def test_layout_to_elements_rules():
    elements = layout_to_elements(NESTED_LAYOUT)
    assert all("pages" not in el and "page_index" not in el and "block_index" not in el for el in elements)
    texts = [el.get("text") for el in elements]
    assert "PARENT SHOULD NOT APPEAR" not in texts
    assert elements[0] == {"page": 1, "type": "heading", "level": 2, "text": "H2"}
    assert elements[1]["type"] == "heading" and elements[1]["level"] == 1
    assert elements[2]["type"] == "heading" and elements[2]["level"] == 1 and elements[2]["text"] == "T"
    assert elements[3] == {"page": 1, "type": "paragraph", "text": "Sub"}
    assert elements[4]["type"] == "header"
    assert elements[5]["type"] == "footer"
    lists = [el for el in elements if el["type"] == "list"]
    assert len(lists) == 2
    assert lists[0]["text"] == "one\none-b"
    assert "level" not in lists[0]
    tables = [el for el in elements if el["type"] == "table"]
    assert len(tables) == 1
    assert "text" not in tables[0]
    assert tables[0]["rows"] == [["A", "B"]]
    assert tables[0]["page"] == 3
    cap = [el for el in elements if el.get("text") == "Table cap"][0]
    assert cap["type"] == "paragraph"
    assert any(el.get("text") == "A cat" and el["type"] == "paragraph" for el in elements)
    assert sum(1 for el in elements if el.get("text") == "A cat") == 1
    no_span = [el for el in elements if el.get("text") == "no span"][0]
    assert no_span["page"] == 1


def test_builder_pages_fallback_is_flat_elements():
    pages = [
        {"page_index": 0, "blocks": [
            {"block_index": 0, "type": "paragraph", "text": "p0"},
            {"block_index": 1, "type": "table", "rows": [["x"]]},
        ]},
        {"page_index": 1, "blocks": [{"block_index": 0, "type": "paragraph", "text": "p1"}]},
    ]
    elements = builder_pages_to_elements(pages)
    assert elements == [
        {"page": 1, "type": "paragraph", "text": "p0"},
        {"page": 1, "type": "table", "rows": [["x"]]},
        {"page": 2, "type": "paragraph", "text": "p1"},
    ]
    assert all("page_index" not in el and "block_index" not in el for el in elements)


@pytest.mark.asyncio
async def test_pdf_structured_uses_document_ai_not_conversion():
    layout = {"documentLayout": {"blocks": [{
        "pageSpan": {"pageStart": 1, "pageEnd": 1},
        "textBlock": {"type": "heading-2", "text": "AI"},
    }]}}
    client = AsyncMock()
    client.process_pdf_online = AsyncMock(return_value=layout)
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 /Type /Page ",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=1,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=client,
    ), patch(
        "aiecs.config.get_documentai_config",
    ) as cfg, patch(
        "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch",
        new_callable=AsyncMock,
    ) as convert:
        cfg.return_value.is_configured.return_value = True
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result.get("isError") is not True
    assert result["elements"][0]["type"] == "heading"
    assert result["elements"][0]["level"] == 2
    assert "pages" not in result
    assert "slides" not in result
    assert result["conversion_output_type"] == "document_layout"
    convert.assert_not_called()
    client.process_pdf_online.assert_awaited_once()


@pytest.mark.asyncio
async def test_pdf_oversize_skips_document_ai_and_uses_builder_body():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": "fallback"}]}]}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock()
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=ONLINE_MAX_BYTES + 1,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.online_max_bytes",
        return_value=ONLINE_MAX_BYTES,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=dai,
    ):
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result.get("isError") is not True
    assert result["elements"] == [{"page": 1, "type": "paragraph", "text": "fallback"}]
    assert "pages" not in result
    assert result["conversion_output_type"] == "builder_json"
    dai.process_pdf_online.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_estimated_pages_over_limit_uses_fallback():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "table", "rows": [["z"]]}]}]}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock()
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 fake",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=ONLINE_MAX_PAGES + 1,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=dai,
    ):
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result["elements"][0]["type"] == "table"
    assert result["elements"][0]["page"] == 1
    dai.process_pdf_online.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_online_limit_uses_batch_structure():
    layout = {"documentLayout": {"blocks": [{
        "pageSpan": {"pageStart": 1, "pageEnd": 1},
        "textBlock": {"type": "paragraph", "text": "from-batch"},
    }]}}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("30 pages"))
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 /Type /Page ",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=47,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=dai,
    ), patch(
        "aiecs.config.get_documentai_config",
    ) as cfg, patch(
        "aiecs.tools.office_tool.core.structured_read.process_pdf_batch",
        new_callable=AsyncMock,
        return_value=layout,
    ) as batch, patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
    ) as sidecar:
        cfg.return_value.is_configured.return_value = True
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result.get("isError") is not True
    assert result["elements"][0]["text"] == "from-batch"
    assert result["conversion_output_type"] == "document_layout"
    assert result["document_ai_mode"] == "batch"
    assert batch.await_count == 1
    sidecar.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_online_limit_empty_batch_uses_builder():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": "builder-after-batch"}]}]}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("30 pages"))
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 fake",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=47,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=dai,
    ), patch(
        "aiecs.config.get_documentai_config",
    ) as cfg, patch(
        "aiecs.tools.office_tool.core.structured_read.process_pdf_batch",
        new_callable=AsyncMock,
        return_value={"documentLayout": {"blocks": []}},
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ):
        cfg.return_value.is_configured.return_value = True
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result["elements"][0]["text"] == "builder-after-batch"
    assert result["conversion_output_type"] == "builder_json"


@pytest.mark.asyncio
async def test_pdf_unknown_page_count_calls_online_then_limit_falls_back():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": "after-limit"}]}]}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("15 pages"))
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 fake",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=None,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
        return_value=dai,
    ), patch(
        "aiecs.config.get_documentai_config",
    ) as cfg, patch(
        "aiecs.tools.office_tool.core.structured_read.process_pdf_batch",
        new_callable=AsyncMock,
        side_effect=RuntimeError("batch unavailable"),
    ) as batch, patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ):
        cfg.return_value.is_configured.return_value = True
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert dai.process_pdf_online.await_count == 1
    assert batch.await_count == 1
    assert result["elements"][0]["text"] == "after-limit"


@pytest.mark.asyncio
async def test_pdf_unconfigured_is_error():
    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.stat_object_size",
        new_callable=AsyncMock,
        return_value=100,
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.download_object_bytes",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 fake",
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.estimate_pdf_pages",
        return_value=1,
    ), patch(
        "aiecs.config.get_documentai_config",
    ) as cfg:
        cfg.return_value.is_configured.return_value = False
        result = await office_read_document(source_path="gs://b/doc.pdf", format="structured")

    assert result.get("isError") is True
    assert "elements" not in result
    assert "slides" not in result


@pytest.mark.asyncio
async def test_djvu_and_xps_still_use_conversion():
    mock_txt = "legacy page"
    for ext in ("djvu", "xps", "oxps"):
        with patch(
            "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=(f"https://signed/doc.{ext}", ext, f"gs://b/doc.{ext}", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=(mock_txt, None),
        ) as convert:
            result = await office_read_document(source_path=f"gs://b/doc.{ext}", format="structured")
        assert result.get("isError") is not True
        assert result["conversion_output_type"] == "txt"
        convert.assert_awaited_once()
