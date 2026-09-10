"""Pytest configuration shared across the test suite."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from tests.stubs.redis8_features import install_redis8_features_stub

install_redis8_features_stub()
importlib.import_module("models.domain.registry")


def pytest_configure(config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: live tests requiring external services (LLM, Redis)",
    )


@pytest.fixture(autouse=True)
def isolate_pending_kitty_redis(request: pytest.FixtureRequest) -> Iterator[None]:
    """Keep unit tests from writing armed Kitty picks into the shared Redis."""
    if request.node.get_closest_marker("integration"):
        yield
        return
    with patch(
        "services.kitty.routing.pending_clarify_store.get_async_redis",
        return_value=None,
    ):
        yield
