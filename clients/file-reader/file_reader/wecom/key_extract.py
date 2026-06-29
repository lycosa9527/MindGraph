"""Extract wxSQLite3 raw keys from WXWork.exe process memory."""

from __future__ import annotations

import bisect
import ctypes
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from file_reader.wecom.crypto import is_plain_sqlite_page, is_wxsqlite3_aes128_page1, verify_wxsqlite3_aes128_key
from file_reader.wecom.debug_log import log_wecom
from file_reader.wecom.discovery import (
    DbFileEntry,
    collect_db_files,
    is_session_db_rel,
    salt_to_rels,
)
from file_reader.wecom.key_store import WeComIncrementalKeyStore, WeComKeyPersistContext
from file_reader.wechat.scan_common import (
    build_key_index,
    enum_readable_regions,
    read_process_memory,
)

_WXWORK_PROCESS = "WXWork.exe"
_HEX_PATTERN = re.compile(rb"x'([0-9a-fA-F]{32,192})'")
_BARE_HEX_PATTERN = re.compile(rb"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])")
_PROCESS_ACCESS = 0x0010 | 0x0400
_PAGE_SIZES = {512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}
_STRUCT_SCAN_SECONDS = 120.0
_SECONDARY_STRUCT_SCAN_SECONDS = 45.0


class WeComKeyError(RuntimeError):
    """Failed to extract WeCom database keys from memory."""


@dataclass(frozen=True)
class WeComKeyExtractResult:
    """Structured key extraction outcome."""

    keys: Dict[str, str]
    method: str


def _wxwork_pids() -> List[Tuple[int, int]]:
    """Return ``(pid, mem_kb)`` sorted by memory descending (main process first)."""
    if sys.platform != "win32":
        return []
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_WXWORK_PROCESS}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WeComKeyError("wxwork_process_unavailable") from exc
    pids: List[Tuple[int, int]] = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip('"').split('","')
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[1])
            mem_text = parts[4].replace(",", "").replace(" K", "").strip() or "0"
            mem_kb = int(mem_text)
        except ValueError:
            continue
        pids.append((pid, mem_kb))
    pids.sort(key=lambda item: item[1], reverse=True)
    return pids


def _open_process(pid: int) -> Optional[int]:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_ACCESS, False, pid)
    return handle or None


def _close_process(handle: int) -> None:
    ctypes.windll.kernel32.CloseHandle(handle)


def _try_record_key(
    enc_key: bytes,
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    pid: int,
    source: str,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
) -> bool:
    if len(enc_key) != 16 or enc_key == b"\x00" * 16:
        return False
    matched = False
    for _rel, _path, _size, salt_hex, page1 in db_files:
        if salt_hex not in remaining_salts:
            continue
        if verify_wxsqlite3_aes128_key(enc_key, page1):
            key_hex = enc_key.hex()
            key_map[salt_hex] = key_hex
            remaining_salts.discard(salt_hex)
            matched = True
            log_wecom(f"found key salt={salt_hex[:16]}... rel={_rel} pid={pid} via {source}")
            if persister is not None:
                persister.on_salt_found(salt_hex, key_hex, salt_map)
    return matched


def _log_remaining_salts(
    remaining_salts: Set[str],
    salt_map: Dict[str, List[str]],
) -> None:
    for salt_hex in sorted(remaining_salts):
        rels = ", ".join(salt_map.get(salt_hex, []))
        log_wecom(f"missing salt={salt_hex[:16]}... dbs={rels}", level="WARN")


def _chat_unlock_keys_present(
    db_files: List[DbFileEntry],
    rel_keys: Dict[str, str],
) -> bool:
    """Return True when session.db (and any required message shard) can decrypt."""
    session_needed = False
    session_ready = False
    for rel, _path, _size, _salt, page1 in db_files:
        if not is_session_db_rel(rel):
            continue
        session_needed = True
        if is_plain_sqlite_page(page1):
            session_ready = True
        elif rel in rel_keys:
            session_ready = True
    if not session_needed:
        return bool(rel_keys)
    return session_ready


