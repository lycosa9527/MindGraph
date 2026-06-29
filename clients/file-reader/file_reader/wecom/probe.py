"""Decrypt WeCom DB and load sessions for the UI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from file_reader.wecom.db_cache import WeComDbCache
from file_reader.wecom.db_reader import WeComDbError, WeComDbReader, WeComSessionPreview
from file_reader.wecom.debug_log import clear_wecom_log, log_wecom, log_wecom_section
from file_reader.wecom.key_extract import WeComKeyError, WeComKeyPersistContext, extract_wecom_db_keys
from file_reader.wecom.key_store import load_wecom_key_cache
from file_reader.wecom.local import WeComLocalStatus, account_from_status, detect_wecom_local


@dataclass(frozen=True)
class WeComProbeReport:
    """Result of a WeCom database unlock attempt."""

    success: bool
    session_count: int
    key_count: int
    duration_sec: float
    error: str = ""
    keys: Optional[Dict[str, str]] = None
    from_cache: bool = False
    method: str = ""


def _try_cached_probe(
    status: WeComLocalStatus,
    *,
    mindgraph_user_id: Optional[int],
) -> Optional[WeComProbeReport]:
    if mindgraph_user_id is None or status.data_root is None or not status.account_label:
        return None
    started = time.perf_counter()
    record = load_wecom_key_cache(
        status.data_root,
        mindgraph_user_id=mindgraph_user_id,
        account_label=status.account_label,
    )
    if record is None:
        return None
    elapsed = time.perf_counter() - started
    log_wecom(f"cache hit keys={len(record.keys)} elapsed={elapsed:.1f}s")
    return WeComProbeReport(
        success=True,
        session_count=0,
        key_count=len(record.keys),
        duration_sec=elapsed,
        keys=record.keys,
        from_cache=True,
        method=record.method,
    )


def run_wecom_probe(
    status: Optional[WeComLocalStatus] = None,
    *,
    mindgraph_user_id: Optional[int] = None,
    mindgraph_phone: str = "",
    prefer_cache: bool = True,
) -> WeComProbeReport:
    """Extract keys (or load cache). Session load is handled separately."""
    started = time.perf_counter()
    current = status or detect_wecom_local()
    if not current.local_dbs_present:
        return WeComProbeReport(
            success=False,
            session_count=0,
            key_count=0,
            duration_sec=time.perf_counter() - started,
            error="db_missing",
        )
    if prefer_cache:
        cached = _try_cached_probe(current, mindgraph_user_id=mindgraph_user_id)
        if cached is not None and cached.keys:
            return cached
    if not current.process_running or current.data_root is None:
        return WeComProbeReport(
            success=False,
            session_count=0,
            key_count=0,
            duration_sec=time.perf_counter() - started,
            error="wxwork_not_running",
        )
    clear_wecom_log()
    log_wecom_section("WeCom key probe started")
    persist: Optional[WeComKeyPersistContext] = None
    if mindgraph_user_id is not None and current.account_label:
        persist = WeComKeyPersistContext(
            mindgraph_user_id=mindgraph_user_id,
            mindgraph_phone=mindgraph_phone,
            account_label=current.account_label,
        )
    try:
        extracted = extract_wecom_db_keys(current.data_root, persist=persist)
    except WeComKeyError as exc:
        return WeComProbeReport(
            success=False,
            session_count=0,
            key_count=0,
            duration_sec=time.perf_counter() - started,
            error=str(exc),
        )
    return WeComProbeReport(
        success=True,
        session_count=0,
        key_count=len(extracted.keys),
        duration_sec=time.perf_counter() - started,
        keys=extracted.keys,
        method=extracted.method,
    )


def load_wecom_sessions(
    status: Optional[WeComLocalStatus] = None,
    *,
    keys: Dict[str, str],
) -> tuple[WeComLocalStatus, List[WeComSessionPreview], Optional[Exception]]:
    """Detect, decrypt chat DBs, and list conversations."""
    current = status or detect_wecom_local()
    account = account_from_status(current)
    if account is None:
        return current, [], WeComDbError("No WeCom account database found")
    try:
        reader = WeComDbReader(WeComDbCache(account, keys), self_id=current.user_id)
        sessions = reader.list_sessions()
        log_wecom(f"load_wecom_sessions count={len(sessions)}")
    except (WeComDbError, OSError, ValueError) as exc:
        log_wecom(f"load_wecom_sessions failed: {exc}", level="ERROR")
        return current, [], exc
    return current, sessions, None
