"""
Builder JSON sidecar extraction for fine read (word/presentation/spreadsheet/pdf).
"""

import io
import json
import logging
import zipfile
from xml.etree import ElementTree as ET

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    BUILDER_TIMEOUT,
    get_documentserver_client,
)
from aiecs.tools.office_tool.core.builder_js import close_file, open_file, save_file
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.source import resolve_document_source

logger = logging.getLogger(__name__)

SIDECAR_FILENAME = "structure.txt"
SIDECAR_DOCX_FILENAME = "structure.docx"
SIDECAR_PPTX_FILENAME = "structure.pptx"
SIDECAR_XLSX_FILENAME = "structure.xlsx"
SIDECAR_MARK_START = "<<<OFFICE_SIDECAR>>>"
SIDECAR_MARK_END = "<<<END_SIDECAR>>>"
_W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
_A_T = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
_S_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
_PRESENTATION_EXTS = frozenset({"pptx", "ppt", "odp"})
_SPREADSHEET_EXTS = frozenset({"xlsx", "xls", "ods"})
_SIDECAR_JSON_KEYS = frozenset(
    {"pages", "slides", "layouts", "sheets", "document", "body", "extract_error"}
)


def _xml_plain_text(xml: bytes, tag: str) -> str:
    return "".join(node.text or "" for node in ET.fromstring(xml).iter(tag))


def _docx_plain_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return _xml_plain_text(zf.read("word/document.xml"), _W_T)


def _pptx_plain_text(data: bytes) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            if name.startswith("ppt/") or name == "content.xml":
                try:
                    parts.append(_xml_plain_text(zf.read(name), _A_T))
                except ET.ParseError:
                    continue
    return "".join(parts)


def _xlsx_plain_text(data: bytes) -> str:
    """Prefer sharedStrings; stop once the sidecar mark is present."""
    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        preferred = [name for name in names if name.endswith("sharedStrings.xml")]
        rest = [
            name
            for name in names
            if name.endswith(".xml")
            and (name.startswith("xl/") or name == "content.xml")
            and name not in preferred
        ]
        for name in preferred + rest:
            try:
                chunk = _xml_plain_text(zf.read(name), _S_T)
            except ET.ParseError:
                continue
            if not chunk:
                continue
            parts.append(chunk)
            joined = "".join(parts)
            if SIDECAR_MARK_START in joined and SIDECAR_MARK_END in joined:
                return joined
    return "".join(parts)


def _sidecar_bytes_to_text(data: bytes) -> str:
    """Decode sidecar bytes. PDF/PPT/xlsx write into the open file; CreateFile('txt') is a no-op."""
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
            if "word/document.xml" in names:
                return _docx_plain_text(data)
            if any(name.startswith("xl/") for name in names):
                return _xlsx_plain_text(data)
            if any(name.startswith("ppt/") for name in names) or "content.xml" in names:
                return _pptx_plain_text(data)
        except Exception:
            logger.exception("Failed to read office sidecar zip")
    return data.decode("utf-8-sig")


def _decode_hex_payload(payload: str) -> str | None:
    hex_body = "".join(ch for ch in payload if ch in "0123456789abcdefABCDEF")
    if len(hex_body) < 4 or len(hex_body) % 2:
        return None
    try:
        return bytes.fromhex(hex_body).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _parse_sidecar_json_text(text: str) -> dict:
    """
    Parse sidecar txt from Builder.

    ONLYOFFICE may prefix UTF-8 BOM, split long AddText across paragraphs/lines,
    or append trailing content after the first JSON value.
    """
    cleaned = text.strip()
    if SIDECAR_MARK_START in cleaned:
        after = cleaned.rsplit(SIDECAR_MARK_START, 1)[1]
        if SIDECAR_MARK_END in after:
            payload = after.split(SIDECAR_MARK_END, 1)[0].strip()
        else:
            payload = after.strip()
        decoded = _decode_hex_payload(payload)
        cleaned = decoded if decoded else payload
    if not cleaned:
        raise json.JSONDecodeError("Empty sidecar", cleaned, 0)

    joined = "".join(cleaned.splitlines())
    last_error: json.JSONDecodeError | None = None
    last_good: dict | None = None
    for candidate in (joined, cleaned):
        if not candidate:
            continue
        idx = 0
        while idx < len(candidate):
            start = candidate.find("{", idx)
            if start < 0:
                break
            try:
                obj, end = json.JSONDecoder().raw_decode(candidate[start:])
                if isinstance(obj, dict) and (_SIDECAR_JSON_KEYS & obj.keys()):
                    last_good = obj
                idx = start + max(end, 1)
            except json.JSONDecodeError as e:
                last_error = e
                idx = start + 1
        if last_good is not None:
            return last_good
    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("Empty sidecar", cleaned, 0)


