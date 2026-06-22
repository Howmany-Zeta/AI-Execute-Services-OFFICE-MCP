"""Unified success/error response shapes for office tools (ADR-006)."""

from typing import Any


def err(text: str) -> dict[str, Any]:
    """Return MCP-compatible error dict."""
    return {"isError": True, "text": text}


def ok(**kwargs: Any) -> dict[str, Any]:
    """Return MCP-compatible success dict."""
    return {"success": True, **kwargs}


def is_error(result: dict[str, Any]) -> bool:
    """True when result is an ADR-006 error dict from err() or compatible helpers."""
    return result.get("isError") is True
