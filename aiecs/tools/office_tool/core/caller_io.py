"""Caller-facing file I/O: inline bytes in, file payload out. No caller MinIO."""

from __future__ import annotations

import base64
import io
import zipfile

from typing import Self

from pydantic import BaseModel, model_validator

from aiecs.tools.office_tool.core.errors import ok
from aiecs.tools.office_tool.core.file_ext import (
    extract_path_file_ext,
    guess_media_type,
    logical_filename,
)

SOURCE_PATH_INTERNAL = (
    "Internal compatibility: gs:// or s3:// on storage this MCP can access. "
    "External callers should use source_url or content_base64."
)

INLINE_SOURCE_PROPERTIES: dict = {
    "content_base64": {
        "type": "string",
        "description": "Base64-encoded file. Alternative to source_url. No bucket required.",
    },
    "source_bytes": {
        "type": "string",
        "description": "Alias of content_base64.",
    },
    "filename": {
        "type": "string",
        "description": "Optional name or extension hint when sending content_base64.",
    },
}


def is_storage_output_path(path: str | None) -> bool:
    p = (path or "").strip()
    return p.startswith("s3://") or p.startswith("gs://")


def decode_inline_file(
    content_base64: str | bytes | None = None,
    source_bytes: str | bytes | None = None,
) -> tuple[bytes | None, str | None]:
    """Return (data, None) or (None, error). Empty input is (None, None)."""
    raw = content_base64 if content_base64 not in (None, "") else source_bytes
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, bytes):
        return raw, None
    try:
        return base64.b64decode(raw, validate=False), None
    except Exception as exc:
        return None, f"content_base64 is not valid base64: {exc}"


def sniff_office_ext(data: bytes, filename: str | None = None) -> str:
    hinted = extract_path_file_ext(filename or "")
    if hinted:
        return hinted
    if data.startswith(b"%PDF"):
        return "pdf"
    if data[:2] == b"PK":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except Exception:
            return "docx"
        if any(name.startswith("word/") for name in names):
            return "docx"
        if any(name.startswith("xl/") for name in names):
            return "xlsx"
        if any(name.startswith("ppt/") for name in names):
            return "pptx"
        return "docx"
    return "docx"


def file_success(
    content: bytes,
    filename: str,
    fmt: str,
    *,
    file_url: str | None = None,
) -> dict:
    payload = ok(
        content_base64=base64.b64encode(content).decode("ascii"),
        filename=filename,
        format=fmt,
        media_type=guess_media_type(filename),
        bytes=len(content),
    )
    if file_url:
        payload["file_url"] = file_url
    return payload


def result_filename(output_path: str | None, file_type: str | None) -> tuple[str, str]:
    return logical_filename(output_path, file_type)


class CallerSourceMixin(BaseModel):
    """source_url or content_base64; source_path is internal s3:// / gs:// only."""

    source_path: str | None = None
    source_url: str | None = None
    content_base64: str | None = None
    source_bytes: str | bytes | None = None
    filename: str | None = None

    @model_validator(mode="after")
    def exactly_one_caller_source(self) -> Self:
        path = (self.source_path or "").strip()
        url = (self.source_url or "").strip()
        inline = self.content_base64 not in (None, "") or self.source_bytes not in (None, "")
        n = sum([bool(path), bool(url), bool(inline)])
        if n > 1:
            raise ValueError("Provide only one of source_path, source_url, or content_base64")
        if n == 0:
            raise ValueError(
                "Provide source_url, content_base64, or source_path (internal s3:// / gs://)"
            )
        return self


def caller_source_kwargs(args: object) -> dict:
    return {
        "content_base64": getattr(args, "content_base64", None),
        "source_bytes": getattr(args, "source_bytes", None),
        "filename": getattr(args, "filename", None),
    }
