"""Exhaustive parse allow-lists. Do not use classify_file_ext (ADR-048)."""

from __future__ import annotations

from typing import Literal

from aiecs.tools.office_tool.core.file_ext import extract_path_file_ext

ParseEngine = Literal["document_ai", "documentserver"]

ALLOW_DAI = frozenset({"pdf"})
ALLOW_DS = frozenset({
    "doc", "docx", "docm", "odt", "ott",
    "ppt", "pptx", "pptm", "odp", "otp", "pps", "ppsx",
})


def parse_file_ext(path_or_url: str) -> str:
    return extract_path_file_ext(path_or_url)


def route_parse_engine(ext: str, engine: str) -> tuple[ParseEngine | None, str | None]:
    """
    Return (engine, None) or (None, error_code).
    error_code is office_unsupported or invalid_engine.
    """
    ext = (ext or "").lower().lstrip(".")
    requested = (engine or "auto").strip().lower()
    if ext in ALLOW_DAI:
        if requested == "documentserver":
            return "documentserver", None
        if requested in ("auto", "document_ai"):
            return "document_ai", None
        return None, "invalid_engine"
    if ext in ALLOW_DS:
        if requested == "document_ai":
            return None, "invalid_engine"
        if requested in ("auto", "documentserver"):
            return "documentserver", None
        return None, "invalid_engine"
    return None, "office_unsupported"
