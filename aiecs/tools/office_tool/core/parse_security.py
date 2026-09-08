"""Parse job security: output prefixes, webhook SSRF, secrets (ADR-048)."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import socket
import time
from urllib.parse import urlparse

from aiecs.config import get_parse_job_config
from aiecs.tools.office_tool.core.storage.paths import is_object_storage_path

logger = logging.getLogger(__name__)

BLOCKED_HOSTS = frozenset({"metadata.google.internal", "metadata.google.com", "169.254.169.254"})


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def secrets_equal(provided: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(provided or ""), stored_hash or "")


def structure_sidecar_path(output_path: str) -> str:
    """s3://b/derived/e/canonical.md -> s3://b/derived/e/canonical.structure.json"""
    if "/" in output_path:
        prefix, name = output_path.rsplit("/", 1)
        if "." in name:
            stem = name.rsplit(".", 1)[0]
            return f"{prefix}/{stem}.structure.json"
        return f"{prefix}/{name}.structure.json"
    if "." in output_path:
        return f"{output_path.rsplit('.', 1)[0]}.structure.json"
    return f"{output_path}.structure.json"


def _normalize_object_path(path: str) -> str:
    p = (path or "").strip()
    while "//" in p[5:]:
        scheme, rest = p.split("://", 1)
        rest = rest.replace("//", "/")
        p = f"{scheme}://{rest}"
    return p.rstrip("/") if p.count("/") > 3 else p


def output_path_allowed(output_path: str, source_path: str | None = None) -> str | None:
    """Return error text if output_path is illegal, else None."""
    cfg = get_parse_job_config()
    prefixes = cfg.allowed_prefixes()
    if not prefixes:
        return "PARSE_OUTPUT_ALLOWED_PREFIXES is empty; writes are disabled"
    path = (output_path or "").strip()
    if not is_object_storage_path(path):
        return "output_path must be gs:// or s3://"
    if ".." in path:
        return "output_path must not contain .."
    normalized = _normalize_object_path(path)
    if not any(normalized.startswith(_normalize_object_path(pref).rstrip("/") + "/") or normalized == _normalize_object_path(pref).rstrip("/") for pref in prefixes):
        return "output_path is outside PARSE_OUTPUT_ALLOWED_PREFIXES"
    src = (source_path or "").strip()
    if src and _normalize_object_path(src) == normalized:
        return "output_path must not equal source_path"
    return None


def _ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def webhook_url_allowed(url: str, *, resolve_dns: bool = True) -> str | None:
    """Return error if webhook URL is not allowed. resolve_dns=True at POST time."""
    cfg = get_parse_job_config()
    if not cfg.webhook_ready():
        return "webhook is disabled"
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https":
        return "callback_url must be https"
    host = (parsed.hostname or "").lower()
    if not host or host in BLOCKED_HOSTS:
        return "callback_url host is not allowed"
    if host not in cfg.webhook_hosts():
        return "callback_url host is not allowlisted"
    if not resolve_dns:
        return None
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return "callback_url host could not be resolved"
    for info in infos:
        raw = info[4][0]
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if _ip_blocked(ip):
            return "callback_url resolves to a blocked address"
    return None


def sign_webhook(job_id: str, sha256: str, timestamp: int, secret: str) -> str:
    payload = f"{job_id}.{sha256}.{timestamp}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_webhook_signature(job_id: str, sha256: str, timestamp: int, signature: str, secret: str, max_skew_sec: int) -> bool:
    now = int(time.time())
    if abs(now - int(timestamp)) > max_skew_sec:
        return False
    expected = sign_webhook(job_id, sha256, timestamp, secret)
    return hmac.compare_digest(expected, signature or "")


async def post_webhook(callback_url: str, body: dict) -> None:
    """POST summary; failures are logged only. Re-resolves DNS at send time."""
    cfg = get_parse_job_config()
    deny = webhook_url_allowed(callback_url, resolve_dns=True)
    if deny:
        logger.warning("Skipping webhook: %s", deny)
        return
    import httpx

    ts = int(time.time())
    sha = str(body.get("sha256") or "")
    sig = sign_webhook(str(body.get("job_id") or ""), sha, ts, cfg.webhook_hmac_secret)
    headers = {
        "Content-Type": "application/json",
        "X-Office-Parse-Timestamp": str(ts),
        "X-Office-Parse-Signature": sig,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(callback_url, json=body, headers=headers)
    except Exception:
        logger.warning("Parse webhook POST failed", exc_info=True)