def build_sidecar_extract_script(
    open_url: str,
    file_ext: str,
    extract_body: str,
) -> str:
    """
    OpenFile → extract_body (must assign JSON to jsonStr)
    → write sidecar → SaveFile → CloseFile

    This DocumentServer resets JS scope at every builder.* call and cannot
    CreateFile("txt"). PDF writes jsonStr onto a FreeText annot in the same
    chunk as extract, then SaveFile("docx"). Presentation writes onto the
    open deck (notes + a slide shape) and SaveFile("pptx"). Spreadsheet writes
    chunked cells on a new sheet and SaveFile("xlsx").
    """
    lines = [
        open_file(open_url, file_ext),
        'var jsonStr = "[]";',
        "try {",
        extract_body.strip(),
        '} catch (e) { jsonStr = "{\\"extract_error\\":\\"" + String(e).replace(/"/g, "\'") + "\\"}"; }',
    ]
    ext = file_ext.lower()
    if ext == "pdf":
        lines.extend(
            [
                "var sidecarHex = '';",
                "for (var hi = 0; hi < jsonStr.length; hi++) {",
                "  var hh = jsonStr.charCodeAt(hi).toString(16);",
                "  sidecarHex += (hh.length < 2 ? '0' : '') + hh;",
                "}",
                f'var sidecarPayload = "{SIDECAR_MARK_START}" + sidecarHex + "{SIDECAR_MARK_END}";',
                "var sidecarDoc = Api.GetDocument();",
                "var sidecarPage = null;",
                "try { sidecarPage = sidecarDoc.AddPage(sidecarDoc.GetPagesCount()); } catch (e) { sidecarPage = sidecarDoc.GetPage(0); }",
                "if (sidecarPage) {",
                "  try {",
                "    var sidecarShape = Api.CreateShape('textRect', 5486400, 5486400);",
                "    var sidecarContent = sidecarShape.GetContent ? sidecarShape.GetContent() : null;",
                "    var sidecarPara = sidecarContent && sidecarContent.GetElement ? sidecarContent.GetElement(0) : null;",
                "    if (sidecarPara && sidecarPara.AddText) sidecarPara.AddText(sidecarPayload);",
                "    sidecarPage.AddObject(sidecarShape);",
                "  } catch (e) {}",
                "  try {",
                "    var sidecarAnnot = Api.CreateFreeTextAnnot([0, 0, 500, 200]);",
                "    sidecarAnnot.SetContents(sidecarPayload);",
                "    sidecarPage.AddObject(sidecarAnnot);",
                "  } catch (e) {}",
                "}",
                save_file("docx", SIDECAR_DOCX_FILENAME),
                close_file(),
            ]
        )
        return "\n".join(lines)
    if ext in _PRESENTATION_EXTS:
        lines.extend(
            [
                "function _sidecarUtf8Hex(s) {",
                "  var hex = '';",
                "  for (var i = 0; i < s.length; i++) {",
                "    var code = s.charCodeAt(i);",
                "    if (code >= 0xD800 && code <= 0xDBFF && i + 1 < s.length) {",
                "      var lo = s.charCodeAt(i + 1);",
                "      if (lo >= 0xDC00 && lo <= 0xDFFF) {",
                "        code = 0x10000 + ((code - 0xD800) << 10) + (lo - 0xDC00);",
                "        i++;",
                "      }",
                "    }",
                "    var bytes;",
                "    if (code <= 0x7F) bytes = [code];",
                "    else if (code <= 0x7FF) bytes = [0xC0 | (code >> 6), 0x80 | (code & 0x3F)];",
                "    else if (code <= 0xFFFF) bytes = [0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)];",
                "    else bytes = [0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)];",
                "    for (var b = 0; b < bytes.length; b++) {",
                "      var hh = bytes[b].toString(16);",
                "      hex += (hh.length < 2 ? '0' : '') + hh;",
                "    }",
                "  }",
                "  return hex;",
                "}",
                f'var sidecarPayload = "{SIDECAR_MARK_START}" + _sidecarUtf8Hex(jsonStr) + "{SIDECAR_MARK_END}";',
                "var sidecarPres = Api.GetPresentation();",
                "var sidecarSlide = sidecarPres && sidecarPres.GetSlideByIndex ? sidecarPres.GetSlideByIndex(0) : null;",
                "if (sidecarSlide) {",
                "  try {",
                "    var sidecarNotes = sidecarSlide.GetNotesPage();",
                "    if (sidecarNotes) {",
                "      var sidecarNoteShapes = sidecarNotes.GetAllShapes ? sidecarNotes.GetAllShapes() : [];",
                "      if (sidecarNoteShapes && sidecarNoteShapes.length > 0 && sidecarNoteShapes[0].SetText) {",
                "        sidecarNoteShapes[0].SetText(sidecarPayload);",
                "      } else if (sidecarNotes.AddTextbox) {",
                "        var sidecarTb = sidecarNotes.AddTextbox();",
                "        if (sidecarTb && sidecarTb.SetText) sidecarTb.SetText(sidecarPayload);",
                "      }",
                "    }",
                "  } catch (e) {}",
                "  try {",
                "    var sidecarShape = Api.CreateShape('rect', 5486400, 5486400);",
                "    var sidecarContent = sidecarShape.GetDocContent ? sidecarShape.GetDocContent() : (sidecarShape.GetContent ? sidecarShape.GetContent() : null);",
                "    var sidecarPara = sidecarContent && sidecarContent.GetElement ? sidecarContent.GetElement(0) : null;",
                "    if (sidecarPara && sidecarPara.AddText) {",
                "      var _chunk = 4000;",
                "      for (var ci = 0; ci < sidecarPayload.length; ci += _chunk) {",
                "        sidecarPara.AddText(sidecarPayload.substring(ci, ci + _chunk));",
                "      }",
                "    }",
                "    sidecarSlide.AddObject(sidecarShape);",
                "  } catch (e) {}",
                "}",
                save_file("pptx", SIDECAR_PPTX_FILENAME),
                close_file(),
            ]
        )
        return "\n".join(lines)
    if ext in _SPREADSHEET_EXTS:
        lines.extend(
            [
                "function _sidecarUtf8Hex(s) {",
                "  var hex = '';",
                "  for (var i = 0; i < s.length; i++) {",
                "    var code = s.charCodeAt(i);",
                "    if (code >= 0xD800 && code <= 0xDBFF && i + 1 < s.length) {",
                "      var lo = s.charCodeAt(i + 1);",
                "      if (lo >= 0xDC00 && lo <= 0xDFFF) {",
                "        code = 0x10000 + ((code - 0xD800) << 10) + (lo - 0xDC00);",
                "        i++;",
                "      }",
                "    }",
                "    var bytes;",
                "    if (code <= 0x7F) bytes = [code];",
                "    else if (code <= 0x7FF) bytes = [0xC0 | (code >> 6), 0x80 | (code & 0x3F)];",
                "    else if (code <= 0xFFFF) bytes = [0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)];",
                "    else bytes = [0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)];",
                "    for (var b = 0; b < bytes.length; b++) {",
                "      var hh = bytes[b].toString(16);",
                "      hex += (hh.length < 2 ? '0' : '') + hh;",
                "    }",
                "  }",
                "  return hex;",
                "}",
                f'var sidecarPayload = "{SIDECAR_MARK_START}" + _sidecarUtf8Hex(jsonStr) + "{SIDECAR_MARK_END}";',
                "var sidecarCount = 0;",
                "if (typeof Api.GetSheetsCount === 'function') {",
                "  sidecarCount = Api.GetSheetsCount();",
                "} else if (typeof Api.GetSheets === 'function') {",
                "  try { var _allS = Api.GetSheets(); sidecarCount = _allS ? _allS.length : 0; } catch (eCount) { sidecarCount = 0; }",
                "}",
                "if (!sidecarCount) {",
                "  for (var _si = 0; _si < 256; _si++) {",
                "    var _probe = null;",
                "    try { _probe = Api.GetSheet(_si); } catch (eProbe) { _probe = null; }",
                "    if (!_probe) break;",
                "    sidecarCount++;",
                "  }",
                "}",
                "try { Api.AddSheet(); } catch (eAdd) {}",
                "var sidecarWs = null;",
                "try { sidecarWs = Api.GetSheet(sidecarCount); } catch (eGet) { sidecarWs = null; }",
                "if (!sidecarWs) { try { sidecarWs = Api.GetActiveSheet(); } catch (eAct) { sidecarWs = null; } }",
                'try { if (sidecarWs && sidecarWs.SetName) sidecarWs.SetName("_office_sidecar"); } catch (eName) {}',
                "var _chunk = 8000;",
                "var _row = 0;",
                "if (sidecarWs) {",
                "  for (var ci = 0; ci < sidecarPayload.length; ci += _chunk) {",
                '    sidecarWs.GetRange("A" + String(_row + 1)).SetValue(sidecarPayload.substring(ci, ci + _chunk));',
                "    _row++;",
                "  }",
                "}",
                save_file("xlsx", SIDECAR_XLSX_FILENAME),
                close_file(),
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            'builder.CreateFile("txt");',
            "var sidecarDoc = Api.GetDocument();",
            "var sidecarPara = sidecarDoc.GetElement ? sidecarDoc.GetElement(0) : null;",
            "if (!sidecarPara) { sidecarPara = Api.CreateParagraph(); if (sidecarDoc.Push) { sidecarDoc.Push(sidecarPara); } }",
            "sidecarPara.AddText(jsonStr);",
            save_file("txt", SIDECAR_FILENAME),
            close_file(),
        ]
    )
    return "\n".join(lines)


