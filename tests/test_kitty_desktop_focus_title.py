"""Desktop focus push carries library title so the watch chip can rematch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.infra.desktop.kitty_desktop_focus_push import (
    _focus_body,
    notify_kitty_desktop_focus_changed,
    resolve_desktop_focus_library_meta,
)


def test_focus_body_includes_title_and_type() -> None:
    """Watch/mobile payload includes trimmed title + type."""
    body = _focus_body("lib-1", 100, title="  新建思维导图  ", diagram_type="mindmap")
    assert body["type"] == "desktop_focus_update"
    assert body["diagram_library_id"] == "lib-1"
    assert body["title"] == "新建思维导图"
    assert body["diagram_type"] == "mindmap"


def test_focus_body_omits_blank_meta() -> None:
    """Empty title/type stay off the wire."""
    body = _focus_body("lib-1", 100, title="  ", diagram_type=None)
    assert "title" not in body
    assert "diagram_type" not in body


@pytest.mark.asyncio
async def test_resolve_desktop_focus_library_meta() -> None:
    """Library cache title is what the watch chip shows after rematch."""
    cache = AsyncMock()
    cache.get_diagram = AsyncMock(return_value={"title": "办公室", "diagram_type": "mindmap"})
    with patch(
        "services.kitty.infra.desktop.kitty_desktop_focus_push.get_diagram_cache",
        return_value=cache,
    ):
        title, dtype = await resolve_desktop_focus_library_meta(7, "abc")
    assert title == "办公室"
    assert dtype == "mindmap"
    cache.get_diagram.assert_awaited_once_with(7, "abc")


@pytest.mark.asyncio
async def test_notify_focus_pushes_resolved_title() -> None:
    """PUT notify looks up the library row and fans title to mobile sockets."""
    with (
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.resolve_desktop_focus_library_meta",
            AsyncMock(return_value=("办公室", "mindmap")),
        ),
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.push_kitty_desktop_focus_to_local_mobile",
            AsyncMock(return_value=1),
        ) as push,
        patch(
            "services.kitty.infra.desktop.kitty_desktop_focus_push.publish_desktop_focus_relay",
            AsyncMock(return_value=True),
        ) as relay,
    ):
        await notify_kitty_desktop_focus_changed(3, "lib-saved", 1_700_000_000)
    push.assert_awaited_once_with(
        3,
        "lib-saved",
        1_700_000_000,
        title="办公室",
        diagram_type="mindmap",
    )
    relay.assert_awaited_once_with(
        3,
        "lib-saved",
        1_700_000_000,
        title="办公室",
        diagram_type="mindmap",
    )
