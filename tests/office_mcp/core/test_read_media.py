"""Media extraction and delivery tests for office_read_document."""

import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from aiecs.config import OfficeReadConfig
from aiecs.tools.office_tool.core.read_media import (
    collect_package_media,
    media_filename,
    public_media,
    realize_media,
)


PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'


def _docx_with_parts(parts: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in parts.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _picture_docx(image_name: str, image_bytes: bytes, rel_type: str = "image") -> bytes:
    document = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main">
  <w:body><w:p><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p></w:body>
</w:document>"""
    if rel_type == "svg":
        document = document.replace("<a:blip r:embed=\"rId1\"/>", "<asvg:svgBlip r:embed=\"rId1\"/>")
    rels = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                Target="media/%s"/>
</Relationships>""" % image_name
    return _docx_with_parts({
        "word/document.xml": document.encode(),
        "word/_rels/document.xml.rels": rels.encode(),
        f"word/media/{image_name}": image_bytes,
    })


def _chart_docx() -> bytes:
    document = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body><w:p><w:r><w:drawing><c:chart r:id="rId1"/></w:drawing></w:r></w:p></w:body>
</w:document>"""
    rels = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
                Target="charts/chart1.xml"/>
</Relationships>"""
    chart = b'<?xml version="1.0"?><c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/>'
    return _docx_with_parts({
        "word/document.xml": document.encode(),
        "word/_rels/document.xml.rels": rels.encode(),
        "word/charts/chart1.xml": chart,
        "word/charts/_rels/chart1.xml.rels": b'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
    })


def test_media_filename_pattern():
    name = media_filename("ab12", PNG, "png", 1)
    assert name.startswith("doc_ab12_")
    assert name.endswith("_01.png")


@pytest.mark.asyncio
async def test_caller_bucket_requires_output_path():
    from aiecs.tools.office_tool.core.document_read import _parse_options

    result = _parse_options({"media_delivery": "caller_bucket"})
    assert result.get("isError") is True
    assert "media_output_path" in result.get("text", "")


@pytest.mark.asyncio
async def test_svg_icon_does_not_call_convert(monkeypatch):
    data = _picture_docx("icon.svg", SVG, rel_type="svg")
    candidates = collect_package_media(data, "docx")
    assert candidates
    assert candidates[0].ext == "svg"
    convert = AsyncMock(return_value=(PNG, None))
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch_bytes",
        convert,
    )
    cfg = OfficeReadConfig()
    items, _warnings = await realize_media(
        candidates, stable_id="ab12", cfg=cfg, delivery="fetch_token", media_output_path=None,
    )
    convert.assert_not_called()
    assert len(items) == 1
    assert items[0].data == SVG


@pytest.mark.asyncio
async def test_chart_convert_success_and_failure(monkeypatch):
    data = _chart_docx()
    candidates = collect_package_media(data, "docx")
    assert any(c.kind == "chart" and c.data is None for c in candidates)

    convert = AsyncMock(return_value=(PNG, None))
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch_bytes",
        convert,
    )
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.read_media.build_bytes_fetch_url",
        lambda *a, **k: "http://mcp/storage-objects/tok",
    )
    cfg = OfficeReadConfig()
    items, warnings = await realize_media(
        candidates, stable_id="ab12", cfg=cfg, delivery="fetch_token", media_output_path=None,
    )
    assert convert.await_count == 1
    assert items[0].data == PNG

    convert.reset_mock()
    convert.return_value = (None, "fail")
    items, warnings = await realize_media(
        candidates, stable_id="ab12", cfg=cfg, delivery="fetch_token", media_output_path=None,
    )
    assert items == []
    assert any("chart" in w for w in warnings)


