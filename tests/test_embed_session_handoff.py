"""Unit tests for embed session handoff helpers and path sanitization."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.embed_session_handoff import (
    append_embed_query,
    consume_embed_handoff,
    create_embed_handoff,
    sanitize_embed_next_path,
)


def test_sanitize_embed_next_allows_mindgraph() -> None:
    """Allowlisted SPA paths under /mindgraph stay unchanged."""
    assert sanitize_embed_next_path("/mindgraph") == "/mindgraph"
    assert sanitize_embed_next_path("/mindgraph/foo") == "/mindgraph/foo"


def test_sanitize_embed_next_rejects_voice_notes_for_word_handoff() -> None:
    """Word Voice uses a dedicated dialog; embed handoff no longer allows /voice-notes."""
    assert sanitize_embed_next_path("/voice-notes") == "/mindgraph"
    assert sanitize_embed_next_path("/voice-notes/") == "/mindgraph"


def test_sanitize_embed_next_rejects_open_redirect() -> None:
    """External URLs and non-allowlisted paths fall back to /mindgraph."""
    assert sanitize_embed_next_path("https://evil.example/x") == "/mindgraph"
    assert sanitize_embed_next_path("//evil.example") == "/mindgraph"
    assert sanitize_embed_next_path("/\\evil") == "/mindgraph"
    assert sanitize_embed_next_path("/admin") == "/mindgraph"


def test_append_embed_query() -> None:
    """Complete redirect paths carry embed=word-addin for SPA desktop layout."""
    assert append_embed_query("/mindgraph") == "/mindgraph?embed=word-addin"
    assert "embed=word-addin" in append_embed_query("/mindgraph?x=1")


@pytest.mark.asyncio
async def test_create_and_consume_handoff_once() -> None:
    """Handoff codes map to a user id once, then expire."""
    store: dict[str, str] = {}

    async def fake_set(key: str, value: str, _ttl: int) -> bool:
        store[key] = value
        return True

    async def fake_get_delete(key: str) -> str | None:
        return store.pop(key, None)

    with (
        patch(
            "services.auth.embed_session_handoff.AsyncRedisOps.set_with_ttl",
            new=AsyncMock(side_effect=fake_set),
        ),
        patch(
            "services.auth.embed_session_handoff.AsyncRedisOps.get_and_delete",
            new=AsyncMock(side_effect=fake_get_delete),
        ),
    ):
        code = await create_embed_handoff(42)
        assert code
        assert await consume_embed_handoff(code) == 42
        assert await consume_embed_handoff(code) is None


@pytest.mark.asyncio
async def test_consume_missing_handoff() -> None:
    """Unknown or already-consumed codes return None."""
    with patch(
        "services.auth.embed_session_handoff.AsyncRedisOps.get_and_delete",
        new=AsyncMock(return_value=None),
    ):
        assert await consume_embed_handoff("missing-code") is None
