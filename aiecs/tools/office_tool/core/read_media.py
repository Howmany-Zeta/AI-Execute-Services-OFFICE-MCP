"""Extract OOXML/ODF images for office_read_document (P1)."""

from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from aiecs.tools.office_tool.core.storage.object_fetch import (
    build_bytes_fetch_url,
    mcp_public_base,
    register_fetch_bytes,
)
from aiecs.tools.office_tool.core.storage.backend import upload_to_storage
from aiecs.tools.office_tool.core.text_sanitize import sanitize_text

logger = logging.getLogger(__name__)

IMAGE_EXTS = {"png", "jpeg", "jpg", "gif", "svg"}
CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
}

_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
    "v": "urn:schemas-microsoft-com:vml",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

_REL_RE = re.compile(
    r'<Relationship[^>]+Id="([^"]+)"[^>]+Target="([^"]+)"[^>]*(?:TargetMode="([^"]+)")?',
    re.I,
)
_REL_RE_ALT = re.compile(
    r'<Relationship[^>]+Target="([^"]+)"[^>]+Id="([^"]+)"',
    re.I,
)


@dataclass
class MediaCandidate:
    kind: str  # picture, chart, icon, ole
    alt: str
    page: int
    part_name: str | None = None
    data: bytes | None = None
    ext: str = ""
    convert_package: bytes | None = None
    convert_ext: str = ""
    convert_attempted: bool = False
    skipped_reason: str | None = None


@dataclass
class MediaItem:
    name: str
    content_type: str
    data: bytes
    page: int
    alt: str
    url: str = ""
    staged: bool = True
    warnings: list[str] = field(default_factory=list)


def _part_ext(name: str) -> str:
    tail = name.rsplit(".", 1)
    return tail[1].lower() if len(tail) == 2 else ""


def _parse_rels(zf: zipfile.ZipFile, rels_name: str) -> dict[str, str]:
    if rels_name not in zf.namelist():
        return {}
    text = zf.read(rels_name).decode("utf-8", errors="ignore")
    mapping: dict[str, str] = {}
    for match in _REL_RE.finditer(text):
        mapping[match.group(1)] = match.group(2)
    if not mapping:
        for match in _REL_RE_ALT.finditer(text):
            mapping[match.group(2)] = match.group(1)
    return mapping


def _resolve_target(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base_dir = base_part.rsplit("/", 1)[0] if "/" in base_part else ""
    parts = [p for p in (base_dir.split("/") if base_dir else []) + target.split("/") if p and p != "."]
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)
    return "/".join(resolved)


def _read_part(zf: zipfile.ZipFile, name: str) -> bytes | None:
    if name in zf.namelist():
        return zf.read(name)
    lower = {n.lower(): n for n in zf.namelist()}
    real = lower.get(name.lower())
    return zf.read(real) if real else None


