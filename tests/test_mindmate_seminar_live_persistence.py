"""Live Postgres and Redis: a seminar's row, transcript, and file bytes survive a Redis wipe."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from models.domain.auth import User
from models.domain.mindmate_seminar import (
    MindmateSeminarBackgroundFile,
    MindmateSeminarMessage,
    MindmateSeminarSession,
)
from services.features.mindmate_seminar.background_files import STATIC_ROOT, store_background_bytes
from services.features.mindmate_seminar.manager import MindmateSeminarManager
from services.features.mindmate_seminar.redis_keys import async_purge_session_redis_keys, session_meta_key
from services.features.mindmate_seminar.seminar_file_storage import (
    delete_seminar_bytes_sync,
    read_seminar_bytes_sync,
)
from services.features.mindmate_seminar.seminar_message import ensure_live_seminar_room
from services.redis.redis_async_client import get_async_redis
from utils.db.session_open import system_rls_session

_LINE = "live seminar line that must survive redis"
_FILE_BYTES = b"live seminar file bytes"


async def _postgres_reachable() -> bool:
    try:
        async with system_rls_session() as db:
            await db.execute(select(User.id).limit(1))
    except (SQLAlchemyError, OSError):
        return False
    return True


async def _delete_fixture(user_id: int | None, session_id: str | None) -> None:
    async with system_rls_session() as db:
        if session_id:
            await db.execute(delete(MindmateSeminarSession).where(MindmateSeminarSession.id == session_id))
        if user_id is not None:
            await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_seminar_survives_redis_room_wipe() -> None:
    """A wiped Redis room is rebuilt from Postgres. The transcript and file stay."""
    redis = get_async_redis()
    try:
        await redis.ping()
    except (OSError, RedisError) as exc:
        pytest.skip(f"Redis is not reachable: {exc}")
    if not await _postgres_reachable():
        pytest.skip("Postgres is not reachable")

    manager = MindmateSeminarManager()
    user_id: int | None = None
    session_id: str | None = None
    code = ""
    storage_key = ""
    try:
        async with system_rls_session() as db:
            user = User(
                email=f"live-seminar-{uuid4().hex}@example.invalid",
                password_hash="live-test-not-a-login",
                name="Live Seminar",
                role="teacher",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            user_id = int(user.id)

        payload, error = await manager.start_session(user_id, title="Live persistence")
        assert error is None and payload is not None
        session_id = str(payload["session_id"])
        code = str(payload["code"])

        await manager.persist_message(
            session_id,
            role="user",
            content=_LINE,
            sender_user_id=user_id,
            room_code=code,
        )
        await manager.set_dify_conversation_id(session_id, "conv-live-persist", server=1)
        renamed = await manager.update_session_title(session_id, user_id, "Renamed live")
        assert renamed is not None
        assert renamed["title"] == "Renamed live"

        before = await manager.get_session_meta(code)
        assert before.get("session_id") == session_id
        assert before.get("title") == "Renamed live"
        assert "conv-live-persist" in before.get("dify_conversation_id", "")

        storage_key = await store_background_bytes("live-note.txt", _FILE_BYTES, "text/plain")
        async with system_rls_session() as db:
            db.add(
                MindmateSeminarBackgroundFile(
                    id=str(uuid4()),
                    session_id=session_id,
                    uploader_user_id=user_id,
                    filename="live-note.txt",
                    content_type="text/plain",
                    size_bytes=len(_FILE_BYTES),
                    storage_key=storage_key,
                    listed=False,
                    created_at=datetime.now(tz=UTC),
                )
            )
            await db.commit()

        await async_purge_session_redis_keys(redis, code, None, "organization")
        assert not await redis.exists(session_meta_key(code))

        session = await manager.load_session_by_id(session_id)
        assert session is not None
        assert session.title == "Renamed live"
        assert session.dify_conversation_id is not None
        assert "conv-live-persist" in session.dify_conversation_id
        history = await manager.fetch_message_history(session_id)
        assert any(item.get("content") == _LINE for item in history)
        async with system_rls_session() as db:
            file_row = (
                await db.execute(
                    select(MindmateSeminarBackgroundFile).where(MindmateSeminarBackgroundFile.session_id == session_id)
                )
            ).scalar_one()
            assert file_row.storage_key == storage_key
        restored = read_seminar_bytes_sync(storage_key, max_bytes=1024)
        if restored is None:
            disk = STATIC_ROOT / storage_key
            assert disk.is_file()
            assert disk.read_bytes() == _FILE_BYTES
        else:
            assert restored == _FILE_BYTES

        assert await ensure_live_seminar_room(session) is True
        after = await manager.get_session_meta(code)
        assert after.get("session_id") == session_id
        assert after.get("title") == "Renamed live"
        assert after.get("dify_conversation_id") == session.dify_conversation_id
        assert after.get("owner_id") == str(user_id)

        assert await manager.stop_session(session_id, user_id, reason="owner") is True
        assert await manager.load_session_by_id(session_id) is None
        ended = await manager.load_session_by_id_any(session_id)
        assert ended is not None and ended.ended_at is not None
        kept = await manager.fetch_message_history(session_id)
        assert any(item.get("content") == _LINE for item in kept)
        assert not await redis.exists(session_meta_key(code))
        async with system_rls_session() as db:
            still = (
                await db.execute(
                    select(MindmateSeminarMessage.id).where(MindmateSeminarMessage.session_id == session_id)
                )
            ).scalar_one_or_none()
        assert still is not None
    finally:
        if code:
            try:
                await async_purge_session_redis_keys(redis, code, None, "organization")
            except (OSError, RedisError):
                pass
        if storage_key:
            delete_seminar_bytes_sync(storage_key, STATIC_ROOT)
        await _delete_fixture(user_id, session_id)
