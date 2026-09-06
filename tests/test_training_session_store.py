"""Redis session state machine for org training follow."""

from __future__ import annotations

import json
import time
from typing import Any, Optional
from unittest.mock import patch

import pytest

from services.features.training.constants import ORG_SESSION_KEY
from services.features.training.session_cas import CAS_WRITE_LUA, CLAIM_ORG_LUA
from services.features.training.session_store import (
    TrainingSessionError,
    bump_and_save,
    get_session,
    heartbeat,
    pause_session,
    present_session,
    require_owner_active,
    resume_session,
    start_session,
    takeover_session,
)
from services.features.training.session_view import audience_view


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

    def delete(self, *keys: str) -> None:
        """Queue a DELETE."""
        self.ops.append(("delete", keys))

    async def execute(self) -> list[None]:
        """Apply queued writes."""
        for op in self.ops:
            if op[0] == "set":
                await self.redis.set(op[1], op[2], ex=op[3])
            elif op[0] == "hset":
                await self.redis.hset(op[1], op[2], op[3])
            elif op[0] == "expire":
                await self.redis.expire(op[1], op[2])
            elif op[0] == "delete":
                await self.redis.delete(*op[1])
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

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        """Store a string value. TTL is ignored in tests."""
        del ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        """Run the training claim / CAS scripts in memory."""
        keys = list(keys_and_args[:numkeys])
        argv = list(keys_and_args[numkeys:])
        if script == CLAIM_ORG_LUA:
            return await self._eval_claim(keys, argv)
        if script == CAS_WRITE_LUA:
            return await self._eval_cas(keys, argv)
        raise NotImplementedError("unsupported eval script")

    async def _eval_claim(self, keys: list[str], argv: list[str]) -> int:
        org_key, inst_key = keys
        payload, pointer, ttl, now, inst_prefix = argv
        current = self.values.get(org_key)
        if current:
            parsed = json.loads(current)
            state = parsed.get("state")
            expires = float(parsed.get("expires_at") or 0)
            blocking = state in {"live", "paused"} and (expires == 0 or expires > float(now))
            if blocking:
                return 0
            old_id = parsed.get("instructor_id")
            if old_id:
                await self.delete(f"{inst_prefix}{old_id}")
        await self.set(org_key, payload, ex=int(ttl))
        await self.set(inst_key, pointer, ex=int(ttl))
        return 1

    async def _eval_cas(self, keys: list[str], argv: list[str]) -> int:
        org_key, inst_key = keys
        expected, payload, pointer, ttl, write_pointer = argv
        current = self.values.get(org_key)
        if current is None:
            return 0
        parsed = json.loads(current)
        if int(parsed.get("seq") or 0) != int(expected):
            return 0
        await self.set(org_key, payload, ex=int(ttl))
        if int(write_pointer):
            await self.set(inst_key, pointer, ex=int(ttl))
        return 1

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        removed = 0
        for key in keys:
            existed = int(key in self.values)
            self.values.pop(key, None)
            removed += existed
        return removed

    async def publish(self, channel: str, message: str) -> int:
        """Record a pub/sub message."""
        self.published.append((channel, message))
        return 1

    async def hset(self, key: str, field: str, value: str) -> int:
        """Write one hash field."""
        self.hashes.setdefault(key, {})[str(field)] = value
        return 1

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Return one hash field."""
        bucket = self.hashes.get(key, {})
        return bucket.get(str(field))

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
        assert first["pull_users"] is False
        assert first.get("course_id") is None


@pytest.mark.asyncio
async def test_two_orgs_can_train_at_once() -> None:
    """Different schools keep independent live sessions."""
    redis = FakeRedis()
    with _patch_redis(redis):
        first = await start_session(
            org_id=1,
            instructor_id=1,
            instructor_name="Ada",
            confirm_teacher_total=3,
        )
        second = await start_session(
            org_id=2,
            instructor_id=2,
            instructor_name="Bea",
            confirm_teacher_total=4,
        )
        assert first["session_id"] != second["session_id"]
        left = await get_session(1)
        right = await get_session(2)
        assert left is not None
        assert right is not None
        assert left["instructor_id"] == 1
        assert right["instructor_id"] == 2


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
    """Stale heartbeat persists pause once; the same instructor resumes."""
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
        paused, wrote = await present_session(session)
        assert wrote is True
        assert paused["state"] == "paused"
        assert paused["session_id"] == session_id
        assert int(paused["seq"]) == seq + 1
        again, wrote_again = await present_session(paused)
        assert wrote_again is False
        assert int(again["seq"]) == seq + 1
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
async def test_get_session_does_not_write_on_expiry() -> None:
    """Hard TTL is a read-only view until present_session persists."""
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
        assert got["state"] == "live"
        assert audience_view(got)["state"] == "ended"
        ended, wrote = await present_session(got)
        assert wrote is True
        assert ended["state"] == "ended"
        stored = await get_session(5)
        assert stored is not None
        assert stored["state"] == "ended"


@pytest.mark.asyncio
async def test_start_overwrites_expired_session() -> None:
    """Claim treats an expired live document as free."""
    redis = FakeRedis()
    with _patch_redis(redis):
        first = await start_session(
            org_id=5,
            instructor_id=2,
            instructor_name="Ada",
            confirm_teacher_total=2,
        )
        first["expires_at"] = time.time() - 1
        await redis.set(ORG_SESSION_KEY.format(org_id=5), json.dumps(first))
        second = await start_session(
            org_id=5,
            instructor_id=9,
            instructor_name="Bea",
            confirm_teacher_total=2,
        )
        assert second["instructor_id"] == 9
        assert second["session_id"] != first["session_id"]
        assert second["state"] == "live"


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


@pytest.mark.asyncio
async def test_steer_cas_rejects_stale_seq() -> None:
    """A second steer with the same loaded seq loses to the first write."""
    redis = FakeRedis()
    with _patch_redis(redis):
        first = await start_session(
            org_id=8,
            instructor_id=4,
            instructor_name="Ada",
            confirm_teacher_total=2,
        )
        stale = dict(first)
        await bump_and_save(first, extra={"pull_users": True}, rate_limit_steer=True)
        with pytest.raises(TrainingSessionError) as exc:
            await bump_and_save(stale, extra={"pull_users": False}, rate_limit_steer=True)
        assert exc.value.code == "seq_conflict"
        current = await get_session(8)
        assert current is not None
        assert current["pull_users"] is True


@pytest.mark.asyncio
async def test_present_session_gate_blocks_second_writer() -> None:
    """A second stale reader loses the SET NX gate and does not bump seq again."""
    redis = FakeRedis()
    with _patch_redis(redis):
        session = await start_session(
            org_id=11,
            instructor_id=6,
            instructor_name="Ada",
            confirm_teacher_total=2,
        )
        seq = int(session["seq"])
        stale = dict(session)
        stale["instructor_seen_at"] = time.time() - 200
        first, wrote = await present_session(dict(stale))
        second, wrote_again = await present_session(dict(stale))
        assert wrote is True
        assert first["state"] == "paused"
        assert int(first["seq"]) == seq + 1
        assert wrote_again is False
        assert second["state"] == "paused"
        assert int(second["seq"]) == seq
        stored = await get_session(11)
        assert stored is not None
        assert stored["state"] == "paused"
        assert int(stored["seq"]) == seq + 1


@pytest.mark.asyncio
async def test_stale_view_does_not_write() -> None:
    """Audience view is paused without bumping seq when nobody persists."""
    redis = FakeRedis()
    with _patch_redis(redis):
        session = await start_session(
            org_id=9,
            instructor_id=5,
            instructor_name="Ada",
            confirm_teacher_total=2,
        )
        session["instructor_seen_at"] = time.time() - 200
        viewed = audience_view(session)
        assert viewed["state"] == "paused"
        assert int(viewed["seq"]) == int(session["seq"])
        stored = await get_session(9)
        assert stored is not None
        assert stored["state"] == "live"
