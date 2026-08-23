"""Request-scoped log user identity for backend log lines."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from services.infrastructure.http.middleware import auth_context_middleware
from services.infrastructure.utils.log_user_context import (
    bind_log_user,
    display_name_for_log,
    format_log_user_suffix,
    reset_log_user,
)
from services.infrastructure.utils.logging_config import UnifiedFormatter
from services.monitoring.log_streamer import LogStreamer


def test_display_name_prefers_profile_name() -> None:
    """Profile name wins over phone and email."""
    user = SimpleNamespace(id=7, name="  Roy  ", phone="13800138000", email="a@b.com")
    assert display_name_for_log(user) == "Roy"


def test_display_name_falls_back_to_phone() -> None:
    """Phone is used when the profile name is empty."""
    user = SimpleNamespace(id=7, name="  ", phone="13800138000", email="a@b.com")
    assert display_name_for_log(user) == "13800138000"


def test_display_name_strips_controls_and_pipes() -> None:
    """Control characters and pipes cannot break the log layout."""
    user = SimpleNamespace(id=7, name="Roy\n|\tWei", phone=None, email=None)
    assert display_name_for_log(user) == "Roy / Wei"


def test_format_suffix_includes_name_and_id() -> None:
    """Bound users render as user=Name(id)."""
    tokens = bind_log_user(SimpleNamespace(id=42, name="赵国庆", phone=None, email=None))
    try:
        assert format_log_user_suffix() == " user=赵国庆(42)"
    finally:
        reset_log_user(tokens)
    assert format_log_user_suffix() == ""


def test_format_suffix_id_only_when_name_missing() -> None:
    """Id-only suffix when no name, phone, or email is present."""
    tokens = bind_log_user(SimpleNamespace(id=9, name=None, phone=None, email=None))
    try:
        assert format_log_user_suffix() == " user=9"
    finally:
        reset_log_user(tokens)


def test_unified_formatter_appends_bound_user() -> None:
    """UnifiedFormatter inserts the actor between pid and message."""
    record = logging.LogRecord(
        name="services.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="[Auth] probe",
        args=(),
        exc_info=None,
    )
    tokens = bind_log_user(SimpleNamespace(id=3, name="Roy", phone=None, email=None))
    try:
        formatted = UnifiedFormatter(use_colors=False).format(record)
    finally:
        reset_log_user(tokens)
    assert "] INFO  | SERV | [" in formatted
    assert " user=Roy(3) [Auth] probe" in formatted


def test_auth_middleware_resets_log_user_after_handler_error() -> None:
    """A route exception must not leak the actor onto the next log line."""
    app = FastAPI()
    app.middleware("http")(auth_context_middleware)

    @app.get("/api/boom")
    async def api_boom() -> PlainTextResponse:
        raise RuntimeError("boom")

    user = SimpleNamespace(id=7, name="Roy", phone=None, email=None)
    with patch(
        "services.infrastructure.http.middleware.resolve_authenticated_user_optional",
        AsyncMock(return_value=user),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/boom")
    assert response.status_code == 500
    assert format_log_user_suffix() == ""


def test_admin_log_parser_keeps_unified_line() -> None:
    """Admin log viewer still parses lines after the user token is inserted."""
    tokens = bind_log_user(SimpleNamespace(id=3, name="Roy", phone=None, email=None))
    try:
        record = logging.LogRecord(
            name="services.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="[Auth] probe",
            args=(),
            exc_info=None,
        )
        line = UnifiedFormatter(use_colors=False).format(record)
    finally:
        reset_log_user(tokens)
    parsed = LogStreamer().parse_log_line(line, "app")
    assert parsed is not None
    assert parsed["level"] == "INFO"
    assert parsed["module"] == "SERV"
    assert "user=Roy(3)" in parsed["message"]
    assert "[Auth] probe" in parsed["message"]


def test_auth_middleware_binds_and_resets_log_user() -> None:
    """HTTP auth middleware pins the actor for the request and clears it after."""
    seen: dict[str, str] = {}
    app = FastAPI()
    app.middleware("http")(auth_context_middleware)

    @app.get("/api/ping")
    async def api_ping() -> PlainTextResponse:
        seen["suffix"] = format_log_user_suffix()
        return PlainTextResponse("pong")

    user = SimpleNamespace(id=7, name="Roy", phone=None, email=None)
    with patch(
        "services.infrastructure.http.middleware.resolve_authenticated_user_optional",
        AsyncMock(return_value=user),
    ):
        client = TestClient(app)
        response = client.get("/api/ping")
    assert response.status_code == 200
    assert seen["suffix"] == " user=Roy(7)"
    assert format_log_user_suffix() == ""