def _walk_xml_media(
    xml: bytes,
    rels: dict[str, str],
    base_part: str,
    zf: zipfile.ZipFile,
    page: int,
    src_ext: str,
) -> list[MediaCandidate]:
    out: list[MediaCandidate] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out

    seen_svg: set[str] = set()

    for elem in root.iter():
        tag = elem.tag.split("}", 1)[-1]
        ns_uri = elem.tag[1:].split("}", 1)[0] if elem.tag.startswith("{") else ""

        if tag == "svgBlip" or ns_uri == _NS["asvg"]:
            rid = elem.get(f"{{{_NS['r']}}}embed") or elem.get("embed")
            if not rid:
                continue
            target = rels.get(rid)
            if not target:
                continue
            part = _resolve_target(base_part, target)
            data = _read_part(zf, part)
            if data:
                seen_svg.add(part)
                out.append(MediaCandidate(kind="icon", alt="icon", page=page, part_name=part, data=data, ext=_part_ext(part) or "svg"))
            continue

        if tag == "blip":
            rid = elem.get(f"{{{_NS['r']}}}embed") or elem.get("embed")
            if not rid:
                continue
            target = rels.get(rid)
            if not target:
                continue
            part = _resolve_target(base_part, target)
            if part in seen_svg:
                continue
            data = _read_part(zf, part)
            ext = _part_ext(part)
            if data and ext in IMAGE_EXTS:
                out.append(MediaCandidate(kind="picture", alt="image", page=page, part_name=part, data=data, ext=ext))
            continue

        if tag == "imagedata":
            rid = elem.get(f"{{{_NS['r']}}}id") or elem.get("id")
            if not rid:
                continue
            target = rels.get(rid)
            if not target:
                continue
            part = _resolve_target(base_part, target)
            data = _read_part(zf, part)
            ext = _part_ext(part)
            if data and ext in IMAGE_EXTS:
                out.append(MediaCandidate(kind="picture", alt="image", page=page, part_name=part, data=data, ext=ext))
            continue

        if tag == "chart":
            rid = elem.get(f"{{{_NS['r']}}}id") or elem.get("id")
            title = "chart"
            target = rels.get(rid or "")
            bitmap = None
            bitmap_part = None
            if target:
                chart_part = _resolve_target(base_part, target)
                chart_rels = _parse_rels(zf, _rels_for(chart_part))
                for rel_target in chart_rels.values():
                    part = _resolve_target(chart_part, rel_target)
                    ext = _part_ext(part)
                    data = _read_part(zf, part)
                    if data and ext in IMAGE_EXTS:
                        bitmap = data
                        bitmap_part = part
                        break
            if bitmap:
                out.append(MediaCandidate(kind="chart", alt=title, page=page, part_name=bitmap_part, data=bitmap, ext=_part_ext(bitmap_part or "")))
            else:
                out.append(
                    MediaCandidate(
                        kind="chart",
                        alt=title,
                        page=page,
                        convert_package=_chart_package(zf, target or "", src_ext),
                        convert_ext=src_ext or "docx",
                    )
                )
            continue

        if tag == "image" and ns_uri == _NS["draw"]:
            href = elem.get(f"{{{_NS['xlink']}}}href") or elem.get("href")
            if not href:
                continue
            part = href.lstrip("./")
            data = _read_part(zf, part)
            ext = _part_ext(part)
            if data and ext in IMAGE_EXTS:
                out.append(MediaCandidate(kind="picture", alt="image", page=page, part_name=part, data=data, ext=ext))

    return _dedupe_candidates(out)


def _rels_for(part: str) -> str:
    if "/" not in part:
        return f"_rels/{part}.rels"
    directory, name = part.rsplit("/", 1)
    return f"{directory}/_rels/{name}.rels"


def _chart_package(zf: zipfile.ZipFile, chart_part: str, src_ext: str) -> bytes | None:
    """Copy the source zip; conversion rasterizes the chart page."""
    try:
        return _zip_bytes(zf)
    except Exception:
        return None


def _zip_bytes(zf: zipfile.ZipFile) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        for info in zf.infolist():
            out.writestr(info, zf.read(info.filename))
    return buf.getvalue()


def _dedupe_candidates(items: list[MediaCandidate]) -> list[MediaCandidate]:
    seen: set[str] = set()
    out: list[MediaCandidate] = []
    for item in items:
        key = item.part_name or f"{item.kind}:{item.page}:{len(out)}"
        if item.part_name and item.part_name in seen:
            continue
        if item.part_name:
            seen.add(item.part_name)
        out.append(item)
    return out


def collect_package_media(data: bytes, file_ext: str) -> list[MediaCandidate]:
    ext = (file_ext or "").lower().lstrip(".")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return []
    names = zf.namelist()
    out: list[MediaCandidate] = []
    if ext in {"docx", "docm", "dotx"} or "word/document.xml" in names:
        xml = _read_part(zf, "word/document.xml")
        if xml:
            rels = _parse_rels(zf, "word/_rels/document.xml.rels")
            out.extend(_walk_xml_media(xml, rels, "word/document.xml", zf, 1, ext or "docx"))
    elif ext in {"pptx", "pptm", "ppsx"} or any(n.startswith("ppt/slides/slide") for n in names):
        slide_names = sorted(
            n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
        )
        for index, slide in enumerate(slide_names, start=1):
            xml = _read_part(zf, slide)
            if not xml:
                continue
            rels = _parse_rels(zf, _rels_for(slide))
            out.extend(_walk_xml_media(xml, rels, slide, zf, index, ext or "pptx"))
    elif ext in {"xlsx", "xlsm"} or any(n.startswith("xl/drawings/") for n in names):
        drawings = sorted(n for n in names if re.fullmatch(r"xl/drawings/drawing\d+\.xml", n))
        for index, drawing in enumerate(drawings, start=1):
            xml = _read_part(zf, drawing)
            if not xml:
                continue
            rels = _parse_rels(zf, _rels_for(drawing))
            out.extend(_walk_xml_media(xml, rels, drawing, zf, index, ext or "xlsx"))
    elif ext in {"odt", "odp"} or "content.xml" in names:
        xml = _read_part(zf, "content.xml")
        if xml:
            out.extend(_walk_xml_media(xml, {}, "content.xml", zf, 1, ext or "odt"))
    return out


