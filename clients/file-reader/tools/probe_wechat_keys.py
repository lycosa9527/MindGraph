"""Diagnose WeChat WCDB key extraction on Windows (dev tool)."""

from __future__ import annotations

import ctypes
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_wcdb = importlib.import_module("file_reader.wechat.wcdb")
_enum_readable_regions = _wcdb._enum_readable_regions
_read_process_memory = _wcdb._read_process_memory
_weixin_pids = _wcdb._weixin_pids
collect_db_files = _wcdb.collect_db_files


def main() -> None:
    kernel32 = ctypes.windll.kernel32
    db_dir = Path(r"C:\Users\roywa\Documents\xwechat_files\rulerwang_c571\db_storage")
    if len(sys.argv) > 1:
        db_dir = Path(sys.argv[1])

    print("db_dir:", db_dir)
    db_files, salt_to_rels = collect_db_files(db_dir)
    print(f"databases: {len(db_files)}, unique salts: {len(salt_to_rels)}")

    pids = _weixin_pids()
    print(f"Weixin.exe PIDs: {pids}")
    if not pids:
        print("FAIL: no Weixin.exe process")
        return

    access = 0x0010 | 0x0400
    opened = 0
    bytes_read = 0
    regions_read = 0
    for pid in pids:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            err = kernel32.GetLastError()
            print(f"OpenProcess PID={pid} FAILED GetLastError={err}")
            continue
        opened += 1
        try:
            regions = _enum_readable_regions(handle)
            print(f"PID={pid}: {len(regions)} readable regions")
            for base, size in regions[:5]:
                data = _read_process_memory(handle, base, size)
                if data:
                    regions_read += 1
                    bytes_read += len(data)
            if len(regions) > 5:
                for base, size in regions[5:]:
                    data = _read_process_memory(handle, base, size)
                    if data:
                        regions_read += 1
                        bytes_read += len(data)
        finally:
            kernel32.CloseHandle(handle)

    print(f"opened={opened}/{len(pids)} regions_read={regions_read} bytes_read={bytes_read}")
    if opened == 0:
        print("LIKELY CAUSE: access denied — try Run as administrator")
    elif bytes_read == 0:
        print("LIKELY CAUSE: ReadProcessMemory blocked")
    else:
        print("Memory readable — key pattern may be absent (WeChat version / need to open chats)")


if __name__ == "__main__":
    main()
