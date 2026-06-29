"""Local WeCom (WXWork) desktop client detection."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from file_reader.wecom.discovery import (
    WeComDataRoot,
    collect_db_files,
    count_wxsqlite3_dbs,
    infer_user_id,
    iter_account_candidates,
    pick_best_account,
    wxwork_documents_root,
)

_WXWORK_PROCESS = "WXWork.exe"


@dataclass(frozen=True)
class WeComLocalStatus:
    """Snapshot of WeCom desktop availability on this PC."""

    process_running: bool
    data_root: Optional[Path]
    account_label: Optional[str]
    user_id: Optional[int]
    encrypted_db_count: int
    wxsqlite3_db_count: int

    @property
    def local_dbs_present(self) -> bool:
        """True when encrypted WeCom databases exist locally."""
        return self.data_root is not None and self.encrypted_db_count > 0

    @property
    def unlock_ready(self) -> bool:
        """True when encrypted databases exist and WXWork is running for key scan."""
        return self.local_dbs_present and self.process_running


def _wxwork_process_running() -> bool:
    if sys.platform != "win32":
        return False
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
    except (OSError, subprocess.SubprocessError):
        return False
    return _WXWORK_PROCESS.lower() in result.stdout.lower()


def detect_wecom_local() -> WeComLocalStatus:
    """Inspect WXWork process and local encrypted message store."""
    running = _wxwork_process_running()
    candidates = list(iter_account_candidates())
    account = pick_best_account(candidates)
    if account is None:
        return WeComLocalStatus(
            process_running=running,
            data_root=None,
            account_label=None,
            user_id=None,
            encrypted_db_count=0,
            wxsqlite3_db_count=0,
        )
    db_files = collect_db_files(account.data_dir)
    encrypted_count = sum(1 for _rel, _path, _size, _salt, page1 in db_files if page1[:16] != b"SQLite format 3")
    return WeComLocalStatus(
        process_running=running,
        data_root=account.data_dir,
        account_label=account.account_label,
        user_id=infer_user_id(account.data_dir),
        encrypted_db_count=encrypted_count,
        wxsqlite3_db_count=count_wxsqlite3_dbs(db_files),
    )


def account_from_status(status: WeComLocalStatus) -> Optional[WeComDataRoot]:
    """Rebuild account candidate from a status snapshot."""
    if status.data_root is None:
        return None
    db_files = collect_db_files(status.data_root)
    encrypted = [entry for entry in db_files if entry[4][:16] != b"SQLite format 3"]
    if not encrypted:
        return None
    label = status.account_label or status.data_root.parent.name
    return WeComDataRoot(
        data_dir=status.data_root,
        account_label=label,
        db_mtime=status.data_root.stat().st_mtime,
        encrypted_db_count=len(encrypted),
    )


def documents_root_display() -> str:
    """Human-readable default WXWork documents path."""
    return str(wxwork_documents_root())
