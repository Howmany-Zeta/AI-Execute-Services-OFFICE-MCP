"""Helpers for office MCP E2E tests (env from `.env.test`)."""

from __future__ import annotations

import httpx

from tests.env_test import get_e2e_config


def documentserver_reachable() -> bool:
    cfg = get_e2e_config()
    if not cfg.documentserver_url:
        return False
    try:
        r = httpx.get(f"{cfg.documentserver_url.rstrip('/')}/healthcheck", timeout=5)
        return r.text.strip() == "true"
    except Exception:
        return False


def mcp_reachable() -> bool:
    cfg = get_e2e_config()
    try:
        transport = (
            httpx.HTTPTransport(local_address="0.0.0.0")
            if "localhost" in cfg.mcp_url or "127.0.0.1" in cfg.mcp_url
            else None
        )
        with httpx.Client(timeout=5, transport=transport) as client:
            r = client.get(f"{cfg.mcp_url.rstrip('/')}/health")
        return r.status_code == 200
    except Exception:
        return False


def mcp_protocol_url() -> str:
    """JSON-RPC base URL for live MCP integration tests."""
    return f"{get_e2e_config().mcp_url.rstrip('/')}/mcp/v1/"