@pytest.mark.asyncio
async def test_media_round_trip_fetch_token_and_zip(monkeypatch):
    from aiecs.main_mcp import get_storage_object
    from aiecs.tools.office_tool.core.document_read import read_document_markdown
    from aiecs.tools.office_tool.core.read_markdown import READ_NOTE

    package = _picture_docx("photo.png", PNG)
    sidecar = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [
                {"class": "paragraph", "text": "Hello", "page_breaks": 0},
                {"class": "image", "alt": "photo", "text": "photo"},
            ],
        }],
        "footnotes": [],
    }
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://office-mcp:5040")
    with patch(
        "aiecs.tools.office_tool.core.document_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed", "docx", "gs://b/doc.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.document_read._load_bytes",
        new_callable=AsyncMock,
        return_value=package,
    ), patch(
        "aiecs.tools.office_tool.core.document_read._source_size",
        new_callable=AsyncMock,
        return_value=len(package),
    ):
        result = await read_document_markdown(source_path="gs://b/doc.docx", format="markdown")
        zipped = await read_document_markdown(
            source_path="gs://b/doc.docx",
            format="markdown",
            options={"accept": "application/zip"},
        )

    assert result.get("success") is True
    assert READ_NOTE in result["_note"]
    assert "![photo](media/" in result["markdown"]
    media = result["media"][0]
    token = media["url"].rsplit("/", 1)[-1]
    request = Request({"type": "http", "method": "GET", "path": f"/storage-objects/{token}", "headers": []})
    response = await get_storage_object(token, request)
    assert response.body == PNG

    raw = __import__("base64").b64decode(zipped["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "document.md" in zf.namelist()
        member = next(n for n in zf.namelist() if n.startswith("media/"))
        assert zf.read(member) == PNG


@pytest.mark.asyncio
async def test_caller_bucket_uploads_bytes():
    uploaded = {}

    async def _upload(content, path):
        uploaded[path] = content

    data = _picture_docx("photo.png", PNG)
    candidates = collect_package_media(data, "docx")
    cfg = OfficeReadConfig()
    with patch(
        "aiecs.tools.office_tool.core.read_media.upload_to_storage",
        side_effect=_upload,
    ):
        items, _ = await realize_media(
            candidates,
            stable_id="ab12",
            cfg=cfg,
            delivery="caller_bucket",
            media_output_path="s3://bucket/media",
        )
    assert items[0].url.startswith("s3://bucket/media/")
    assert uploaded[items[0].url] == PNG


@pytest.mark.asyncio
async def test_media_budget_overflow_skips_convert(monkeypatch):
    cfg = OfficeReadConfig(max_media_count=1, max_media_bytes=8 * 1024 * 1024)
    first = _picture_docx("a.png", PNG)
    candidates = collect_package_media(first, "docx")
    candidates.append(candidates[0].__class__(kind="chart", alt="chart", page=1, convert_package=b"x", convert_ext="docx"))
    convert = AsyncMock(return_value=(PNG, None))
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch_bytes",
        convert,
    )
    items, warnings = await realize_media(
        candidates, stable_id="ab12", cfg=cfg, delivery="fetch_token", media_output_path=None,
    )
    assert len(items) == 1
    convert.assert_not_called()
    assert any("budget" in w for w in warnings)


@pytest.mark.asyncio
async def test_picture_stage_failure_empty_image(monkeypatch):
    from aiecs.tools.office_tool.core.document_read import read_document_markdown

    package = _picture_docx("photo.png", PNG)
    sidecar = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [
                {"class": "paragraph", "text": "Hello", "page_breaks": 0},
                {"class": "image", "alt": "photo", "text": "photo"},
            ],
        }],
        "footnotes": [],
    }
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://office-mcp:5040")

    def _boom(*_a, **_k):
        raise RuntimeError("stage fail")

    with patch(
        "aiecs.tools.office_tool.core.document_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed", "docx", "gs://b/doc.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.document_read._load_bytes",
        new_callable=AsyncMock,
        return_value=package,
    ), patch(
        "aiecs.tools.office_tool.core.document_read._source_size",
        new_callable=AsyncMock,
        return_value=len(package),
    ), patch(
        "aiecs.tools.office_tool.core.read_media.build_bytes_fetch_url",
        side_effect=_boom,
    ):
        result = await read_document_markdown(source_path="gs://b/doc.docx", format="markdown")

    assert result.get("success") is True
    assert "![photo]()" in result["markdown"]
    assert result["media"] == []
    assert any("stage" in w for w in result.get("_warnings") or [])


@pytest.mark.asyncio
async def test_chart_convert_fail_is_alt_line(monkeypatch):
    from aiecs.tools.office_tool.core.document_read import read_document_markdown

    package = _chart_docx()
    sidecar = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [{"class": "paragraph", "text": "Intro", "page_breaks": 0}],
        }],
        "footnotes": [],
    }
    convert = AsyncMock(return_value=(None, "fail"))
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.coarse_read.convert_and_fetch_bytes",
        convert,
    )
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.read_media.build_bytes_fetch_url",
        lambda *a, **k: "http://mcp/storage-objects/tok",
    )
    with patch(
        "aiecs.tools.office_tool.core.document_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed", "docx", "gs://b/doc.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.document_read._load_bytes",
        new_callable=AsyncMock,
        return_value=package,
    ), patch(
        "aiecs.tools.office_tool.core.document_read._source_size",
        new_callable=AsyncMock,
        return_value=len(package),
    ):
        result = await read_document_markdown(source_path="gs://b/doc.docx", format="markdown")

    assert result.get("success") is True
    assert "![" not in result["markdown"]
    assert "chart" in result["markdown"]
    assert result["media"] == []
    assert any("chart" in w for w in result.get("_warnings") or [])


@pytest.mark.asyncio
async def test_media_budget_overflow_empty_image_in_markdown(monkeypatch):
    from aiecs.config import OfficeReadConfig
    from aiecs.tools.office_tool.core.document_read import read_document_markdown

    first = _picture_docx("a.png", PNG)
    sidecar = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [
                {"class": "image", "alt": "one", "text": "one"},
                {"class": "image", "alt": "two", "text": "two"},
            ],
        }],
        "footnotes": [],
    }
    extra = collect_package_media(first, "docx")[0]
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.document_read.get_office_read_config",
        lambda: OfficeReadConfig(max_media_count=1),
    )
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.document_read.collect_package_media",
        lambda *_a, **_k: [extra, extra],
    )
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://office-mcp:5040")
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.read_media.build_bytes_fetch_url",
        lambda *a, **k: "http://mcp/storage-objects/tok",
    )
    with patch(
        "aiecs.tools.office_tool.core.document_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=("https://signed", "docx", "gs://b/doc.docx", "gs://"),
    ), patch(
        "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ), patch(
        "aiecs.tools.office_tool.core.document_read._load_bytes",
        new_callable=AsyncMock,
        return_value=first,
    ), patch(
        "aiecs.tools.office_tool.core.document_read._source_size",
        new_callable=AsyncMock,
        return_value=len(first),
    ):
        result = await read_document_markdown(source_path="gs://b/doc.docx", format="markdown")

    assert result.get("success") is True
    assert "![one](media/" in result["markdown"]
    assert "![two]()" in result["markdown"]
    assert len(result["media"]) == 1
    assert any("budget" in w for w in result.get("_warnings") or [])
