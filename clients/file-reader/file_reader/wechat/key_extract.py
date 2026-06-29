"""Version-aware WeChat DB key extraction (Windows v3 / v4 / v4.1).

Three crypto cases (cross-ref ylytdeng/wechat-decrypt + chatlog + wx_key):

- v3: WeChat.exe + WeChatWin.dll (PBKDF2-SHA1)
- v4: Weixin 4.0.x raw enc_key in memory as x'hex' (wechat-decrypt)
- v4.1: Weixin 4.1+ WCDB passphrase (chatlog / wx_key.dll)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from file_reader.wechat.crypto import (
    KEY_SZ,
    WeChatKeyError,
    collect_db_files,
)
from file_reader.wechat.debug_log import log_wechat
from file_reader.wechat.scan_common import (
    MemoryBasicInformation,
    SaltKeyCallback,
    _V41_CHUNK,
    _V41_CHUNK_OVERLAP,
    _MAX_V41_SCAN_BYTES,
    build_key_index,
    cross_verify_keys,
    enum_readable_regions,
    enum_v4_private_regions,
    read_process_memory,
    scan_memory_for_keys,
    scan_v4_passphrase_in_chunk,
)
from file_reader.wechat.v3 import derive_v3_enc_key, verify_v3_passphrase
from file_reader.wechat.v41 import derive_keys_from_passphrase
from file_reader.wechat.version import (
    WeChatCryptoVariant,
    detect_client_exe_version,
    format_client_version,
    infer_layout_variant,
    requires_wx_key_hook,
    resolve_crypto_variant,
    supports_passive_passphrase_scan,
)
from file_reader.wechat.key_store import WeChatIncrementalKeyStore, WeChatKeyPersistContext
from file_reader.wechat.wxkey_dll import find_wx_key_dll, try_wx_key_passphrase

_V3_MODULE = "WeChatWin.dll"
_V3_KEY_PATTERN = bytes([0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
_PAGE_WRITABLE = 0x04 | 0x08 | 0x40 | 0x80


class _ModuleInfo(ctypes.Structure):
    _fields_ = [
        ("base_of_dll", ctypes.c_void_p),
        ("size_of_image", wt.DWORD),
        ("entry_point", ctypes.c_void_p),
    ]


@dataclass(frozen=True)
class KeyExtractResult:
    """Structured key extraction outcome."""

    keys: Dict[str, str]
    crypto_variant: WeChatCryptoVariant
    method: str


def resolve_db_dir(account_dir: Path, client_variant: Optional[str]) -> Path:
    """Return the directory that contains encrypted .db files."""
    storage = account_dir / "db_storage"
    if client_variant in {"v4", "v4.1"} and storage.is_dir():
        return storage
    return account_dir


def _process_pids(*image_names: str) -> List[int]:
    pids: List[int] = []
    for image in image_names:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    continue
    return list(dict.fromkeys(pids))


def _find_module_base(pid: int, module_name: str) -> Optional[Tuple[int, int]]:
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    access = 0x0010 | 0x0400
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return None
    try:
        needed = wt.DWORD()
        psapi.EnumProcessModulesEx(handle, None, 0, ctypes.byref(needed), 0x03)
        if needed.value == 0:
            return None
        count = needed.value // ctypes.sizeof(ctypes.c_void_p)
        modules = (ctypes.c_void_p * count)()
        psapi.EnumProcessModulesEx(handle, ctypes.byref(modules), needed, ctypes.byref(needed), 0x03)
        name_buffer = ctypes.create_unicode_buffer(260)
        info = _ModuleInfo()
        for module in modules:
            if not module:
                continue
            read = psapi.GetModuleBaseNameW(handle, module, name_buffer, 260)
            if read == 0:
                continue
            if name_buffer.value.lower() != module_name.lower():
                continue
            if psapi.GetModuleInformation(handle, module, ctypes.byref(info), ctypes.sizeof(info)) == 0:
                return None
            base = info.base_of_dll or 0
            return base, info.size_of_image
    finally:
        kernel32.CloseHandle(handle)
    return None


def _reference_page1(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    client_variant: Optional[str],
) -> Optional[bytes]:
    if client_variant == "v3":
        for rel, _path, _size, _salt, page1 in db_files:
            norm = rel.replace("\\", "/").lower()
            if norm.endswith("misc.db") or norm.endswith("micromsg.db"):
                return page1
    for rel, _path, _size, _salt, page1 in db_files:
        if rel.replace("\\", "/") == "message/message_0.db":
            return page1
    for rel, _path, _size, _salt, page1 in db_files:
        if "message/message_" in rel.replace("\\", "/"):
            return page1
    return db_files[0][4] if db_files else None


def _derive_v3_key_map(
    passphrase: bytes,
    db_files: List[Tuple[str, Path, int, str, bytes]],
) -> Dict[str, str]:
    key_map: Dict[str, str] = {}
    for _rel, _path, _size, salt_hex, page1 in db_files:
        salt = bytes.fromhex(salt_hex)
        enc_key = derive_v3_enc_key(passphrase, salt)
        if verify_v3_passphrase(passphrase, page1):
            key_map[salt_hex] = enc_key.hex()
    return key_map


def _scan_v3_wechatwin(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    pids: List[int],
) -> Optional[bytes]:
    reference = _reference_page1(db_files, "v3")
    if reference is None:
        return None
    kernel32 = ctypes.windll.kernel32
    access = 0x0010 | 0x0400
    seen: Set[int] = set()

    for pid in pids:
        module = _find_module_base(pid, _V3_MODULE)
        if module is None:
            continue
        base, size = module
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        try:
            end = base + size
            address = base
            block = MemoryBasicInformation()
            while address < end:
                if (
                    kernel32.VirtualQueryEx(handle, ctypes.c_uint64(address), ctypes.byref(block), ctypes.sizeof(block))
                    == 0
                ):
                    break
                writable = (block.protect & _PAGE_WRITABLE) != 0
                if block.state == 0x1000 and writable and block.region_size >= 100 * 1024:
                    region_end = min(block.base_address + block.region_size, end)
                    region_size = region_end - block.base_address
                    data = read_process_memory(handle, block.base_address, region_size)
                    if data:
                        index = len(data)
                        while index > 0:
                            found = data.rfind(_V3_KEY_PATTERN, 0, index)
                            if found < 8:
                                break
                            index = found
                            ptr_value = struct.unpack("<Q", data[found - 8 : found])[0]
                            if ptr_value <= 0x10000 or ptr_value >= 0x7FFFFFFFFFFF:
                                continue
                            if ptr_value in seen:
                                continue
                            seen.add(ptr_value)
                            key_data = read_process_memory(handle, ptr_value, KEY_SZ)
                            if key_data and verify_v3_passphrase(key_data, reference):
                                return key_data
                next_addr = block.base_address + block.region_size
                if next_addr <= address:
                    break
                address = next_addr
        finally:
            kernel32.CloseHandle(handle)
    return None


def _scan_v4_raw_keys(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    salt_to_rels: Dict[str, List[str]],
    pids: List[int],
    *,
    persister: Optional[WeChatIncrementalKeyStore] = None,
) -> Dict[str, str]:
    """WeChat 4.0.x: scan memory for cached x'<enc_key><salt>' patterns."""
    hex_pattern = re.compile(rb"x'([0-9a-fA-F]{64,192})'")
    key_map: Dict[str, str] = {}
    remaining_salts = set(salt_to_rels.keys())
    kernel32 = ctypes.windll.kernel32
    access = 0x0010 | 0x0400
    on_salt_found: Optional[SaltKeyCallback] = None
    if persister is not None:

        def on_salt_found(salt: str, key: str) -> None:
            persister.on_salt_found(salt, key, salt_to_rels)

    for pid in pids:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        try:
            for base, size in enum_readable_regions(handle):
                data = read_process_memory(handle, base, size)
                if not data:
                    continue
                scan_memory_for_keys(
                    data,
                    hex_pattern,
                    db_files,
                    key_map,
                    remaining_salts,
                    on_salt_found=on_salt_found,
                )
                if not remaining_salts:
                    break
        finally:
            kernel32.CloseHandle(handle)
        if not remaining_salts:
            break

    cross_verify_keys(db_files, salt_to_rels, key_map, on_salt_found=on_salt_found)
    return build_key_index(db_files, key_map)


def _scan_v41_passphrase(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    pids: List[int],
) -> Dict[str, str]:
    """WeChat 4.1+: struct pattern in large private RW regions (chunked, capped)."""
    reference = _reference_page1(db_files, "v4.1")
    if reference is None:
        log_wechat("v4.1 passphrase scan skipped: no reference page1")
        return {}
    kernel32 = ctypes.windll.kernel32
    access = 0x0010 | 0x0400
    seen_pointers: Set[int] = set()
    scanned_bytes = 0

    for pid in pids:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            log_wechat(f"OpenProcess failed pid={pid}", level="WARN")
            continue
        try:
            regions = enum_v4_private_regions(handle)
            log_wechat(f"v4.1 scan pid={pid} regions={len(regions)}")
            for region_index, (base, size) in enumerate(regions):
                if scanned_bytes >= _MAX_V41_SCAN_BYTES:
                    log_wechat(f"v4.1 scan byte cap reached ({_MAX_V41_SCAN_BYTES // (1024 * 1024)} MiB)")
                    break
                offset = 0
                trailing: Optional[bytes] = None
                while offset < size and scanned_bytes < _MAX_V41_SCAN_BYTES:
                    chunk_size = min(_V41_CHUNK, size - offset)
                    chunk = read_process_memory(handle, base + offset, chunk_size)
                    offset += chunk_size
                    scanned_bytes += chunk_size
                    if not chunk:
                        trailing = None
                        continue
                    if trailing:
                        data = trailing + chunk
                    else:
                        data = chunk
                    material = scan_v4_passphrase_in_chunk(
                        data,
                        handle,
                        reference,
                        seen_pointers,
                    )
                    if material is not None:
                        derived = derive_keys_from_passphrase(material, db_files)
                        indexed = build_key_index(db_files, derived)
                        if indexed:
                            log_wechat(
                                f"v4.1 passphrase found pid={pid} region={region_index} "
                                f"scanned={scanned_bytes // (1024 * 1024)} MiB"
                            )
                            return indexed
                    start = max(0, len(data) - _V41_CHUNK_OVERLAP)
                    trailing = data[start:]
                if scanned_bytes >= _MAX_V41_SCAN_BYTES:
                    break
        finally:
            kernel32.CloseHandle(handle)
    log_wechat("v4.1 passphrase scan finished without match")
    return {}


def _rank_weixin_pids(pids: List[int]) -> List[int]:
    """Prefer the Weixin process with the largest private RW heap (main client)."""
    if len(pids) <= 1:
        return pids
    kernel32 = ctypes.windll.kernel32
    access = 0x0010 | 0x0400
    scored: List[tuple[int, int, int]] = []
    for pid in pids:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            scored.append((0, 0, pid))
            continue
        try:
            regions = enum_v4_private_regions(handle)
            total_bytes = sum(size for _base, size in regions)
            scored.append((len(regions), total_bytes, pid))
        finally:
            kernel32.CloseHandle(handle)
    scored.sort(reverse=True)
    return [pid for _regions, _bytes, pid in scored]


def _try_wx_key_derived(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    pids: List[int],
    crypto: WeChatCryptoVariant,
) -> tuple[Dict[str, str], Optional[str]]:
    """Return (key index, last wx_key error if all attempts failed)."""
    last_error: Optional[str] = None
    if find_wx_key_dll() is None:
        return {}, "wx_key.dll not found"
    for pid in _rank_weixin_pids(pids):
        result = try_wx_key_passphrase(pid)
        if result.error and result.material is None:
            last_error = result.error
            continue
        if result.material is None:
            last_error = last_error or "no key captured"
            continue
        if crypto == "v3":
            derived = _derive_v3_key_map(result.material, db_files)
        else:
            derived = derive_keys_from_passphrase(result.material, db_files)
        indexed = build_key_index(db_files, derived)
        if indexed:
            return indexed, None
        last_error = "key captured but HMAC verification failed"
    return {}, last_error


def _persist_indexed_keys(
    indexed: Dict[str, str],
    persister: Optional[WeChatIncrementalKeyStore],
) -> Dict[str, str]:
    if persister is not None:
        persister.merge_rel_keys(indexed)
        merged = dict(persister.rel_keys)
        merged.update(indexed)
        return merged
    return indexed


def extract_db_keys_with_report(
    account_dir: Path,
    *,
    client_variant: Optional[str] = None,
    persist: Optional[WeChatKeyPersistContext] = None,
) -> KeyExtractResult:
    """Extract DB keys from account_dir and report which method succeeded."""
    layout = infer_layout_variant(account_dir)
    if client_variant == "v3":
        crypto: WeChatCryptoVariant = "v3"
    elif client_variant == "v4.1":
        crypto = "v4.1"
    elif client_variant == "v4":
        version = detect_client_exe_version(layout="v4")
        crypto = resolve_crypto_variant("v4", weixin_version=version)
    else:
        version = detect_client_exe_version(layout=layout)
        crypto = resolve_crypto_variant(layout, weixin_version=version)

    db_dir = resolve_db_dir(account_dir, crypto)
    log_wechat(f"layout={layout} crypto_variant={crypto} client_hint={client_variant} db_dir={db_dir}")

    if sys.platform != "win32":
        raise WeChatKeyError("WeChat DB decryption is supported on Windows only")
    if not db_dir.is_dir():
        raise WeChatKeyError(f"Database directory not found: {db_dir}")

    db_files, salt_to_rels = collect_db_files(db_dir)
    if not db_files:
        raise WeChatKeyError("No encrypted WeChat databases found")
    log_wechat(f"db_files={len(db_files)} unique_salts={len(salt_to_rels)}")

    persister = WeChatIncrementalKeyStore(account_dir, db_dir, persist) if persist is not None else None
    key_map: Dict[str, str] = {}
    remaining_salts: Set[str] = set(salt_to_rels.keys())
    if persister is not None:
        seeded = persister.seed_key_map(db_files, key_map, remaining_salts)
        if seeded:
            log_wechat(
                f"cache seeded unique_salts={seeded} "
                f"rel_keys={len(persister.rel_keys)} remaining={len(remaining_salts)}"
            )
        if not remaining_salts:
            log_wechat(f"all salts satisfied from cache rel_keys={len(persister.rel_keys)}")
            return KeyExtractResult(persister.rel_keys, crypto, "cached")

    process_names = ("Weixin.exe",) if crypto != "v3" else ("WeChat.exe", "Weixin.exe")
    pids = _process_pids(*process_names)
    if not pids:
        raise WeChatKeyError("WeChat is not running — open WeChat and try again")
    log_wechat(f"pids={pids}")

    if crypto == "v3":
        log_wechat("try method=v3_wechatwin")
        material = _scan_v3_wechatwin(db_files, pids)
        if material is not None:
            derived = _derive_v3_key_map(material, db_files)
            indexed = build_key_index(db_files, derived)
            if indexed:
                indexed = _persist_indexed_keys(indexed, persister)
                return KeyExtractResult(indexed, crypto, "v3_wechatwin")
        log_wechat("try method=v3_wx_key_dll")
        indexed, wx_err = _try_wx_key_derived(db_files, pids, crypto)
        if indexed:
            indexed = _persist_indexed_keys(indexed, persister)
            return KeyExtractResult(indexed, crypto, "v3_wx_key_dll")
        raise WeChatKeyError(
            _format_wx_key_failure(wx_err, crypto)
            if wx_err
            else "Could not read WeChat 3.x database keys. Keep WeChat open or export chats manually."
        )

    if crypto == "v4":
        log_wechat("try method=v4_xhex")
        started = time.monotonic()
        indexed = _scan_v4_raw_keys(db_files, salt_to_rels, pids, persister=persister)
        log_wechat(f"v4_xhex elapsed={time.monotonic() - started:.1f}s keys={len(indexed)}")
        if indexed:
            indexed = _persist_indexed_keys(indexed, persister)
            return KeyExtractResult(indexed, crypto, "v4_xhex")
        log_wechat("try method=v4_wx_key_dll")
        indexed, wx_err = _try_wx_key_derived(db_files, pids, crypto)
        if indexed:
            indexed = _persist_indexed_keys(indexed, persister)
            return KeyExtractResult(indexed, crypto, "v4_wx_key_dll")
        raise WeChatKeyError(_format_wx_key_failure(wx_err, crypto))

    weixin_version = detect_client_exe_version(layout="v4")
    passive_ok = supports_passive_passphrase_scan(weixin_version)
    if requires_wx_key_hook(weixin_version):
        log_wechat(f"v4.1 passive scan skipped: Weixin {format_client_version(weixin_version)} needs wx_key.dll hook")
    elif passive_ok:
        log_wechat("try method=v4.1_passphrase")
        indexed = _scan_v41_passphrase(db_files, pids)
        if indexed:
            indexed = _persist_indexed_keys(indexed, persister)
            return KeyExtractResult(indexed, crypto, "v4.1_passphrase")

    log_wechat("try method=v4.1_wx_key_dll")
    indexed, wx_err = _try_wx_key_derived(db_files, pids, crypto)
    if indexed:
        indexed = _persist_indexed_keys(indexed, persister)
        return KeyExtractResult(indexed, crypto, "v4.1_wx_key_dll")

    raise WeChatKeyError(_format_v41_failure(wx_err, weixin_version))


def _format_wx_key_failure(error: Optional[str], crypto: WeChatCryptoVariant) -> str:
    if error and "not found" in error.lower():
        return (
            "wx_key.dll is required but was not found. Place wx_key.dll from "
            "https://github.com/ycccccccy/wx_key/releases beside mindgraph-file-reader.exe "
            "or in clients/file-reader/tools/, then retry."
        )
    if crypto != "v3":
        hint = (
            "Keep Weixin open, browse a few chats after clicking Start, then retry. "
            "Run as Administrator if hook initialization fails."
        )
    else:
        hint = "Keep WeChat open and retry, or export chats manually."
    detail = error or "hook did not capture a key"
    return f"wx_key.dll failed: {detail}. {hint}"


def _format_v41_failure(
    wx_err: Optional[str],
    weixin_version: Optional[tuple[int, int, int, int]],
) -> str:
    version_label = format_client_version(weixin_version)
    if wx_err and "not found" in wx_err.lower():
        if requires_wx_key_hook(weixin_version):
            return (
                f"Weixin {version_label} requires wx_key.dll (passive RAM scan is not supported). "
                "Download wx_key.dll from https://github.com/ycccccccy/wx_key/releases, "
                "place it beside mindgraph-file-reader.exe, run as Administrator, "
                "browse a few chats, then retry. Or export chats manually."
            )
        return _format_wx_key_failure(wx_err, "v4.1")
    return _format_wx_key_failure(
        wx_err,
        "v4.1",
    )


def extract_db_keys(
    db_dir: Path,
    *,
    client_variant: Optional[str] = None,
    account_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Extract per-database derived encryption keys (hex) for v3, v4, or v4.1."""
    target = account_dir
    if target is None:
        layout_hint = client_variant or ("v4" if "db_storage" in db_dir.as_posix() else "v3")
        target = db_dir.parent if layout_hint in {"v4", "v4.1"} else db_dir
    variant = client_variant
    if variant is None:
        variant = "v4" if (target / "db_storage").is_dir() else "v3"
    return extract_db_keys_with_report(target, client_variant=variant).keys
