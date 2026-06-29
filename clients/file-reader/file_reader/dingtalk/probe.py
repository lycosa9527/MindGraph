"""Decrypt DingTalk DB and load sessions for the UI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from file_reader.dingtalk.crypto import DingTalkCryptoError
from file_reader.dingtalk.db_cache import DingTalkDbCache
from file_reader.dingtalk.db_reader import DingTalkDbError, DingTalkDbReader, DingTalkSessionPreview
from file_reader.dingtalk.key_store import DingTalkUnlockPersistContext
from file_reader.dingtalk.local import DingTalkLocalStatus, account_from_status, detect_dingtalk_local


@dataclass(frozen=True)
class DingTalkProbeReport:
    """Result of a DingTalk database unlock attempt."""

    success: bool
    session_count: int
    storage_version: str
    duration_sec: float
    error: str = ""


def run_dingtalk_probe(
    status: Optional[DingTalkLocalStatus] = None,
    *,
    mindgraph_user_id: Optional[int] = None,
    mindgraph_phone: str = "",
) -> DingTalkProbeReport:
    """Decrypt local DB and count sessions."""
    started = time.perf_counter()
    current = status or detect_dingtalk_local()
    if not current.unlock_ready:
        return DingTalkProbeReport(
            success=False,
            session_count=0,
            storage_version=current.storage_version or "",
            duration_sec=time.perf_counter() - started,
            error="missing_uid_or_salt",
        )
    account = account_from_status(current)
    if account is None:
        return DingTalkProbeReport(
            success=False,
            session_count=0,
            storage_version=current.storage_version or "",
            duration_sec=time.perf_counter() - started,
            error="account_not_found",
        )
    persist: Optional[DingTalkUnlockPersistContext] = None
    if mindgraph_user_id is not None and current.account_folder_id:
        persist = DingTalkUnlockPersistContext(
            mindgraph_user_id=mindgraph_user_id,
            mindgraph_phone=mindgraph_phone,
            account_folder_id=current.account_folder_id,
        )
    try:
        reader = DingTalkDbReader(DingTalkDbCache(account, persist=persist))
        sessions = reader.list_sessions()
    except (DingTalkCryptoError, DingTalkDbError, OSError, ValueError) as exc:
        return DingTalkProbeReport(
            success=False,
            session_count=0,
            storage_version=current.storage_version or "",
            duration_sec=time.perf_counter() - started,
            error=str(exc),
        )
    return DingTalkProbeReport(
        success=True,
        session_count=len(sessions),
        storage_version=current.storage_version or "",
        duration_sec=time.perf_counter() - started,
    )


def load_dingtalk_sessions(
    status: Optional[DingTalkLocalStatus] = None,
    *,
    mindgraph_user_id: Optional[int] = None,
    mindgraph_phone: str = "",
) -> tuple[DingTalkLocalStatus, List[DingTalkSessionPreview], Optional[Exception]]:
    """Detect, decrypt, and list conversations."""
    current = status or detect_dingtalk_local()
    account = account_from_status(current)
    if account is None:
        return current, [], DingTalkDbError("No DingTalk account database found")
    persist: Optional[DingTalkUnlockPersistContext] = None
    if mindgraph_user_id is not None and current.account_folder_id:
        persist = DingTalkUnlockPersistContext(
            mindgraph_user_id=mindgraph_user_id,
            mindgraph_phone=mindgraph_phone,
            account_folder_id=current.account_folder_id,
        )
    try:
        reader = DingTalkDbReader(DingTalkDbCache(account, persist=persist))
        sessions = reader.list_sessions()
    except (DingTalkCryptoError, DingTalkDbError, OSError, ValueError) as exc:
        return current, [], exc
    return current, sessions, None
