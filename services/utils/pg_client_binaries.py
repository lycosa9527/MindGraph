"""
Locate PostgreSQL client programs (pg_dump, pg_restore) on the host.

Single implementation shared by admin export/import, CLI dump/import, scheduled
backups, and PG-merge staging restore. Honors PG_BIN_DIR; scans common Linux
layout (versions 18–12), then PATH (which / where).

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import os
import subprocess
import sys
from typing import Optional


def find_pg_client_binary(name: str) -> Optional[str]:
    """
    Return an executable path for *name* (e.g. ``pg_dump``, ``pg_restore``).

    Returns None if no suitable binary is found.
    """
    pg_bin = os.environ.get("PG_BIN_DIR", "")
    paths = [
        os.path.join(pg_bin, name) if pg_bin else "",
        os.path.join(pg_bin, f"{name}.exe") if pg_bin else "",
    ]
    for version in range(18, 11, -1):
        paths.append(f"/usr/lib/postgresql/{version}/bin/{name}")
    paths += [
        f"/usr/local/pgsql/bin/{name}",
        f"/usr/bin/{name}",
        f"/usr/local/bin/{name}",
    ]
    for path in paths:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            return path

    try:
        cmd = ["where", name] if sys.platform == "win32" else ["which", name]
        result = subprocess.run(cmd, capture_output=True, timeout=2, check=False)
        if result.returncode == 0 and result.stdout:
            first_line = result.stdout.decode("utf-8").strip().split("\n")[0]
            found = first_line.strip()
            return found if found else None
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None
