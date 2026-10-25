"""Headless PNG clicks empty pane chrome, not the fitted diagram."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request

from routers.api import vueflow_screenshot as screenshot_mod
from routers.api.vueflow_screenshot import pane_empty_click_point
from services.infrastructure.http import exception_handlers as handlers


def test_pane_empty_click_is_inset_not_center() -> None:
    """Fit-view parks nodes in the middle; the click must stay in the corner."""
    box = {"x": 100.0, "y": 40.0, "width": 1200.0, "height": 800.0}
    click_x, click_y = pane_empty_click_point(box)
    assert click_x == 112.0
    assert click_y == 52.0
    assert click_x < box["x"] + box["width"] / 2
    assert click_y < box["y"] + box["height"] / 2


@pytest.mark.asyncio
async def test_playwright_timeout_becomes_diagram_screenshot_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Playwright timeout is a diagram-unavailable error, not a RuntimeError."""

    def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    async def _async_noop(*_args: object, **_kwargs: object) -> None:
        return None

    async def _new_page() -> SimpleNamespace:
        return SimpleNamespace(
            set_default_timeout=_noop,
            set_default_navigation_timeout=_noop,
            set_viewport_size=_async_noop,
            on=_noop,
        )

    def _browser() -> AbstractAsyncContextManager[SimpleNamespace]:
        @asynccontextmanager
        async def _open() -> AsyncIterator[SimpleNamespace]:
            yield SimpleNamespace(new_page=_new_page)

        return _open()

    async def _navigate(*_args: object, **_kwargs: object) -> None:
        raise screenshot_mod.PlaywrightTimeoutError("waiting for element to be stable")

    monkeypatch.setattr(screenshot_mod, "BrowserContextManager", _browser)
    monkeypatch.setattr(screenshot_mod, "_inject_spec_and_navigate", _navigate)

    with pytest.raises(screenshot_mod.DiagramScreenshotError):
        await screenshot_mod.capture_diagram_screenshot({"topic": "光合作用"}, "mind_map")


@pytest.mark.asyncio
async def test_diagram_screenshot_handler_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dedicated handler answers 503 at error severity, so it does not page SMS."""
    recorded: dict[str, object] = {}

    def _record(*_args: object, **kwargs: object) -> None:
        recorded.update(kwargs)

    monkeypatch.setattr(handlers, "record_exception", _record)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/export/png"),
        state=SimpleNamespace(request_id="req-1"),
    )
    response = await handlers.diagram_screenshot_handler(
        cast(Request, request),
        handlers.DiagramScreenshotError("timed out"),
    )
    assert response.status_code == 503
    assert json.loads(bytes(response.body))["detail"] == "Diagram image is not ready. Try again."
    assert recorded["severity"] == "error"
    assert recorded["http_status"] == 503
