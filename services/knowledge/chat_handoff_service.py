"""Redis-backed pairing codes for file-reader → 文档总结 package ingest.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select

from models.domain.knowledge_space import KnowledgeDocument
from services.redis.redis_async_ops import AsyncRedisOps
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)

HANDOFF_TTL_SECONDS = 600
HANDOFF_KEY_PREFIX = "chat_handoff:"
RATE_KEY_PREFIX = "chat_handoff_rate:"
USER_CODES_PREFIX = "chat_handoff_user:"


@dataclass(frozen=True)
class ChatHandoffRecord:
    """Stored handoff session metadata."""

    user_id: int
    package_id: int
    status: str
    document_id: Optional[int] = None


@dataclass(frozen=True)
class WaitingHandoffSession:
    """Active website pairing session for the desktop client."""

    code: str
    package_id: int
    status: str
    expires_in_seconds: int


def _code_key(code: str) -> str:
    return f"{HANDOFF_KEY_PREFIX}{code}"


def _rate_key(user_id: int) -> str:
    return f"{RATE_KEY_PREFIX}{user_id}"


def _user_codes_key(user_id: int) -> str:
    return f"{USER_CODES_PREFIX}{user_id}"


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def load_handoff(code: str) -> Optional[ChatHandoffRecord]:
    """Load handoff record by pairing code."""
    raw = await AsyncRedisOps.get(_code_key(code))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        user_id = int(data["user_id"])
        package_id = int(data["package_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    document_id = data.get("document_id")
    parsed_doc_id = int(document_id) if document_id is not None else None
    return ChatHandoffRecord(
        user_id=user_id,
        package_id=package_id,
        status=str(data.get("status") or "waiting"),
        document_id=parsed_doc_id,
    )


async def consume_handoff(code: str) -> None:
    """Remove pairing code after successful ingest."""
    record = await load_handoff(code)
    try:
        await AsyncRedisOps.delete(_code_key(code))
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning("[ChatHandoff] Failed to delete code %s: %s", code, exc)
    if record is not None:
        await AsyncRedisOps.set_remove(_user_codes_key(record.user_id), code)


async def revoke_handoff_code(code: str, user_id: int) -> bool:
    """Delete a waiting pairing code owned by the user. Idempotent."""
    record = await load_handoff(code)
    if record is None or record.user_id != user_id or record.status != "waiting":
        return False
    await consume_handoff(code)
    logger.info(
        "[ChatHandoff] Revoked waiting code for user=%s package=%s",
        user_id,
        record.package_id,
    )
    return True


async def revoke_waiting_handoffs_for_package(user_id: int, package_id: int) -> int:
    """Revoke all waiting pairing codes for a user + package."""
    codes = await AsyncRedisOps.set_members(_user_codes_key(user_id))
    revoked = 0
    for code in codes:
        record = await load_handoff(code)
        if record is None:
            await AsyncRedisOps.set_remove(_user_codes_key(user_id), code)
            continue
        if record.user_id != user_id or record.package_id != package_id:
            continue
        if record.status != "waiting":
            continue
        if await revoke_handoff_code(code, user_id):
            revoked += 1
    return revoked


async def mint_handoff_code(user_id: int, package_id: int) -> str:
    """Create a six-digit pairing code bound to user + package."""
    rate_count = await AsyncRedisOps.increment(_rate_key(user_id), ttl_seconds=600)
    if rate_count is not None and rate_count > 20:
        raise ValueError("Too many pairing codes requested; try again later")

    # One waiting code per package — drop any prior live pairing for this corpus.
    await revoke_waiting_handoffs_for_package(user_id, package_id)

    for _ in range(8):
        code = _generate_code()
        payload = json.dumps(
            {
                "user_id": user_id,
                "package_id": package_id,
                "status": "waiting",
                "document_id": None,
            }
        )
        stored = await AsyncRedisOps.set_with_ttl_if_not_exists(_code_key(code), payload, HANDOFF_TTL_SECONDS)
        if stored:
            await AsyncRedisOps.set_add(
                _user_codes_key(user_id),
                code,
                ttl_seconds=HANDOFF_TTL_SECONDS,
            )
            logger.info("[ChatHandoff] Minted code for user=%s package=%s", user_id, package_id)
            return code
    raise RuntimeError("Failed to allocate pairing code")


async def claim_handoff_for_ingest(code: str, user_id: int) -> Optional[ChatHandoffRecord]:
    """Atomically transition ``waiting`` → ``received`` for a single ingest."""
    key = _code_key(code)
    raw = await AsyncRedisOps.get(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        record_user = int(data["user_id"])
        package_id = int(data["package_id"])
        status = str(data.get("status") or "waiting")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if record_user != user_id or status != "waiting":
        return None
    new_payload = json.dumps(
        {
            "user_id": user_id,
            "package_id": package_id,
            "status": "received",
            "document_id": None,
        }
    )
    claimed = await AsyncRedisOps.compare_and_set_with_ttl(
        key,
        raw,
        new_payload,
        HANDOFF_TTL_SECONDS,
    )
    if not claimed:
        return None
    await AsyncRedisOps.set_remove(_user_codes_key(user_id), code)
    logger.info("[ChatHandoff] Claimed code for ingest user=%s package=%s", user_id, package_id)
    return ChatHandoffRecord(
        user_id=user_id,
        package_id=package_id,
        status="received",
    )


async def update_handoff_status(
    code: str,
    status: str,
    document_id: Optional[int] = None,
) -> bool:
    """Update handoff status while preserving TTL."""
    record = await load_handoff(code)
    if record is None:
        return False
    payload = json.dumps(
        {
            "user_id": record.user_id,
            "package_id": record.package_id,
            "status": status,
            "document_id": document_id,
        }
    )
    await AsyncRedisOps.set_with_ttl(_code_key(code), payload, HANDOFF_TTL_SECONDS)
    if status != "waiting":
        await AsyncRedisOps.set_remove(_user_codes_key(record.user_id), code)
    return True


async def list_waiting_handoffs(user_id: int) -> List[WaitingHandoffSession]:
    """Return pairing codes the website is waiting on for this user."""
    codes = await AsyncRedisOps.set_members(_user_codes_key(user_id))
    sessions: List[WaitingHandoffSession] = []
    for code in codes:
        record = await load_handoff(code)
        if record is None or record.user_id != user_id:
            await AsyncRedisOps.set_remove(_user_codes_key(user_id), code)
            continue
        if record.status != "waiting":
            await AsyncRedisOps.set_remove(_user_codes_key(user_id), code)
            continue
        ttl = await AsyncRedisOps.get_ttl(_code_key(code))
        expires = max(0, int(ttl)) if ttl and ttl > 0 else HANDOFF_TTL_SECONDS
        sessions.append(
            WaitingHandoffSession(
                code=code,
                package_id=record.package_id,
                status=record.status,
                expires_in_seconds=expires,
            )
        )
    return sessions


async def finalize_handoff_for_document(document_id: int, terminal_status: str) -> None:
    """Update pairing status when chat-handoff document indexing finishes."""
    if terminal_status not in ("done", "failed"):
        return
    async with rls_async_session(RlsContext.system_bootstrap()) as db:
        result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None or not isinstance(doc.doc_metadata, dict):
            return
        code = doc.doc_metadata.get("handoff_code")
        if not isinstance(code, str) or len(code) != 6:
            return
    await update_handoff_status(code, terminal_status, document_id)
