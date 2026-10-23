"""Fixtures for PDF structured Document AI mapping and oversize fallback."""

from unittest.mock import AsyncMock, patch

import pytest

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


def test_reading_order_attaches_orphan_punct_not_cjk_spaces():
    layout = {
        "documentLayout": {
            "blocks": [
                {"pageSpan": {"pageStart": 1}, "textBlock": {"type": "paragraph", "text": "经济制度"}},
                {"pageSpan": {"pageStart": 1}, "textBlock": {"type": "paragraph", "text": "。"}},
                {"pageSpan": {"pageStart": 1}, "textBlock": {"type": "paragraph", "text": "思想 政治"}},
                {"pageSpan": {"pageStart": 1}, "textBlock": {"type": "paragraph", "text": "创新"}},
                {"pageSpan": {"pageStart": 5}, "textBlock": {"type": "paragraph", "text": "重要 2、为什么支柱"}},
                {"pageSpan": {"pageStart": 5}, "textBlock": {"type": "paragraph", "text": "……统"}},
                {"pageSpan": {"pageStart": 5}, "textBlock": {"type": "paragraph", "text": "二者关系:一于……"}},
                {"pageSpan": {"pageStart": 8}, "textBlock": {"type": "paragraph", "text": "一条 发展现代农业。 龙服务"}},
                {"pageSpan": {"pageStart": 8}, "textBlock": {"type": "paragraph", "text": "develop-"}},
                {"pageSpan": {"pageStart": 8}, "textBlock": {"type": "paragraph", "text": "ment"}},
                {"pageSpan": {"pageStart": 9}, "textBlock": {"type": "paragraph", "text": "【"}},
            ]
        }
    }
    elements = layout_to_elements(layout)
    texts = [el["text"] for el in elements]
    assert "经济制度。" in texts
    assert "。" not in texts
    assert "思想 政治" in texts
    assert "创新" in texts
    assert any("2、为什么" in text for text in texts)
    assert "重要 2、为什么支柱" in texts
    assert "……统" in texts
    assert "二者关系:一于……" in texts
    assert "一条 发展现代农业。 龙服务" in texts
    assert "development" in texts
    assert "develop-" not in texts
    assert "【" not in texts


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


def _two_page_pdf() -> bytes:
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.add_blank_page(200, 200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


LONG = "This readable page has forty plus nonspace characters in one paragraph."
assert sum(1 for ch in LONG if not ch.isspace()) >= 40
SHORT = "tiny"


def _pdf_patches(sidecar, data, dai=None):
    dai = dai or AsyncMock()
    return (
        patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=("https://signed/doc.pdf", "pdf", "gs://b/doc.pdf", "gs://"),
        ),
        patch(
            "aiecs.tools.office_tool.core.document_read._source_size",
            new_callable=AsyncMock,
            return_value=len(data),
        ),
        patch(
            "aiecs.tools.office_tool.core.document_read._load_bytes",
            new_callable=AsyncMock,
            return_value=data,
        ),
        patch(
            "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
            new_callable=AsyncMock,
            return_value=(sidecar, None),
        ),
        patch(
            "aiecs.tools.office_tool.core.structured_read.get_documentai_client",
            return_value=dai,
        ),
        patch(
            "aiecs.tools.office_tool.core.structured_read.process_pdf_batch",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.asyncio
async def test_readable_pdf_page_stays_on_documentserver():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": LONG}]}]}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock()
    data = _two_page_pdf()
    patches = _pdf_patches(sidecar, data, dai)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as batch:
        result = await office_read_document(source_path="gs://b/doc.pdf", format="markdown")
    assert not result.get("isError"), result.get("text")
    assert LONG in result["markdown"]
    assert "[Page 1]" in result["markdown"]
    dai.process_pdf_online.assert_not_called()
    batch.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_pdf_splits_short_page_to_document_ai():
    sidecar = {"pages": [
        {"page_index": 0, "blocks": [{"type": "paragraph", "text": SHORT}]},
        {"page_index": 1, "blocks": [{"type": "paragraph", "text": LONG}]},
    ]}
    layout = {"documentLayout": {"blocks": [{
        "pageSpan": {"pageStart": 1},
        "textBlock": {"type": "paragraph", "text": "ocr short page"},
    }]}}
    dai = AsyncMock()
    dai.process_pdf_online = AsyncMock(return_value=layout)
    data = _two_page_pdf()
    cfg = patch("aiecs.config.get_documentai_config")
    patches = _pdf_patches(sidecar, data, dai)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as batch, cfg as dai_cfg:
        dai_cfg.return_value.is_configured.return_value = True
        result = await office_read_document(source_path="gs://b/doc.pdf", format="markdown")
    assert not result.get("isError"), result.get("text")
    assert dai.process_pdf_online.await_count == 1
    sent = dai.process_pdf_online.await_args.kwargs["raw_bytes"]
    from pypdf import PdfReader
    assert len(PdfReader(io_bytes(sent)).pages) == 1
    assert sent != data
    batch.assert_not_called()
    assert "[Page 1]" in result["markdown"]
    assert "ocr short page" in result["markdown"]
    assert LONG in result["markdown"]
    assert "[Page 2]" in result["markdown"]


def io_bytes(data: bytes):
    from io import BytesIO
    return BytesIO(data)


@pytest.mark.asyncio
async def test_short_page_without_dai_is_error():
    sidecar = {"pages": [{"page_index": 0, "blocks": [{"type": "paragraph", "text": SHORT}]}]}
    data = _two_page_pdf()
    dai = AsyncMock()
    cfg = patch("aiecs.config.get_documentai_config")
    patches = _pdf_patches(sidecar, data, dai)
    with patches[0], patches[1], patches[2], patches[3], patches[4], cfg as dai_cfg:
        dai_cfg.return_value.is_configured.return_value = False
        result = await office_read_document(source_path="gs://b/doc.pdf", format="markdown")
    assert result.get("isError") is True
    assert "DOCUMENT_AI_PROJECT" in result["text"]
    assert "office_parse_document" not in result["text"]


@pytest.mark.asyncio
async def test_djvu_and_xps_still_use_conversion():
    mock_txt = "legacy page"
    for ext in ("djvu", "xps", "oxps"):
        with patch(
            "aiecs.tools.office_tool.core.document_read.resolve_document_source",
            new_callable=AsyncMock,
            return_value=(f"https://signed/doc.{ext}", ext, f"gs://b/doc.{ext}", "gs://"),
        ), patch(
            "aiecs.tools.office_tool.core.document_read.convert_and_fetch",
            new_callable=AsyncMock,
            return_value=(mock_txt, None),
        ) as convert:
            result = await office_read_document(source_path=f"gs://b/doc.{ext}", format="markdown")
        assert result.get("isError") is not True
        assert result["conversion_output_type"] == "txt"
        convert.assert_awaited_once()