def _scan_hex_region(
    data: bytes,
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    pid: int,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
) -> int:
    matches = 0
    for match in _HEX_PATTERN.finditer(data):
        hex_str = match.group(1).decode()
        matches += 1
        hex_len = len(hex_str)
        candidates: List[Tuple[str, Optional[str]]] = []
        if hex_len == 32:
            candidates.append((hex_str, None))
        elif hex_len == 64:
            candidates.append((hex_str[:32], hex_str[32:]))
        elif hex_len == 96:
            candidates.append((hex_str[:64], hex_str[64:]))
            candidates.append((hex_str[:32], hex_str[-32:]))
        elif hex_len > 96 and hex_len % 2 == 0:
            candidates.append((hex_str[:32], hex_str[-32:]))

        for enc_key_hex, salt_hex in candidates:
            if len(enc_key_hex) != 32:
                continue
            try:
                enc_key = bytes.fromhex(enc_key_hex)
            except ValueError:
                continue
            if salt_hex and salt_hex in remaining_salts:
                _try_record_key(
                    enc_key,
                    db_files,
                    key_map,
                    remaining_salts,
                    pid=pid,
                    source="hex+salt",
                    salt_map=salt_map,
                    persister=persister,
                )
            elif remaining_salts:
                _try_record_key(
                    enc_key,
                    db_files,
                    key_map,
                    remaining_salts,
                    pid=pid,
                    source="hex",
                    salt_map=salt_map,
                    persister=persister,
                )
            if not remaining_salts:
                return matches
    return matches


def _scan_bare_hex_region(
    data: bytes,
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    pid: int,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
) -> int:
    matches = 0
    for match in _BARE_HEX_PATTERN.finditer(data):
        matches += 1
        try:
            enc_key = bytes.fromhex(match.group(1).decode())
        except ValueError:
            continue
        if _try_record_key(
            enc_key,
            db_files,
            key_map,
            remaining_salts,
            pid=pid,
            source="bare_hex",
            salt_map=salt_map,
            persister=persister,
        ):
            if not remaining_salts:
                return matches
    return matches


def _find_region(
    memory_regions: List[Tuple[int, int, bytes]],
    starts: List[int],
    address: int,
    length: int = 4,
) -> Optional[Tuple[int, int, bytes]]:
    index = bisect.bisect_right(starts, address) - 1
    if index < 0:
        return None
    base, end, data = memory_regions[index]
    if base <= address and address + length <= end:
        return base, end, data
    return None


def _read_u32(
    memory_regions: List[Tuple[int, int, bytes]],
    starts: List[int],
    address: int,
) -> Optional[int]:
    region = _find_region(memory_regions, starts, address, 4)
    if region is None:
        return None
    base, _end, data = region
    return struct.unpack_from("<I", data, address - base)[0]


def _valid_ptr(
    memory_regions: List[Tuple[int, int, bytes]],
    starts: List[int],
    address: int,
    length: int = 4,
) -> bool:
    return _find_region(memory_regions, starts, address, length) is not None


def _wxwork_page_size_chain(
    memory_regions: List[Tuple[int, int, bytes]],
    starts: List[int],
    cipher_addr: int,
) -> Optional[int]:
    page_size_holder = _read_u32(memory_regions, starts, cipher_addr + 0x30)
    if page_size_holder is None or not _valid_ptr(memory_regions, starts, page_size_holder, 8):
        return None
    page_size_obj = _read_u32(memory_regions, starts, page_size_holder + 4)
    if page_size_obj is None or not _valid_ptr(memory_regions, starts, page_size_obj + 0x24, 4):
        return None
    return _read_u32(memory_regions, starts, page_size_obj + 0x24)


