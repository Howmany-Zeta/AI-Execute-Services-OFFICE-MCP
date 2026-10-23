"""Unit tests for Builder JSON sidecar extract/parse (no DocumentServer)."""

from __future__ import annotations

import io
import json
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

from aiecs.tools.office_tool.core.builder_json_sidecar import (
    SIDECAR_MARK_END,
    SIDECAR_MARK_START,
    _parse_sidecar_json_text,
    _sidecar_bytes_to_text,
    build_sidecar_extract_script,
)

_A_T = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
_S_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"


def _pptx_with_text(text: str) -> bytes:
    root = Element("sld")
    node = SubElement(root, _A_T)
    node.text = text
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ppt/slides/slide1.xml", tostring(root, encoding="unicode"))
        zf.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


def test_pptx_script_skips_createfile_txt():
    script = build_sidecar_extract_script("https://x/deck.pptx", "pptx", "var jsonStr = '{}';")
    assert 'CreateFile("txt")' not in script
    assert "GetPresentation" in script
    assert "GetNotesPage" in script
    assert 'SaveFile("pptx"' in script


def test_pdf_script_still_skips_createfile_txt():
    script = build_sidecar_extract_script("https://x/doc.pdf", "pdf", "var jsonStr = '{}';")
    assert 'CreateFile("txt")' not in script
    assert 'SaveFile("docx"' in script


def test_word_script_still_uses_createfile_txt():
    script = build_sidecar_extract_script("https://x/doc.docx", "docx", "var jsonStr = '{}';")
    assert 'CreateFile("txt")' in script


def test_xlsx_script_skips_createfile_txt():
    script = build_sidecar_extract_script("https://x/book.xlsx", "xlsx", "var jsonStr = '{}';")
    assert 'CreateFile("txt")' not in script
    assert "AddSheet" in script
    assert "_office_sidecar" in script
    assert 'SaveFile("xlsx"' in script
    assert "typeof Api.GetSheetsCount" in script
    assert "GetSheetsCount() - 1" not in script


def test_parse_accepts_slides_and_layouts():
    payload = {"layouts": ["Title Slide"], "slides": [{"slide_index": 0, "title": "Hi"}]}
    parsed = _parse_sidecar_json_text(json.dumps(payload, ensure_ascii=False))
    assert parsed["layouts"] == ["Title Slide"]
    assert parsed["slides"][0]["title"] == "Hi"


def _xlsx_with_text(text: str) -> bytes:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    root = Element("sst", {"xmlns": ns})
    si = SubElement(root, f"{{{ns}}}si")
    node = SubElement(si, _S_T)
    node.text = text
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/sharedStrings.xml", tostring(root, encoding="unicode"))
        zf.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


def test_xlsx_zip_hex_sidecar_roundtrip():
    body = {"sheets": [{"sheet_index": 0, "name": "品牌", "rows": [["a"]]}]}
    raw = json.dumps(body, ensure_ascii=False)
    marked = SIDECAR_MARK_START + raw.encode("utf-8").hex() + SIDECAR_MARK_END
    text = _sidecar_bytes_to_text(_xlsx_with_text("prefix " + marked + " suffix"))
    parsed = _parse_sidecar_json_text(text)
    assert parsed["sheets"][0]["name"] == "品牌"


def test_pptx_zip_hex_sidecar_roundtrip():
    body = {"layouts": ["Title"], "slides": [{"slide_index": 0, "title": "思念"}]}
    raw = json.dumps(body, ensure_ascii=False)
    marked = SIDECAR_MARK_START + raw.encode("utf-8").hex() + SIDECAR_MARK_END
    text = _sidecar_bytes_to_text(_pptx_with_text("prefix " + marked + " suffix"))
    parsed = _parse_sidecar_json_text(text)
    assert parsed["slides"][0]["title"] == "思念"
