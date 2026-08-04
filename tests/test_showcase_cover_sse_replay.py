"""Unit tests for Showcase cover SSE last-event replay helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.showcase.covers.events import (
    LAST_EVENT_TTL_SECONDS,
    build_cover_event_payload,
    clear_cover_last_event_sync,
    cover_last_event_key,
    get_cover_last_event_sync,
    publish_showcase_cover_event_sync,
)
from services.showcase.covers.stream import (
    build_cover_ready_payload_from_post,
    select_terminal_cover_payload,
)


def _redis_available() -> bool:
    """Stub: Redis is available."""
    return True


def test_cover_last_event_key() -> None:
    """Last-event keys are namespaced per post."""
    assert cover_last_event_key("abc") == "showcase:cover:last:abc"
    assert LAST_EVENT_TTL_SECONDS >= 600


def test_publish_stores_last_event(monkeypatch) -> None:
    """Terminal publish writes Redis last-event for SSE replay."""
    stored: dict[str, object] = {}

    class FakeRedis:
        """In-memory Redis stub for publish + last-event SET."""

        def set(self, key: str, value: str, ex: int | None = None) -> bool:
            """Record SET args for assertions."""
            stored["key"] = key
            stored["value"] = value
            stored["ex"] = ex
            return True

        def publish(self, _channel: str, _payload: str) -> int:
            """Acknowledge pub/sub publish."""
            return 1

    monkeypatch.setattr(
        "services.showcase.covers.events.is_redis_available",
        _redis_available,
    )
    monkeypatch.setattr(
        "services.showcase.covers.events.get_redis",
        FakeRedis,
    )
    publish_showcase_cover_event_sync(
        "post-1",
        "cover_ready",
        thumbnail_url="/t.png",
        preview_url="/p.pdf",
    )
    assert stored["key"] == cover_last_event_key("post-1")
    assert stored["ex"] == LAST_EVENT_TTL_SECONDS
    assert "cover_ready" in str(stored["value"])


def test_get_cover_last_event_sync_decodes(monkeypatch) -> None:
    """Last-event getter returns UTF-8 payload."""
    payload = build_cover_event_payload("cover_fail", post_id="x", reason="boom")

    class FakeRedis:
        """In-memory Redis stub for GET."""

        def get(self, _key: str) -> bytes:
            """Return a fixed last-event payload."""
            return payload.encode("utf-8")

    monkeypatch.setattr(
        "services.showcase.covers.events.is_redis_available",
        _redis_available,
    )
    monkeypatch.setattr(
        "services.showcase.covers.events.get_redis",
        FakeRedis,
    )
    assert get_cover_last_event_sync("x") == payload


def test_build_cover_ready_waits_for_office_preview() -> None:
    """Office without preview_path must not emit thumb-only cover_ready."""
    post = MagicMock()
    post.id = "p1"
    post.case_type = "teaching_design"
    post.thumbnail_path = "showcase/posts/p1/thumbnail.png"
    post.spec = {"attachment_path": "showcase/posts/p1/a.docx"}
    assert build_cover_ready_payload_from_post(post) is None


def test_build_cover_ready_for_pdf_or_office_with_preview() -> None:
    """PDF thumb or Office with preview_path yields cover_ready."""
    post = MagicMock()
    post.id = "p2"
    post.case_type = "teaching_design"
    post.thumbnail_path = "showcase/posts/p2/thumbnail.png"
    post.spec = {
        "attachment_path": "showcase/posts/p2/a.docx",
        "preview_path": "showcase/posts/p2/preview.pdf",
    }
    payload = build_cover_ready_payload_from_post(post)
    assert payload is not None
    assert "cover_ready" in payload


def test_select_ignores_stale_ready_while_office_needs_preview() -> None:
    """Stale cover_ready must not short-circuit a live Office conversion."""
    post = MagicMock()
    post.id = "p3"
    post.case_type = "teaching_design"
    post.thumbnail_path = "showcase/posts/p3/thumbnail.png"
    post.spec = {"attachment_path": "showcase/posts/p3/a.docx"}
    stale_ready = build_cover_event_payload(
        "cover_ready",
        post_id="p3",
        thumbnail_url="/t.png",
        preview_url="/old.pdf",
    )
    assert select_terminal_cover_payload(post=post, last_event_payload=stale_ready) is None


def test_select_honors_fail_when_db_not_ready() -> None:
    """cover_fail from last-event is terminal when preview is still missing."""
    post = MagicMock()
    post.id = "p4"
    post.case_type = "teaching_design"
    post.thumbnail_path = None
    post.spec = {"attachment_path": "showcase/posts/p4/a.docx"}
    fail = build_cover_event_payload("cover_fail", post_id="p4", reason="lo_failed")
    assert select_terminal_cover_payload(post=post, last_event_payload=fail) == fail


def test_select_db_ready_wins_over_stale_fail() -> None:
    """Fresh DB preview beats a prior cover_fail in Redis."""
    post = MagicMock()
    post.id = "p5"
    post.case_type = "teaching_design"
    post.thumbnail_path = "showcase/posts/p5/thumbnail.png"
    post.spec = {
        "attachment_path": "showcase/posts/p5/a.docx",
        "preview_path": "showcase/posts/p5/preview.pdf",
    }
    fail = build_cover_event_payload("cover_fail", post_id="p5", reason="old")
    selected = select_terminal_cover_payload(post=post, last_event_payload=fail)
    assert selected is not None
    assert "cover_ready" in selected


def test_clear_cover_last_event_sync(monkeypatch) -> None:
    """Enqueue path can drop stale terminal replay keys."""
    deleted: list[str] = []

    class FakeRedis:
        """In-memory Redis stub for DELETE."""

        def delete(self, key: str) -> int:
            """Record deleted keys."""
            deleted.append(key)
            return 1

    monkeypatch.setattr(
        "services.showcase.covers.events.is_redis_available",
        _redis_available,
    )
    monkeypatch.setattr(
        "services.showcase.covers.events.get_redis",
        FakeRedis,
    )
    clear_cover_last_event_sync("post-z")
    assert deleted == [cover_last_event_key("post-z")]
