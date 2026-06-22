"""
Shared test environment loading from repository `.env.test`.

All pytest sessions load `.env.test` via `tests/conftest.py` before test modules
import. E2E helpers read variables after that load (with legacy alias fallbacks).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_TEST_FILE = REPO_ROOT / ".env.test"

_loaded = False


def load_env_test(*, override: bool = False) -> bool:
    """Load `.env.test` into os.environ. Returns True if file existed."""
    global _loaded
    if _loaded and not override:
        return ENV_TEST_FILE.is_file()

    from dotenv import load_dotenv

    if ENV_TEST_FILE.is_file():
        load_dotenv(ENV_TEST_FILE, override=override)
        _loaded = True
        apply_e2e_env_overrides()
        return True

    _loaded = True
    return False


def _first_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return default


def apply_e2e_env_overrides() -> None:
    """
    Apply E2E-specific overrides from `.env.test` into process env.

    E2E_MCP_PUBLIC_URL → MCP_PUBLIC_URL so DocumentServer can fetch docbuilder scripts
    during E2E (must be DS-reachable; docker service names are not).
    """
    mcp_public = _first_env("E2E_MCP_PUBLIC_URL")
    if mcp_public:
        os.environ["MCP_PUBLIC_URL"] = mcp_public


@dataclass(frozen=True)
class E2EConfig:
    """E2E settings from environment (post `.env.test` load)."""

    documentserver_url: str
    documentserver_jwt_secret: str
    mcp_url: str
    source_path: str
    source_paths: str
    template_path: str
    docbuilder_url: str
    mcp_public_url: str
    docbuilder_script_gcs_path: str

    @property
    def has_jwt(self) -> bool:
        return bool(self.documentserver_jwt_secret)

    @property
    def has_source_path(self) -> bool:
        return bool(self.source_path) and (
            self.source_path.startswith("gs://") or self.source_path.startswith("s3://")
        )

    @property
    def has_source_paths(self) -> bool:
        return bool(self.source_paths.strip())

    @property
    def has_template_path(self) -> bool:
        return bool(self.template_path) and (
            self.template_path.startswith("gs://") or self.template_path.startswith("s3://")
        )

    @property
    def has_script_to_url(self) -> bool:
        mcp = self.mcp_public_url
        gcs = self.docbuilder_script_gcs_path
        return bool(mcp.startswith("http")) or bool(gcs.startswith("gs://"))

    @property
    def minio_source_path(self) -> str:
        return _first_env(
            "E2E_MINIO_SOURCE_PATH",
            "E2E_S3_SOURCE_PATH",
            "E2E_SOURCE_PATH",
            "E2E_GCS_SOURCE_PATH",
        )


@lru_cache(maxsize=1)
def get_e2e_config() -> E2EConfig:
    load_env_test()
    port = os.environ.get("MCP_PORT", "5040").strip() or "5040"
    default_mcp = f"http://127.0.0.1:{port}"
    return E2EConfig(
        documentserver_url=_first_env("DOCUMENTSERVER_URL"),
        documentserver_jwt_secret=_first_env("DOCUMENTSERVER_JWT_SECRET"),
        mcp_url=_first_env("E2E_MCP_URL", "MCP_BASE_URL", default=default_mcp).rstrip("/"),
        source_path=_first_env(
            "E2E_SOURCE_PATH",
            "E2E_S3_SOURCE_PATH",
            "E2E_MINIO_SOURCE_PATH",
            "E2E_GCS_SOURCE_PATH",
        ),
        source_paths=_first_env(
            "E2E_SOURCE_PATHS",
            "E2E_S3_SOURCE_PATHS",
            "E2E_GCS_SOURCE_PATHS",
        ),
        template_path=_first_env(
            "E2E_TEMPLATE_PATH",
            "E2E_S3_TEMPLATE_PATH",
            "E2E_GCS_TEMPLATE_PATH",
        ),
        docbuilder_url=_first_env("E2E_DOCBUILDER_URL"),
        mcp_public_url=_first_env("MCP_PUBLIC_URL"),
        docbuilder_script_gcs_path=_first_env("DOCBUILDER_SCRIPT_GCS_PATH"),
    )
