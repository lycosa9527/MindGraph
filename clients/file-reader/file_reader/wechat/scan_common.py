"""Shared Windows memory scan helpers for WeChat key extraction."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import re
import struct
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from file_reader.win32_ctypes import windll_module
from file_reader.wechat.crypto import (
    KEY_SZ,
    derive_enc_key_from_passphrase,
    verify_enc_key,
    verify_passphrase,
)

SaltKeyCallback = Callable[[str, str], None]

_MEM_COMMIT = 0x1000
_MEM_PRIVATE = 0x20000
_PAGE_READWRITE = 0x04
_READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}
_MIN_V4_REGION = 1024 * 1024
_V4_KEY_PATTERN = bytes(
    [
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x20,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x2F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)
_V41_CHUNK = 4 * 1024 * 1024
_V41_CHUNK_OVERLAP = 32
_MAX_V41_SCAN_BYTES = 256 * 1024 * 1024
_DEFAULT_MAX_PBKDF2 = 24


class MemoryBasicInformation(ctypes.Structure):
    """Win32 MEMORY_BASIC_INFORMATION layout for VirtualQueryEx."""

    _fields_ = [
        ("base_address", ctypes.c_uint64),
        ("allocation_base", ctypes.c_uint64),
        ("allocation_protect", wt.DWORD),
        ("partition_id", wt.DWORD),
        ("region_size", ctypes.c_uint64),
        ("state", wt.DWORD),
        ("protect", wt.DWORD),
        ("type", wt.DWORD),
        ("attributes", wt.DWORD),
    ]


def scan_memory_for_keys(
    data: bytes,
    hex_pattern: re.Pattern[bytes],
    db_files: List[Tuple[str, Path, int, str, bytes]],
    key_map: Dict[str, str],
    remaining_salts: Set[str],
    *,
    on_salt_found: Optional[SaltKeyCallback] = None,
) -> int:
    """Scan a memory chunk for SQLCipher x'hex' key patterns."""
    matches = 0
    for match in hex_pattern.finditer(data):
        hex_str = match.group(1).decode()
        matches += 1
        hex_len = len(hex_str)

        if hex_len == 96:
            enc_key_hex = hex_str[:64]
            salt_hex = hex_str[64:]
            if salt_hex in remaining_salts:
                enc_key = bytes.fromhex(enc_key_hex)
                for _rel, _path, _size, salt, page1 in db_files:
                    if salt == salt_hex and verify_enc_key(enc_key, page1):
                        key_map[salt_hex] = enc_key_hex
                        remaining_salts.discard(salt_hex)
                        if on_salt_found is not None:
                            on_salt_found(salt_hex, enc_key_hex)
                        break
        elif hex_len == 64:
            if not remaining_salts:
                continue
            enc_key_hex = hex_str
            enc_key = bytes.fromhex(enc_key_hex)
            for _rel, _path, _size, salt_hex_db, page1 in db_files:
                if salt_hex_db in remaining_salts and verify_enc_key(enc_key, page1):
                    key_map[salt_hex_db] = enc_key_hex
                    remaining_salts.discard(salt_hex_db)
                    if on_salt_found is not None:
                        on_salt_found(salt_hex_db, enc_key_hex)
                    break
        elif hex_len > 96 and hex_len % 2 == 0:
            enc_key_hex = hex_str[:64]
            salt_hex = hex_str[-32:]
            if salt_hex in remaining_salts:
                enc_key = bytes.fromhex(enc_key_hex)
                for _rel, _path, _size, salt, page1 in db_files:
                    if salt == salt_hex and verify_enc_key(enc_key, page1):
                        key_map[salt_hex] = enc_key_hex
                        remaining_salts.discard(salt_hex)
                        if on_salt_found is not None:
                            on_salt_found(salt_hex, enc_key_hex)
                        break
    return matches


def cross_verify_keys(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    salt_to_rels: Dict[str, List[str]],
    key_map: Dict[str, str],
    *,
    on_salt_found: Optional[SaltKeyCallback] = None,
) -> None:
    """Fill missing salts when one derived key decrypts multiple DBs."""
    missing = set(salt_to_rels.keys()) - set(key_map.keys())
    if not missing or not key_map:
        return
    for salt_hex in list(missing):
        for _rel, _path, _size, salt, page1 in db_files:
            if salt != salt_hex:
                continue
            for known_key_hex in key_map.values():
                enc_key = bytes.fromhex(known_key_hex)
                if verify_enc_key(enc_key, page1):
                    key_map[salt_hex] = known_key_hex
                    missing.discard(salt_hex)
                    if on_salt_found is not None:
                        on_salt_found(salt_hex, known_key_hex)
                    break
            break


def build_key_index(
    db_files: List[Tuple[str, Path, int, str, bytes]],
    key_map: Dict[str, str],
) -> Dict[str, str]:
    """Map db relative paths to derived encryption keys."""
    result: Dict[str, str] = {}
    for rel, _path, _size, salt_hex, _page1 in db_files:
        enc_key = key_map.get(salt_hex)
        if enc_key:
            result[rel] = enc_key
    return result


def enum_readable_regions(process_handle: int) -> List[Tuple[int, int]]:
    """Return readable committed memory regions for a process."""
    kernel32 = windll_module("kernel32")
    regions: List[Tuple[int, int]] = []
    address = 0
    info = MemoryBasicInformation()
    while address < 0x7FFFFFFFFFFF:
        if (
            kernel32.VirtualQueryEx(
                process_handle,
                ctypes.c_uint64(address),
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            == 0
        ):
            break
        if info.state == _MEM_COMMIT and info.protect in _READABLE and 0 < info.region_size < 500 * 1024 * 1024:
            regions.append((info.base_address, info.region_size))
        next_addr = info.base_address + info.region_size
        if next_addr <= address:
            break
        address = next_addr
    return regions


def enum_v4_private_regions(process_handle: int) -> List[Tuple[int, int]]:
    """Writable private regions (>= 1 MiB) used by WeChat 4.1+ key scan."""
    kernel32 = windll_module("kernel32")
    regions: List[Tuple[int, int]] = []
    address = 0x10000
    info = MemoryBasicInformation()
    while address < 0x7FFFFFFFFFFF:
        if (
            kernel32.VirtualQueryEx(
                process_handle,
                ctypes.c_uint64(address),
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            == 0
        ):
            break
        if (
            info.state == _MEM_COMMIT
            and (info.protect & _PAGE_READWRITE) != 0
            and info.type == _MEM_PRIVATE
            and info.region_size >= _MIN_V4_REGION
        ):
            regions.append((info.base_address, info.region_size))
        next_addr = info.base_address + info.region_size
        if next_addr <= address:
            break
        address = next_addr
    return regions


def read_process_memory(process_handle: int, address: int, size: int) -> Optional[bytes]:
    """Read bytes from another process."""
    kernel32 = windll_module("kernel32")
    buffer = ctypes.create_string_buffer(size)
    read_size = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(
        process_handle,
        ctypes.c_uint64(address),
        buffer,
        size,
        ctypes.byref(read_size),
    ):
        return buffer.raw[: read_size.value]
    return None


def scan_v4_passphrase_in_chunk(
    memory: bytes,
    process_handle: int,
    reference_page1: bytes,
    seen_pointers: Set[int],
    *,
    max_pbkdf2_checks: int = _DEFAULT_MAX_PBKDF2,
) -> Optional[bytes]:
    """Find WCDB passphrase via chatlog V4 struct pattern in one memory chunk."""
    pbkdf2_checks = 0
    index = len(memory)
    while index > 0:
        found = memory.rfind(_V4_KEY_PATTERN, 0, index)
        if found < 0 or found < 8:
            break
        index = found
        ptr_value = struct.unpack("<Q", memory[found - 8 : found])[0]
        if ptr_value <= 0x10000 or ptr_value >= 0x7FFFFFFFFFFF:
            continue
        if ptr_value in seen_pointers:
            continue
        seen_pointers.add(ptr_value)
        key_data = read_process_memory(process_handle, ptr_value, KEY_SZ)
        if key_data is None or len(key_data) != KEY_SZ:
            continue
        if pbkdf2_checks >= max_pbkdf2_checks:
            break
        pbkdf2_checks += 1
        if verify_passphrase(key_data, reference_page1):
            return key_data
    return None


def derive_keys_from_passphrase(
    passphrase: bytes,
    db_files: List[Tuple[str, Path, int, str, bytes]],
) -> Dict[str, str]:
    """Derive per-salt encryption keys from a WeChat 4.1+ passphrase."""
    key_map: Dict[str, str] = {}
    for _rel, _path, _size, salt_hex, page1 in db_files:
        salt = bytes.fromhex(salt_hex)
        enc_key = derive_enc_key_from_passphrase(passphrase, salt)
        if verify_enc_key(enc_key, page1):
            key_map[salt_hex] = enc_key.hex()
    return key_map
