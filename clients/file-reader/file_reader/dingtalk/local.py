"""Local DingTalk desktop client detection."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from file_reader.dingtalk.crypto import DingTalkStorageVersion
from file_reader.dingtalk.discovery import (
    DingTalkAccountCandidate,
    dingtalk_roaming_root,
    iter_account_candidates,
    pick_best_account,
    read_v3_salt,
    resolve_key_uid,
)

_DINGTALK_PROCESS = "DingTalk.exe"


@dataclass(frozen=True)
class DingTalkLocalStatus:
    """Snapshot of DingTalk desktop availability on this PC."""

    process_running: bool
    data_root: Optional[Path]
    account_folder_id: Optional[str]
    storage_version: Optional[DingTalkStorageVersion]
    real_uid: Optional[str]
    uid_source: Optional[str]
    salt_present: bool
    db_present: bool

    @property
    def local_dbs_present(self) -> bool:
        """True when an encrypted account database exists locally."""
        return self.db_present and self.data_root is not None

    @property
    def unlock_ready(self) -> bool:
        """True when uid (and V3 salt) are available for decryption."""
        if not self.local_dbs_present or self.real_uid is None:
            return False
        if self.storage_version == "v3":
            return self.salt_present
        return True


def _dingtalk_process_running() -> bool:
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_DINGTALK_PROCESS}", "/FO", "CSV", "/NH"],
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
    return _DINGTALK_PROCESS.lower() in result.stdout.lower()


def detect_dingtalk_local() -> DingTalkLocalStatus:
    """Inspect DingTalk process and local encrypted message store."""
    running = _dingtalk_process_running()
    root = dingtalk_roaming_root()
    candidates = list(iter_account_candidates(root))
    account = pick_best_account(candidates)
    if account is None:
        return DingTalkLocalStatus(
            process_running=running,
            data_root=None,
            account_folder_id=None,
            storage_version=None,
            real_uid=None,
            uid_source=None,
            salt_present=False,
            db_present=False,
        )
    real_uid, uid_source = resolve_key_uid(account, log_dir=root / "log")
    salt = read_v3_salt(account.user_config_path) if account.version == "v3" else None
    return DingTalkLocalStatus(
        process_running=running,
        data_root=account.data_dir,
        account_folder_id=account.folder_id,
        storage_version=account.version,
        real_uid=real_uid,
        uid_source=uid_source,
        salt_present=bool(salt),
        db_present=True,
    )


def account_from_status(status: DingTalkLocalStatus) -> Optional[DingTalkAccountCandidate]:
    """Rebuild account candidate from a status snapshot."""
    if status.data_root is None or status.storage_version is None:
        return None
    db_path = status.data_root / "DBFiles" / "dingtalk.db"
    if not db_path.is_file():
        return None
    folder_id = status.account_folder_id or status.data_root.name.rsplit("_", 1)[0]
    return DingTalkAccountCandidate(
        data_dir=status.data_root,
        folder_id=folder_id,
        version=status.storage_version,
        db_path=db_path,
        user_config_path=status.data_root / "user_config",
        db_mtime=db_path.stat().st_mtime,
    )
