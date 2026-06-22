"""Unified success/error response shapes for office tools (ADR-006)."""

from typing import Any


def err(text: str) -> dict[str, Any]:
    """Return MCP-compatible error dict."""
    return {"isError": True, "text": text}


def ok(**kwargs: Any) -> dict[str, Any]:
    """Return MCP-compatible success dict."""
    return {"success": True, **kwargs}