def _scan_cipher_structs(
    process_handle: int,
    regions: List[Tuple[int, int]],
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    pid: int,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
    max_seconds: float = _STRUCT_SCAN_SECONDS,
) -> None:
    started = time.monotonic()
    memory_regions: List[Tuple[int, int, bytes]] = []
    total_bytes = 0
    for base, size in regions:
        data = read_process_memory(process_handle, base, size)
        if data:
            memory_regions.append((base, base + len(data), data))
            total_bytes += len(data)
    if not memory_regions:
        return
    memory_regions.sort(key=lambda item: item[0])
    starts = [base for base, _end, _data in memory_regions]
    log_wecom(f"cipher struct scan pid={pid} mb={total_bytes / 1024 / 1024:.0f} regions={len(memory_regions)}")

    checked = 0
    for base, _end, data in memory_regions:
        max_off = len(data) - 0x40
        offset = 0
        while offset < max_off:
            if time.monotonic() - started > max_seconds:
                log_wecom(
                    f"cipher struct scan timeout pid={pid} checked={checked}",
                    level="WARN",
                )
                return
            if not remaining_salts:
                return
            flag0, flag4 = struct.unpack_from("<II", data, offset)
            if flag0 in (1, 2) and flag4 in (1, 2, 4096, 8192, 16384):
                cipher_addr = base + offset
                aes_ctx = struct.unpack_from("<I", data, offset + 0x2C)[0]
                if _valid_ptr(memory_regions, starts, aes_ctx, 0x40):
                    page_size = _wxwork_page_size_chain(memory_regions, starts, cipher_addr)
                    if page_size in _PAGE_SIZES:
                        enc_key = data[offset + 8 : offset + 24]
                        if len(set(enc_key)) >= 6:
                            _try_record_key(
                                enc_key,
                                db_files,
                                key_map,
                                remaining_salts,
                                pid=pid,
                                source=f"struct page_size={page_size}",
                                salt_map=salt_map,
                                persister=persister,
                            )
                            if not remaining_salts:
                                return
            checked += 1
            offset += 4
    log_wecom(f"cipher struct scan done pid={pid} checked={checked}")


def _scan_process_regions(
    handle: int,
    regions: List[Tuple[int, int]],
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    pid: int,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
    include_struct: bool,
    struct_seconds: float,
    allow_bare_hex: bool,
) -> None:
    hex_matches = 0
    bare_matches = 0
    for base, size in regions:
        if not remaining_salts:
            break
        data = read_process_memory(handle, base, size)
        if not data:
            continue
        hex_matches += _scan_hex_region(
            data,
            db_files,
            key_map,
            remaining_salts,
            pid=pid,
            salt_map=salt_map,
            persister=persister,
        )
        if not remaining_salts:
            break
    if hex_matches:
        log_wecom(f"pid={pid} hex_pattern_matches={hex_matches} keys={len(key_map)}")
    if remaining_salts and include_struct:
        log_wecom(f"pid={pid} trying cipher struct scan ({len(remaining_salts)} salt(s) left)")
        _scan_cipher_structs(
            handle,
            regions,
            db_files,
            key_map,
            remaining_salts,
            pid=pid,
            salt_map=salt_map,
            persister=persister,
            max_seconds=struct_seconds,
        )
    if remaining_salts and allow_bare_hex:
        log_wecom(f"pid={pid} bare hex scan ({len(remaining_salts)} salt(s) left)")
        for base, size in regions:
            if not remaining_salts:
                break
            data = read_process_memory(handle, base, size)
            if not data:
                continue
            bare_matches += _scan_bare_hex_region(
                data,
                db_files,
                key_map,
                remaining_salts,
                pid=pid,
                salt_map=salt_map,
                persister=persister,
            )
            if not remaining_salts:
                break
    if bare_matches:
        log_wecom(f"pid={pid} bare_hex_matches={bare_matches} keys={len(key_map)}")


def _cross_verify_keys(
    db_files: List[DbFileEntry],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    salt_map: Dict[str, List[str]],
    persister: Optional[WeComIncrementalKeyStore] = None,
) -> None:
    if not remaining_salts or not key_map:
        return
    log_wecom(f"cross-verify {len(remaining_salts)} remaining salt(s)")
    for salt_hex in list(remaining_salts):
        for _rel, _path, _size, salt, page1 in db_files:
            if salt != salt_hex:
                continue
            for known_key_hex in key_map.values():
                try:
                    enc_key = bytes.fromhex(known_key_hex)
                except ValueError:
                    continue
                if verify_wxsqlite3_aes128_key(enc_key, page1):
                    key_map[salt_hex] = known_key_hex
                    remaining_salts.discard(salt_hex)
                    log_wecom(f"cross-verify matched salt={salt_hex[:16]}...")
                    if persister is not None:
                        persister.on_salt_found(salt_hex, known_key_hex, salt_map)
                    break
            break


