"""Redis session state machine for org training follow."""

from __future__ import annotations

import json
import time
from typing import Any, Optional
from unittest.mock import patch

import pytest

from services.features.training.constants import ORG_SESSION_KEY
from services.features.training.session_store import (
    TrainingSessionError,
    get_session,
    heartbeat,
    maybe_auto_pause,
    pause_session,
    require_owner_active,
    resume_session,
    start_session,
    takeover_session,
)


class FakePipeline:
    """Collects Redis writes then applies them."""

    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.ops: list[tuple] = []

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        """Queue a SET."""
        self.ops.append(("set", key, value, ex))

    def hset(self, key: str, field: str, value: str) -> None:
        """Queue an HSET."""
        self.ops.append(("hset", key, field, value))

    def expire(self, key: str, ttl: int) -> None:
        """Queue an EXPIRE."""
        self.ops.append(("expire", key, ttl))

    async def execute(self) -> list[None]:
        """Apply queued writes."""
        for op in self.ops:
            if op[0] == "set":
                await self.redis.set(op[1], op[2], ex=op[3])
            elif op[0] == "hset":
                await self.redis.hset(op[1], op[2], op[3])
            elif op[0] == "expire":
                await self.redis.expire(op[1], op[2])
        return [None] * len(self.ops)

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class FakeRedis:
    """In-memory stand-in for the async Redis client."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.published: list[tuple[str, str]] = []

    async def get(self, key: str) -> Optional[str]:
        """Return a string value."""
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Store a string value. TTL is ignored in tests."""
        del ex
        self.values[key] = value
        return True

    async def delete(self, key: str) -> int:
        """Delete one key."""
        existed = int(key in self.values)
        self.values.pop(key, None)
        return existed

    async def publish(self, channel: str, message: str) -> int:
        """Record a pub/sub message."""
        self.published.append((channel, message))
        return 1

    async def hset(self, key: str, field: str, value: str) -> int:
        """Write one hash field."""
        self.hashes.setdefault(key, {})[str(field)] = value
        return 1

    async def hgetall(self, key: str) -> dict[str, str]:
        """Return a hash copy."""
        return dict(self.hashes.get(key, {}))

    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        bucket = self.hashes.get(key, {})
        removed = 0
        for field in fields:
            if str(field) in bucket:
                del bucket[str(field)]
                removed += 1
        return removed

    async def expire(self, key: str, ttl: int) -> bool:
        """Pretend to set a TTL."""
        del key
        return bool(ttl)

    def pipeline(self, transaction: bool = False) -> FakePipeline:
        """Open a non-transactional pipeline."""
        del transaction
        return FakePipeline(self)


def _patch_redis(redis: FakeRedis) -> Any:
    return patch(
        "services.features.training.session_store.get_async_redis",
        return_value=redis,
    )


@pytest.mark.asyncio
async def test_start_rejects_second_session_for_org() -> None:
    """One live-or-paused session per org."""
    redis = FakeRedis()
    with _patch_redis(redis):
        first = await start_session(
            org_id=7,
            instructor_id=1,
            instructor_name="Ada",
            confirm_teacher_total=20,
        )
        with pytest.raises(TrainingSessionError) as exc:
            await start_session(
                org_id=7,
                instructor_id=2,
                instructor_name="Bea",
                confirm_teacher_total=20,
            )
        assert exc.value.code == "org_busy"
        assert exc.value.extras.get("instructor_name") == "Ada"
        assert first["state"] == "live"


@pytest.mark.asyncio
async def test_instructor_cannot_host_second_org() -> None:
    """An instructor may host only one session globally."""
    redis = FakeRedis()
    with _patch_redis(redis):
        await start_session(
            org_id=1,
            instructor_id=5,
            instructor_name="Ada",
            confirm_teacher_total=3,
        )
        with pytest.raises(TrainingSessionError) as exc:
            await start_session(
                org_id=2,
                instructor_id=5,
                instructor_name="Ada",
                confirm_teacher_total=4,
            )
        assert exc.value.code == "instructor_busy"


@pytest.mark.asyncio
async def test_heartbeat_loss_pauses_and_resume_keeps_id() -> None:
    """Stale heartbeat pauses; the same instructor resumes the same session."""
    redis = FakeRedis()
    with _patch_redis(redis):
        session = await start_session(
            org_id=3,
            instructor_id=8,
            instructor_name="Ada",
            confirm_teacher_total=12,
        )
        session_id = session["session_id"]
        seq = int(session["seq"])
        session["instructor_seen_at"] = time.time() - 200
        paused = await maybe_auto_pause(session)
        assert paused["state"] == "paused"
        assert paused["session_id"] == session_id
        assert int(paused["seq"]) == seq + 1
        resumed = await resume_session(3, 8)
        assert resumed["session_id"] == session_id
        assert resumed["state"] == "live"
        assert int(resumed["seq"]) == seq + 2


@pytest.mark.asyncio
async def test_takeover_transfers_owner() -> None:
    """Takeover keeps seq/snapshot; the old instructor cannot steer."""
    redis = FakeRedis()
    with _patch_redis(redis):
        session = await start_session(
            org_id=4,
            instructor_id=1,
            instructor_name="Ada",
            confirm_teacher_total=9,
        )
        seq = int(session["seq"])
        updated = await takeover_session(4, 99, "Bea")
        assert updated["instructor_id"] == 99
        assert updated["instructor_name"] == "Bea"
        assert updated["taken_over_from"] == 1
        assert int(updated["seq"]) == seq + 1
        with pytest.raises(TrainingSessionError) as exc:
            await require_owner_active(4, 1)
        assert exc.value.code == "not_owner"


@pytest.mark.asyncio
async def test_hard_ttl_ends_session() -> None:
    """Expired sessions become ended tombstones."""
    redis = FakeRedis()
    with _patch_redis(redis):
        session = await start_session(
            org_id=5,
            instructor_id=2,
            instructor_name="Ada",
            confirm_teacher_total=2,
        )
        session["expires_at"] = time.time() - 1
        await redis.set(ORG_SESSION_KEY.format(org_id=5), json.dumps(session))
        got = await get_session(5)
        assert got is not None
        assert got["state"] == "ended"


@pytest.mark.asyncio
async def test_pause_resume_and_heartbeat_owner() -> None:
    """Owner pause/resume and heartbeat refresh seen_at."""
    redis = FakeRedis()
    with _patch_redis(redis):
        await start_session(
            org_id=6,
            instructor_id=3,
            instructor_name="Ada",
            confirm_teacher_total=1,
        )
        paused = await pause_session(6, 3)
        assert paused["state"] == "paused"
        beat = await heartbeat(6, 3)
        assert beat is not None
        assert float(beat["instructor_seen_at"]) > 0
        live = await resume_session(6, 3)
        assert live["state"] == "live"
