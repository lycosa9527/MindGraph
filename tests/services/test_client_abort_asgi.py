"""Client abort must not escape the ASGI app as an unhandled crash."""

from __future__ import annotations

import pytest
from starlette.requests import ClientDisconnect
from starlette.testclient import TestClient
from uvicorn.protocols.utils import ClientDisconnected

from services.infrastructure.http.client_abort import MindGraphFastAPI, is_client_abort
from services.infrastructure.http.exception_handlers import setup_exception_handlers


def test_is_client_abort_matches_starlette_no_response() -> None:
    """The middleware message is an abort; other runtime errors are not."""
    assert is_client_abort(RuntimeError("No response returned."))
    assert is_client_abort(ClientDisconnect())
    assert is_client_abort(ClientDisconnected())
    assert not is_client_abort(RuntimeError("database connection failed"))


def test_client_abort_returns_204_and_does_not_raise() -> None:
    """ServerErrorMiddleware re-raises; the app must swallow that re-raise."""
    app = MindGraphFastAPI()
    setup_exception_handlers(app)

    @app.middleware("http")
    async def drop_response(_request, _call_next):
        raise RuntimeError("No response returned.")

    @app.get("/gone")
    async def gone() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/gone")

    assert response.status_code == 204


def test_real_runtime_error_still_propagates() -> None:
    """Swallowing is limited to the client-abort shape."""
    app = MindGraphFastAPI()
    setup_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> dict[str, bool]:
        raise RuntimeError("database connection failed")

    with pytest.raises(RuntimeError, match="database connection failed"):
        TestClient(app).get("/boom")
