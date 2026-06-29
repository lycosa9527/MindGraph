"""Diagnose WeChat 4.1 passphrase scan: pattern hits, pointer reads, PBKDF2 cap."""

from __future__ import annotations

from file_reader.win32_ctypes import windll_module
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from file_reader.wechat.crypto import KEY_SZ, collect_db_files, verify_passphrase
from file_reader.wechat.scan_common import (
    _DEFAULT_MAX_PBKDF2,
    _MAX_V41_SCAN_BYTES,
    _V4_KEY_PATTERN,
    enum_v4_private_regions,
    read_process_memory,
)


def weixin_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=8,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    pids: list[int] = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            try:
                pids.append(int(parts[1]))
            except ValueError:
                continue
    return pids


def main() -> None:
    db_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
    db_files, _salt = collect_db_files(db_dir)
    reference = next(page1 for rel, _p, _s, _salt, page1 in db_files if "message/message_" in rel)

    kernel32 = windll_module("kernel32")
    access = 0x0010 | 0x0400
    pid_list = weixin_pids()
    print(f"weixin_pids={pid_list}")
    if not pid_list:
        print("Weixin.exe not running")
        return

    for pid in pid_list:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            print(f"pid={pid} OpenProcess failed")
            continue
        try:
            regions = enum_v4_private_regions(handle)
            pattern_hits = 0
            pointers: set[int] = set()
            readable_pointers = 0
            cap_stops = 0
            pbkdf2_tried = 0
            scanned_bytes = 0
            found = False
            chunk_size = 4 * 1024 * 1024
            overlap = 32

            for base, size in regions:
                offset = 0
                trailing: bytes | None = None
                while offset < size and scanned_bytes < _MAX_V41_SCAN_BYTES:
                    read_size = min(chunk_size, size - offset)
                    chunk = read_process_memory(handle, base + offset, read_size)
                    offset += read_size
                    scanned_bytes += read_size
                    if not chunk:
                        trailing = None
                        continue
                    data = trailing + chunk if trailing else chunk
                    index = len(data)
                    checks_in_chunk = 0
                    while index > 0:
                        hit = data.rfind(_V4_KEY_PATTERN, 0, index)
                        if hit < 0 or hit < 8:
                            break
                        index = hit
                        pattern_hits += 1
                        ptr_value = struct.unpack("<Q", data[hit - 8 : hit])[0]
                        if ptr_value <= 0x10000 or ptr_value >= 0x7FFFFFFFFFFF:
                            continue
                        if ptr_value in pointers:
                            continue
                        pointers.add(ptr_value)
                        key_data = read_process_memory(handle, ptr_value, KEY_SZ)
                        if key_data is None or len(key_data) != KEY_SZ:
                            continue
                        readable_pointers += 1
                        if checks_in_chunk >= _DEFAULT_MAX_PBKDF2:
                            cap_stops += 1
                            break
                        checks_in_chunk += 1
                        pbkdf2_tried += 1
                        if verify_passphrase(key_data, reference):
                            print(f"PASSPHRASE FOUND pid={pid} ptr={ptr_value:#x}")
                            found = True
                            break
                    if found:
                        break
                    start = max(0, len(data) - overlap)
                    trailing = data[start:]
                if found:
                    break

            print(
                f"pid={pid} regions={len(regions)} "
                f"scanned_mb={scanned_bytes // (1024 * 1024)} "
                f"pattern_hits={pattern_hits} unique_ptrs={len(pointers)} "
                f"readable_ptrs={readable_pointers} pbkdf2_tried={pbkdf2_tried} "
                f"cap_stops={cap_stops}"
            )
        finally:
            kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