def media_filename(stable_id: str, data: bytes, ext: str, seq: int) -> str:
    digest = hashlib.sha256(data).hexdigest()[:8]
    safe_ext = ext if ext in IMAGE_EXTS else "png"
    return f"doc_{stable_id}_{digest}_{seq:02d}.{safe_ext}"


def _guess_ext(data: bytes, hinted: str) -> str:
    if hinted in IMAGE_EXTS:
        return "jpg" if hinted == "jpeg" else hinted
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpg"
    if data.startswith(b"GIF8"):
        return "gif"
    if b"<svg" in data[:200].lower():
        return "svg"
    return "png"


async def export_chart_or_icon(
    package_bytes: bytes,
    src_ext: str,
    client=None,
) -> tuple[bytes | None, bool]:
    """Convert a chart/icon package to PNG. Returns (bytes, convert_attempted)."""
    from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch_bytes

    if not package_bytes:
        return None, False
    try:
        fetch_url = build_bytes_fetch_url(package_bytes, src_ext or "docx", 300)
    except Exception:
        return None, True
    data, error = await convert_and_fetch_bytes(fetch_url, src_ext or "docx", "png", client=client)
    if error or not data:
        return None, True
    return data, True


async def realize_media(
    candidates: list[MediaCandidate],
    *,
    stable_id: str,
    cfg,
    delivery: str,
    media_output_path: str | None,
    client=None,
) -> tuple[list[MediaItem], list[str]]:
    warnings: list[str] = []
    kept: list[MediaItem] = []
    used_bytes = 0
    seq = 1
    overflow = False

    for candidate in candidates:
        alt = sanitize_text(candidate.alt, trim_edges=True) or candidate.kind
        if overflow or len(kept) >= cfg.max_media_count:
            overflow = True
            candidate.skipped_reason = "overflow"
            continue
        data = candidate.data
        convert_attempted = False
        if data is None and candidate.kind in {"chart", "icon"}:
            data, convert_attempted = await export_chart_or_icon(
                candidate.convert_package or b"",
                candidate.convert_ext or "docx",
                client=client,
            )
            candidate.convert_attempted = convert_attempted
            if data is None:
                if convert_attempted:
                    candidate.skipped_reason = "convert_fail"
                    warnings.append(f"{candidate.kind} export failed")
                continue
        if data is None:
            continue
        if used_bytes + len(data) > cfg.max_media_bytes:
            overflow = True
            candidate.skipped_reason = "overflow"
            continue
        ext = _guess_ext(data, candidate.ext)
        name = media_filename(stable_id, data, ext, seq)
        seq += 1
        used_bytes += len(data)
        kept.append(
            MediaItem(
                name=name,
                content_type=CONTENT_TYPES.get(ext, "application/octet-stream"),
                data=data,
                page=candidate.page,
                alt=alt,
            )
        )

    if overflow:
        warnings.append("media budget exceeded; extra images omitted from media[]")

    if delivery == "caller_bucket":
        prefix = (media_output_path or "").rstrip("/")
        for item in kept:
            dest = f"{prefix}/{item.name}"
            try:
                await upload_to_storage(item.data, dest)
                item.url = dest
            except Exception as exc:
                warnings.append(f"failed to upload {item.name}")
                logger.warning("caller_bucket upload failed: %s", exc)
    else:
        base = mcp_public_base()
        if not base:
            warnings.append("MCP_PUBLIC_URL is not set; media[].url is empty")
        for item in kept:
            try:
                if base:
                    item.url = build_bytes_fetch_url(item.data, item.name.rsplit(".", 1)[-1], cfg.media_ttl_sec)
                else:
                    register_fetch_bytes(item.data, item.content_type, cfg.media_ttl_sec)
            except Exception as exc:
                item.staged = False
                warnings.append(f"failed to stage {item.name}")
                logger.warning("fetch_token stage failed: %s", exc)

    return kept, warnings


def public_media(items: list[MediaItem]) -> list[dict[str, Any]]:
    return [
        {
            "name": item.name,
            "content_type": item.content_type,
            "bytes": len(item.data),
            "url": item.url,
            "page": item.page,
        }
        for item in items
        if item.staged
    ]