def extract_wecom_db_keys(
    data_dir: Path,
    *,
    persist: Optional[WeComKeyPersistContext] = None,
) -> WeComKeyExtractResult:
    """Scan WXWork memory and return relative-path → hex-key mapping."""
    db_files = [entry for entry in collect_db_files(data_dir) if is_wxsqlite3_aes128_page1(entry[4])]
    if not db_files:
        raise WeComKeyError("no_encrypted_databases")

    pid_rows = _wxwork_pids()
    if not pid_rows:
        raise WeComKeyError("wxwork_not_running")

    salt_map = salt_to_rels(db_files)
    key_map: Dict[str, str] = {}
    remaining_salts: Set[str] = set(salt_map.keys())
    method = "memory_scan"
    started = time.monotonic()
    persister = WeComIncrementalKeyStore(data_dir, persist) if persist is not None else None
    if persister is not None:
        seeded = persister.seed_key_map(db_files, key_map, remaining_salts)
        if seeded:
            log_wecom(
                f"cache seeded unique_salts={seeded} "
                f"rel_keys={len(persister.rel_keys)} remaining={len(remaining_salts)}"
            )
            method = "cached+memory_scan"
        elif persister.cached_count:
            log_wecom(
                f"cached rel_keys={persister.cached_count} but no salt match; rescanning",
                level="WARN",
            )
        if not remaining_salts:
            log_wecom(f"all salts satisfied from cache rel_keys={len(persister.rel_keys)}")
            return WeComKeyExtractResult(keys=persister.rel_keys, method="cached")

    log_wecom(f"encrypted_dbs={len(db_files)} unique_salts={len(salt_map)} wxwork_pids={len(pid_rows)}")

    for index, (pid, mem_kb) in enumerate(pid_rows):
        if not remaining_salts:
            break
        is_primary = index == 0
        log_wecom(
            f"scanning WXWork pid={pid} mem_mb={mem_kb // 1024} "
            f"remaining_salts={len(remaining_salts)} primary={is_primary}"
        )
        handle = _open_process(pid)
        if handle is None:
            log_wecom(f"OpenProcess failed pid={pid} (try Administrator?)", level="WARN")
            continue
        try:
            regions = enum_readable_regions(handle)
            total_mb = sum(size for _base, size in regions) / 1024 / 1024
            log_wecom(f"pid={pid} readable_mb={total_mb:.0f} regions={len(regions)}")
            include_struct = is_primary or len(remaining_salts) > 2
            struct_seconds = _STRUCT_SCAN_SECONDS if is_primary else _SECONDARY_STRUCT_SCAN_SECONDS
            _scan_process_regions(
                handle,
                regions,
                db_files,
                key_map,
                remaining_salts,
                pid=pid,
                salt_map=salt_map,
                persister=persister,
                include_struct=include_struct,
                struct_seconds=struct_seconds,
                allow_bare_hex=is_primary,
            )
        finally:
            _close_process(handle)

        _cross_verify_keys(
            db_files,
            key_map,
            remaining_salts,
            salt_map=salt_map,
            persister=persister,
        )
        if not remaining_salts:
            log_wecom(f"all salts matched after pid={pid}")
            break

    rel_keys = build_key_index(db_files, key_map)
    if persister is not None:
        merged = dict(persister.rel_keys)
        merged.update(rel_keys)
        rel_keys = merged
    elapsed = time.monotonic() - started
    if remaining_salts:
        _log_remaining_salts(remaining_salts, salt_map)
        if _chat_unlock_keys_present(db_files, rel_keys):
            log_wecom(
                f"partial unlock keys={len(rel_keys)}/{len(db_files)} "
                f"optional_missing={len(remaining_salts)} elapsed={elapsed:.1f}s",
                level="WARN",
            )
            return WeComKeyExtractResult(keys=rel_keys, method=method)
        log_wecom(
            f"scan finished in {elapsed:.1f}s keys={len(key_map)}/{len(salt_map)} missing_salts={len(remaining_salts)}",
            level="WARN",
        )
        raise WeComKeyError("keys_not_found")

    if not rel_keys:
        raise WeComKeyError("keys_not_found")
    log_wecom(f"extracted keys={len(rel_keys)} method={method} elapsed={elapsed:.1f}s")
    return WeComKeyExtractResult(keys=rel_keys, method=method)
