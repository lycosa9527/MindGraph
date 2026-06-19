"""Import smoke tests for DingTalk bind / diagram library modules."""

from __future__ import annotations

from fastapi.routing import APIRoute

from routers.api.helpers import build_public_temp_image_url
from routers.auth.dingtalk_bind import router as dingtalk_bind_router
from services.diagram.generation_library_save import (
    SAVE_LIMIT_REACHED,
    try_save_diagram_to_library,
)
from services.diagram.generation_skip_registry import store_generation_library_skip
from services.diagram.library_save_user_notices import library_save_user_notice
from services.mindbot.diagram.library_save_reply import (
    enrich_dingtalk_reply_with_library_save_notice,
)


def test_generation_library_save_importable() -> None:
    """generation_library_save exports SAVE_LIMIT_REACHED and save helper."""
    assert SAVE_LIMIT_REACHED
    assert callable(try_save_diagram_to_library)


def test_png_export_helpers_importable() -> None:
    """png export helpers module exports build_public_temp_image_url."""
    assert callable(build_public_temp_image_url)


def test_dingtalk_bind_router_importable() -> None:
    """DingTalk bind router registers start and unbind paths."""
    paths = [
        route.path for route in dingtalk_bind_router.routes if isinstance(route, APIRoute)
    ]
    assert "/dingtalk-bind/start" in paths
    assert "/dingtalk-bind/qr-code" in paths
    assert "/dingtalk-bind/unbind" in paths


def test_library_save_notice_modules_importable() -> None:
    """Library save notice helpers are importable and callable."""
    assert callable(store_generation_library_skip)
    assert callable(library_save_user_notice)
    assert callable(enrich_dingtalk_reply_with_library_save_notice)
