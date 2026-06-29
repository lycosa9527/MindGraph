"""WeChat key probe with structured report for the UI."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from file_reader.wechat.crypto import WeChatKeyError
from file_reader.wechat.debug_log import clear_wechat_log, log_wechat, log_wechat_section
from file_reader.wechat.key_extract import extract_db_keys_with_report, resolve_db_dir
from file_reader.wechat.key_store import WeChatKeyPersistContext, load_wechat_key_cache
from file_reader.wechat.version import (
    WeChatCryptoVariant,
    detect_client_exe_version,
    format_client_version,
    infer_layout_variant,
    key_extraction_plan,
    requires_wx_key_hook,
    resolve_crypto_variant,
)


@dataclass(frozen=True)
class WeChatProbeReport:
    """Result of an explicit user-initiated WeChat DB key probe."""

    success: bool
    key_count: int
    crypto_variant: Optional[str]
    method: Optional[str]
    weixin_version: Optional[str]
    duration_sec: float
    error: Optional[str]
    keys: Dict[str, str]
    from_cache: bool = False


def _resolve_crypto(
    account_dir: Path,
    *,
    client_variant: Optional[str],
) -> tuple[WeChatCryptoVariant, str]:
    layout = infer_layout_variant(account_dir)
    version_tuple = detect_client_exe_version(layout=layout)
    version_label = format_client_version(version_tuple)
    if client_variant == "v3":
        crypto = "v3"
    elif client_variant == "v4.1":
        crypto = "v4.1"
    elif client_variant == "v4":
        crypto = resolve_crypto_variant("v4", weixin_version=version_tuple)
    else:
        crypto = resolve_crypto_variant(layout, weixin_version=version_tuple)
    return crypto, version_label


def _try_cached_probe(
    account_dir: Path,
    db_dir: Path,
    *,
    client_variant: Optional[str],
    mindgraph_user_id: Optional[int],
    wxid: Optional[str],
    current_weixin_version: Optional[str] = None,
) -> Optional[WeChatProbeReport]:
    if mindgraph_user_id is None or not wxid:
        return None
    started = time.monotonic()
    record = load_wechat_key_cache(
        account_dir,
        db_dir,
        mindgraph_user_id=mindgraph_user_id,
        wxid=wxid,
        current_weixin_version=current_weixin_version,
    )
    if record is None:
        return None
    elapsed = time.monotonic() - started
    crypto, version_label = _resolve_crypto(account_dir, client_variant=client_variant)
    log_wechat(
        f"SUCCESS method=cached keys={len(record.keys)} crypto={record.crypto_variant or crypto} elapsed={elapsed:.1f}s"
    )
    return WeChatProbeReport(
        success=True,
        key_count=len(record.keys),
        crypto_variant=record.crypto_variant or crypto,
        method="cached",
        weixin_version=record.weixin_version or version_label,
        duration_sec=elapsed,
        error=None,
        keys=record.keys,
        from_cache=True,
    )


def run_wechat_key_probe(
    account_dir: Path,
    *,
    client_variant: Optional[str],
    mindgraph_user_id: Optional[int] = None,
    mindgraph_phone: str = "",
    wxid: Optional[str] = None,
    prefer_cache: bool = True,
    current_weixin_version: Optional[str] = None,
) -> WeChatProbeReport:
    """Extract DB keys once and return a UI-friendly report."""
    clear_wechat_log()
    log_wechat_section("WeChat key probe started")
    layout = infer_layout_variant(account_dir)
    version_tuple = detect_client_exe_version(layout=layout)
    version_label = format_client_version(version_tuple)
    if current_weixin_version is None:
        current_weixin_version = version_label
    crypto, _version_from_resolve = _resolve_crypto(account_dir, client_variant=client_variant)
    plan = key_extraction_plan(crypto, weixin_version=version_tuple)
    db_dir = resolve_db_dir(account_dir, crypto)
    log_wechat(f"account_dir={account_dir}")
    log_wechat(f"layout={layout} client_hint={client_variant} crypto={crypto}")
    log_wechat(f"client_version={version_label}")
    if mindgraph_user_id is not None and wxid:
        log_wechat(f"mindgraph_user_id={mindgraph_user_id} wxid={wxid}")
    if requires_wx_key_hook(version_tuple):
        log_wechat("passive_passphrase_scan=skipped (Weixin >= 4.1.10.31)")
    log_wechat(f"key_plan={' → '.join(plan)}")

    if prefer_cache:
        cached = _try_cached_probe(
            account_dir,
            db_dir,
            client_variant=client_variant,
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            current_weixin_version=current_weixin_version,
        )
        if cached is not None:
            return cached

    started = time.monotonic()
    persist: Optional[WeChatKeyPersistContext] = None
    if mindgraph_user_id is not None and wxid:
        persist = WeChatKeyPersistContext(
            mindgraph_user_id=mindgraph_user_id,
            mindgraph_phone=mindgraph_phone,
            wxid=wxid,
            crypto_variant=crypto,
            weixin_version=version_label,
        )
    try:
        result = extract_db_keys_with_report(
            account_dir,
            client_variant=client_variant,
            persist=persist,
        )
        elapsed = time.monotonic() - started
        log_wechat(
            f"SUCCESS method={result.method} keys={len(result.keys)} "
            f"crypto={result.crypto_variant} elapsed={elapsed:.1f}s"
        )
        return WeChatProbeReport(
            success=True,
            key_count=len(result.keys),
            crypto_variant=result.crypto_variant,
            method=result.method,
            weixin_version=version_label,
            duration_sec=elapsed,
            error=None,
            keys=result.keys,
            from_cache=False,
        )
    except WeChatKeyError as exc:
        elapsed = time.monotonic() - started
        message = str(exc)
        log_wechat(f"FAILED elapsed={elapsed:.1f}s error={message}", level="ERROR")
        return WeChatProbeReport(
            success=False,
            key_count=0,
            crypto_variant=crypto,
            method=None,
            weixin_version=version_label,
            duration_sec=elapsed,
            error=message,
            keys={},
            from_cache=False,
        )
