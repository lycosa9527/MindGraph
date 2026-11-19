"""Canvas remote queue: glasses push, the open editor drains."""

from services.learning_space.glasses_contract import REMOTE_DISPLAY, normalize_remote_action
from services.learning_space.glasses_remote import (
    MAX_QUEUED,
    push_remote_action,
    remote_key,
    take_remote_actions,
)


class _FakeRedis:
    """List operations the remote queue uses."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.ttl: dict[str, int] = {}

    def rpush(self, key: str, value: str) -> None:
        """Append one action."""
        self.lists.setdefault(key, []).append(value)

    def ltrim(self, key: str, start: int, end: int) -> None:
        """Keep the inclusive slice, with Redis-style negative indexes."""
        row = self.lists.get(key, [])
        count = len(row)
        begin = start + count if start < 0 else start
        finish = end + count if end < 0 else end
        self.lists[key] = row[max(0, begin) : finish + 1]

    def expire(self, key: str, seconds: int) -> None:
        """Record the TTL the queue sets."""
        self.ttl[key] = seconds

    def lrange(self, key: str, _start: int, _end: int) -> list[str]:
        """Return the stored actions."""
        return list(self.lists.get(key, []))

    def delete(self, key: str) -> None:
        """Drop the list."""
        self.lists.pop(key, None)


def test_unknown_remote_action_is_rejected() -> None:
    """Only the pad's seven nudges are queued."""
    assert normalize_remote_action("zoom_in") == "zoom_in"
    assert normalize_remote_action(" delete ") == ""
    assert push_remote_action(_FakeRedis(), 4, "spin") is False


def test_queue_keeps_order_and_clears_on_drain() -> None:
    """The editor applies the oldest nudge first, then the list is gone."""
    redis = _FakeRedis()
    assert push_remote_action(redis, 7, "pan_left") is True
    assert push_remote_action(redis, 7, "fit") is True
    assert take_remote_actions(redis, 7) == ["pan_left", "fit"]
    assert not take_remote_actions(redis, 7)
    assert redis.ttl[remote_key(7)] == 20
    assert REMOTE_DISPLAY["fit"] == "适应画面"


def test_queue_drops_the_oldest_past_the_cap() -> None:
    """A stuck editor does not accumulate an unbounded list."""
    redis = _FakeRedis()
    for _ in range(MAX_QUEUED + 2):
        push_remote_action(redis, 3, "pan_up")
    assert len(take_remote_actions(redis, 3)) == MAX_QUEUED


def test_bytes_from_redis_are_decoded() -> None:
    """A client without decode_responses still yields action names."""

    class _BytesRedis(_FakeRedis):
        """Returns the raw bytes a Redis client emits without decode_responses."""

        def lrange(self, key: str, _start: int, _end: int) -> list[bytes]:
            """Encode stored actions the way Redis would."""
            return [item.encode("utf-8") for item in self.lists.get(key, [])]

    redis = _BytesRedis()
    push_remote_action(redis, 1, "zoom_out")
    assert take_remote_actions(redis, 1) == ["zoom_out"]
