"""
Root pytest configuration: load `.env.test` for all tests under `tests/`.
"""

from __future__ import annotations

import pytest

from tests.env_test import ENV_TEST_FILE, get_e2e_config, load_env_test


def pytest_configure(config: pytest.Config) -> None:
    """Load test env before any test module reads os.environ at import time."""
    if not load_env_test():
        config.issue_config_time_warning(
            pytest.PytestConfigWarning(
                f"Test env file not found: {ENV_TEST_FILE}. "
                "Copy .env.test.example to .env.test for E2E and integration tests."
            ),
            stacklevel=2,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    ADR-021: skip entire e2e package when DocumentServer is unreachable.

    Unit tests (`-m "not e2e"`) are unaffected.
    """
    from tests.office_mcp.e2e_support import documentserver_reachable

    if documentserver_reachable():
        return

    skip = pytest.mark.skip(
        reason=(
            "DocumentServer not reachable (DOCUMENTSERVER_URL from .env.test). "
            "Skipping e2e tests (ADR-021)."
        )
    )
    for item in items:
        if item.get_closest_marker("e2e"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def e2e_config():
    """Session-scoped E2E settings from `.env.test`."""
    return get_e2e_config()
