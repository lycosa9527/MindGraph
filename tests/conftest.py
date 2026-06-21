"""Pytest configuration shared across the test suite."""

from __future__ import annotations

from tests.stubs.redis8_features import install_redis8_features_stub

install_redis8_features_stub()


def pytest_configure(config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: live tests requiring external services (LLM, Redis)",
    )

