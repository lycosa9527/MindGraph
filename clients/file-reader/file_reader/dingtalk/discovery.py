"""Discover DingTalk desktop data directories and V3 key material."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Literal, Optional, Tuple

from file_reader.dingtalk.crypto import DingTalkStorageVersion

_REAL_UID_RE = re.compile(r"real_uid[=:\s]+(\d{6,12})", re.IGNORECASE)
_ACCOUNT_DIR_RE = re.compile(r"^(.+)_(v2|v3)$", re.IGNORECASE)


@dataclass(frozen=True)
class DingTalkAccountCandidate:
    """One local DingTalk account data directory."""

    data_dir: Path
    folder_id: str
    version: DingTalkStorageVersion
    db_path: Path
    user_config_path: Path
    db_mtime: float


def dingtalk_roaming_root() -> Path:
    """Return ``%AppData%\\Roaming\\DingTalk`` when present."""
    appdata = Path.home() / "AppData" / "Roaming" / "DingTalk"
    if appdata.is_dir():
        return appdata
    local = Path.home() / "AppData" / "Local" / "DingTalk"
    return local if local.is_dir() else appdata


def iter_account_candidates(root: Optional[Path] = None) -> Iterator[DingTalkAccountCandidate]:
    """Yield ``*_v2`` / ``*_v3`` account folders that contain ``dingtalk.db``."""
    base = root or dingtalk_roaming_root()
    if not base.is_dir():
        return
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        match = _ACCOUNT_DIR_RE.match(entry.name)
        if match is None:
            continue
        db_path = entry / "DBFiles" / "dingtalk.db"
        if not db_path.is_file():
            continue
        version: DingTalkStorageVersion = "v3" if match.group(2).lower() == "v3" else "v2"
        yield DingTalkAccountCandidate(
            data_dir=entry,
            folder_id=match.group(1),
            version=version,
            db_path=db_path,
            user_config_path=entry / "user_config",
            db_mtime=db_path.stat().st_mtime,
        )


def pick_best_account(candidates: List[DingTalkAccountCandidate]) -> Optional[DingTalkAccountCandidate]:
    """Prefer V3, then most recently modified DB."""
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.version == "v3", item.db_mtime), reverse=True)[0]


def read_v3_salt(user_config_path: Path) -> Optional[str]:
    """Read hex salt from Base64 ``user_config`` JSON."""
    if not user_config_path.is_file():
        return None
    try:
        raw = user_config_path.read_text(encoding="utf-8").strip()
        decoded = base64.b64decode(raw).decode("utf-8")
        payload = json.loads(decoded)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    salt = payload.get("salt") or payload.get("slt")
    if isinstance(salt, str) and salt.strip():
        return salt.strip()
    return None


def find_real_uid_in_logs(log_dir: Path, *, max_files: int = 12) -> Optional[str]:
    """Search recent ``gaea.log*`` files for ``real_uid``."""
    if not log_dir.is_dir():
        return None
    log_files = sorted(
        (path for path in log_dir.iterdir() if path.is_file() and path.name.startswith("gaea.log")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in log_files[:max_files]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = _REAL_UID_RE.search(text)
        if match:
            return match.group(1)
    return None


def resolve_key_uid(
    account: DingTalkAccountCandidate,
    *,
    log_dir: Optional[Path] = None,
) -> Tuple[str, Literal["folder", "log", "v2_folder"]]:
    """Return UID string used for key derivation and how it was resolved."""
    if account.version == "v2":
        return account.folder_id, "v2_folder"
    logs = log_dir if log_dir is not None else account.data_dir.parent / "log"
    real_uid = find_real_uid_in_logs(logs)
    if real_uid:
        return real_uid, "log"
    if account.folder_id.isdigit():
        return account.folder_id, "folder"
    return account.folder_id, "folder"
