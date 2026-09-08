"""Parse security gates (ADR-048)."""

import time

import pytest

from aiecs.config.config import get_parse_job_config
from aiecs.tools.office_tool.core.parse_security import (
    output_path_allowed,
    secrets_equal,
    hash_secret,
    structure_sidecar_path,
    verify_webhook_signature,
    sign_webhook,
    webhook_url_allowed,
)


@pytest.fixture
def parse_cfg(monkeypatch):
    monkeypatch.setenv("PARSE_OUTPUT_ALLOWED_PREFIXES", "s3://allowed/derived/,gs://ok/out/")
    monkeypatch.setenv("PARSE_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("PARSE_WEBHOOK_ALLOWED_HOSTS", "hooks.scholar-kg.example")
    monkeypatch.setenv("PARSE_WEBHOOK_HMAC_SECRET", "supersecret")
    get_parse_job_config.cache_clear()
    yield
    get_parse_job_config.cache_clear()


def test_output_path_allowlist(parse_cfg):
    assert output_path_allowed("s3://allowed/derived/e/canonical.md") is None
    assert output_path_allowed("s3://other-user/workspace/x.md") is not None
    assert output_path_allowed("s3://allowed/derived/e/canonical.md", "s3://allowed/derived/e/canonical.md") is not None


def test_empty_prefixes_fail_closed(monkeypatch):
    monkeypatch.setenv("PARSE_OUTPUT_ALLOWED_PREFIXES", "")
    get_parse_job_config.cache_clear()
    assert output_path_allowed("s3://allowed/derived/e/canonical.md") is not None
    get_parse_job_config.cache_clear()


def test_structure_sidecar_name():
    assert structure_sidecar_path("s3://b/derived/e/canonical.md") == "s3://b/derived/e/canonical.structure.json"


def test_webhook_http_and_metadata(parse_cfg):
    assert webhook_url_allowed("http://hooks.scholar-kg.example/cb", resolve_dns=False) is not None
    assert webhook_url_allowed("https://169.254.169.254/x", resolve_dns=False) is not None
    assert webhook_url_allowed("https://metadata.google.internal/x", resolve_dns=False) is not None
    assert webhook_url_allowed("https://hooks.scholar-kg.example/cb", resolve_dns=False) is None


def test_webhook_empty_hosts_fail_closed(monkeypatch):
    monkeypatch.setenv("PARSE_WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("PARSE_WEBHOOK_ALLOWED_HOSTS", "")
    monkeypatch.setenv("PARSE_WEBHOOK_HMAC_SECRET", "x")
    get_parse_job_config.cache_clear()
    assert webhook_url_allowed("https://hooks.scholar-kg.example/cb", resolve_dns=False) is not None
    get_parse_job_config.cache_clear()


def test_hmac_window():
    secret = "k"
    ts = int(time.time())
    sig = sign_webhook("jid", "abc", ts, secret)
    assert verify_webhook_signature("jid", "abc", ts, sig, secret, 300)
    assert not verify_webhook_signature("jid", "abc", ts - 400, sig, secret, 300)


def test_compare_digest_secrets():
    h = hash_secret("abc")
    assert secrets_equal("abc", h)
    assert not secrets_equal("abd", h)


def test_webhook_rfc1918_at_post_time(parse_cfg, monkeypatch):
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.parse_security.socket.getaddrinfo",
        lambda *a, **k: [(0, 0, 0, "", ("10.0.0.8", 443))],
    )
    assert webhook_url_allowed("https://hooks.scholar-kg.example/cb", resolve_dns=True) is not None


def test_webhook_mapped_ipv6_metadata(parse_cfg, monkeypatch):
    monkeypatch.setattr(
        "aiecs.tools.office_tool.core.parse_security.socket.getaddrinfo",
        lambda *a, **k: [(0, 0, 0, "", ("::ffff:169.254.169.254", 443))],
    )
    assert webhook_url_allowed("https://hooks.scholar-kg.example/cb", resolve_dns=True) is not None


def test_webhook_non_allowlist_host(parse_cfg):
    assert webhook_url_allowed("https://evil.example/cb", resolve_dns=False) is not None