async def read_sidecar_json(
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    extract_body: str,
    client: DocumentServerClient | None = None,
    *,
    fetch_url: str | None = None,
    content_base64: str | bytes | None = None,
    source_bytes: str | bytes | None = None,
    filename: str | None = None,
) -> tuple[dict | None, str | None]:
    """
    Resolve source, run sidecar Builder script, download and parse JSON.

    Pass fetch_url when the caller already resolved (needed for content_base64).

    Returns:
        (parsed_dict, None) on success
        (None, error_text) on failure
    """
    ext = file_ext
    if not fetch_url:
        resolved = await resolve_document_source(
            (source_path or "").strip(),
            (source_url or "").strip(),
            content_base64=content_base64,
            source_bytes=source_bytes,
            filename=filename,
        )
        if isinstance(resolved, dict):
            return None, resolved.get("text", "Failed to resolve document source")
        fetch_url, resolved_ext, _, _ = resolved
        ext = file_ext or resolved_ext

    script = build_sidecar_extract_script(fetch_url, ext, extract_body)
    result = await run_builder_script(script, client=client)
    if result.get("isError"):
        return None, result.get("text", "Builder sidecar failed")

    file_url = result.get("file_url")
    if not file_url:
        return None, "DocumentServer did not return sidecar fileUrl"

    try:
        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            text = _sidecar_bytes_to_text(response.content)
        parsed = _parse_sidecar_json_text(text)
        if parsed.get("extract_error"):
            return None, f"Sidecar extract failed: {parsed['extract_error']}"
        return parsed, None
    except json.JSONDecodeError as e:
        logger.exception("Sidecar JSON parse failed")
        return None, f"Invalid sidecar JSON: {e}"
    except Exception as e:
        logger.exception("Failed to download sidecar")
        return None, str(e)
