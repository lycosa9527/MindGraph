"""Detect local WeChat / Weixin client state on Windows (v3, v4, v4.1)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Optional, Tuple

winreg: Any = None
if sys.platform == "win32":
    import winreg as _winreg_module

    winreg = _winreg_module

from file_reader.wechat.version import (
    detect_client_exe_version,
    detect_running_process,
    format_client_version,
    infer_layout_variant,
    key_extraction_plan,
    requires_wx_key_hook,
    resolve_crypto_variant,
)
from file_reader.wechat.wxkey_dll import find_wx_key_dll
from file_reader.windows_paths import dedupe_existing, iter_documents_directories

_SKIP_DIR_NAMES = frozenset(
    {
        "All Users",
        "all_users",
        "Applet",
        "WMPF",
        "Backup",
        "BackupFiles",
        "config",
        "head_imgs",
        "sqlite",
    }
)

_V3_PROCESS_NAMES = ("WeChat.exe",)
_V4_PROCESS_NAMES = ("Weixin.exe",)
_V3_PROCESS = _V3_PROCESS_NAMES[0]
_V4_PROCESS = _V4_PROCESS_NAMES[0]

# WeChat 3.x message stores (under each wxid account folder).
_V3_MESSAGE_DB_DIRS = (
    ("Msg", "Multi"),
    ("Msg",),
    ("msg", "Multi"),
    ("msg",),
)

# Weixin 4.x message stores (under each account folder).
_V4_MESSAGE_DB_DIRS = (
    ("db_storage", "message"),
    ("msg",),
)

_V3_DATA_DIR_NAMES = ("WeChat Files",)
_V4_DATA_DIR_NAMES = ("xwechat_files", "Weixin Files")


@dataclass(frozen=True)
class WeChatLocalStatus:
    """Snapshot of WeChat desktop client availability."""

    process_running: bool
    data_root: Optional[Path]
    wxid: Optional[str]
    db_count: int
    client_variant: Optional[str] = None
    key_db_found: bool = False
    weixin_version: Optional[str] = None
    process_image: Optional[str] = None
    key_methods: tuple[str, ...] = ()
    requires_wx_key_hook: bool = False
    wx_key_dll_present: bool = False

    @property
    def local_dbs_present(self) -> bool:
        """True when encrypted WeChat databases exist on disk for an account."""
        return self.db_count > 0 and self.wxid is not None and self.data_root is not None

    @property
    def db_ready(self) -> bool:
        """True when logged-in client likely has readable message databases."""
        return self.process_running and self.db_count > 0 and self.wxid is not None

    @property
    def live_db_ready(self) -> bool:
        """True when local DB files exist and a probe could be attempted."""
        return self.db_ready and self.client_variant in {"v3", "v4", "v4.1"} and self.data_root is not None


def _tasklist_has(image_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
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
    return image_name.lower() in result.stdout.lower()


def wechat_process_running() -> bool:
    """Return True if WeChat 3.x or Weixin 4.x is running."""
    if sys.platform != "win32":
        return False
    for name in _V3_PROCESS_NAMES + _V4_PROCESS_NAMES:
        if _tasklist_has(name):
            return True
    return False


def _registry_path(key_path: str, value_name: str) -> Optional[Path]:
    if sys.platform != "win32" or winreg is None:
        return None

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(os.path.expandvars(value.strip()))
    return path if path.exists() else None


def _registry_data_roots() -> List[Path]:
    roots: List[Path] = []
    for key_path, value_name in (
        (r"Software\Tencent\WeChat", "FileSavePath"),
        (r"Software\Tencent\Weixin", "FileSavePath"),
        (r"Software\Tencent\WeChat", "InstallPath"),
        (r"Software\Tencent\Weixin", "InstallPath"),
    ):
        path = _registry_path(key_path, value_name)
        if path is None:
            continue
        if path.is_dir():
            roots.append(path)
            continue
        parent = path.parent
        if parent.is_dir():
            roots.append(parent)
    return roots


def collect_wechat_data_roots() -> List[Path]:
    """All known WeChat v3 / Weixin v4 data root directories."""
    roots: List[Path] = []
    for docs in iter_documents_directories():
        for folder_name in _V3_DATA_DIR_NAMES + _V4_DATA_DIR_NAMES:
            roots.append(docs / folder_name)
    roots.extend(_registry_data_roots())
    return dedupe_existing(roots)


def _count_dbs_in_dir(msg_dir: Path, *, max_depth: int = 3) -> int:
    if not msg_dir.is_dir():
        return 0
    count = 0
    for path in msg_dir.rglob("*.db"):
        if not path.is_file():
            continue
        try:
            depth = len(path.relative_to(msg_dir).parts)
        except ValueError:
            depth = 0
        if depth <= max_depth:
            count += 1
    return count


def _message_db_count(account_dir: Path) -> Tuple[int, Optional[str]]:
    """Count message DBs and return (count, client variant hint)."""
    best = 0
    variant: Optional[str] = None
    for parts in _V4_MESSAGE_DB_DIRS:
        count = _count_dbs_in_dir(account_dir.joinpath(*parts))
        if count > best:
            best = count
            variant = "v4"
    for parts in _V3_MESSAGE_DB_DIRS:
        count = _count_dbs_in_dir(account_dir.joinpath(*parts))
        if count > best:
            best = count
            variant = "v3"
    micro = account_dir / "MicroMsg.db"
    if micro.is_file():
        best = max(best, 1)
        variant = variant or "v3"
    if best:
        return best, variant
    storage = account_dir / "db_storage"
    if storage.is_dir():
        count = _count_dbs_in_dir(storage)
        if count > best:
            return count, "v4"
    return best, variant


def _key_db_found(data_root: Path, account_name: str) -> bool:
    """Weixin 4.x stores login key material under all_users/login/<user>/."""
    login_dir = data_root / "all_users" / "login" / account_name
    key_file = login_dir / "key_info.db"
    return key_file.is_file()


def _account_label(folder_name: str) -> str:
    if folder_name.startswith("wxid_"):
        return folder_name[5:]
    if "_" in folder_name:
        prefix = folder_name.rsplit("_", 1)[0]
        if prefix:
            return prefix
    return folder_name


def _iter_account_dirs(data_root: Path) -> Iterator[Tuple[Path, str]]:
    """Yield (account_dir, label) for v3 and v4 layouts under a data root."""
    root_name = data_root.name.lower()
    if root_name in {name.lower() for name in _V4_DATA_DIR_NAMES}:
        login_root = data_root / "all_users" / "login"
        if login_root.is_dir():
            try:
                login_entries = list(login_root.iterdir())
            except OSError:
                login_entries = []
            for entry in login_entries:
                if entry.is_dir() and entry.name not in _SKIP_DIR_NAMES:
                    yield entry, entry.name
        try:
            top_entries = list(data_root.iterdir())
        except OSError:
            top_entries = []
        for entry in top_entries:
            if not entry.is_dir() or entry.name in _SKIP_DIR_NAMES or entry.name.startswith("."):
                continue
            yield entry, _account_label(entry.name)
        return

    try:
        entries = list(data_root.iterdir())
    except OSError:
        return
    for entry in entries:
        if not entry.is_dir() or entry.name in _SKIP_DIR_NAMES or entry.name.startswith("."):
            continue
        yield entry, _account_label(entry.name)


def _best_account(data_roots: Iterable[Path]) -> Tuple[Optional[Path], Optional[str], int, Optional[str], bool]:
    best_dir: Optional[Path] = None
    best_label: Optional[str] = None
    best_count = 0
    best_variant: Optional[str] = None
    best_key = False

    for data_root in data_roots:
        for account_dir, label in _iter_account_dirs(data_root):
            db_count, variant = _message_db_count(account_dir)
            key_found = _key_db_found(data_root, label)
            score = db_count + (2 if key_found else 0)
            best_score = best_count + (2 if best_key else 0)
            if score > best_score:
                best_dir = account_dir
                best_label = label
                best_count = db_count
                best_variant = variant
                best_key = key_found
            elif score == best_score and db_count > best_count:
                best_dir = account_dir
                best_label = label
                best_count = db_count
                best_variant = variant
                best_key = key_found

    return best_dir, best_label, best_count, best_variant, best_key


def _read_client_version_snapshot() -> tuple[Optional[str], Optional[tuple[int, int, int, int]], str]:
    """Detect running client and PE version before account / DB inspection."""
    process_image = detect_running_process()
    version_tuple: Optional[tuple[int, int, int, int]] = None
    if process_image == _V4_PROCESS:
        version_tuple = detect_client_exe_version(layout="v4")
    elif process_image == _V3_PROCESS:
        version_tuple = detect_client_exe_version(layout="v3")
    else:
        version_tuple = detect_client_exe_version(layout="v4")
        if version_tuple is None:
            version_tuple = detect_client_exe_version(layout="v3")
    return process_image, version_tuple, format_client_version(version_tuple)


def _resolve_account_crypto(
    account_dir: Optional[Path],
    layout_hint: Optional[str],
    *,
    version_tuple: Optional[tuple[int, int, int, int]],
    process_image: Optional[str],
) -> tuple[Optional[str], Optional[str], tuple[str, ...], Optional[str], bool, bool]:
    """Return (crypto, version_label, key_methods, process_image, hook_required, dll_present)."""
    dll_present = find_wx_key_dll() is not None
    if account_dir is not None:
        layout = infer_layout_variant(account_dir)
    elif layout_hint == "v3" or process_image == _V3_PROCESS:
        layout = "v3"
    else:
        layout = "v4"
    active_version = version_tuple
    if active_version is None:
        active_version = detect_client_exe_version(layout=layout)
    if layout == "v3":
        crypto = "v3"
        hook_required = False
    else:
        crypto = resolve_crypto_variant("v4", weixin_version=active_version)
        hook_required = crypto == "v4.1" and requires_wx_key_hook(active_version)
    version_label = format_client_version(active_version)
    methods = key_extraction_plan(crypto, weixin_version=active_version)
    return crypto, version_label, methods, process_image, hook_required, dll_present


def detect_wechat_local() -> WeChatLocalStatus:
    """Inspect WeChat / Weixin process and local SQLite message stores."""
    process_image, version_tuple, _version_label = _read_client_version_snapshot()
    running = wechat_process_running()
    data_roots = collect_wechat_data_roots()
    account_dir, wxid, db_count, layout_hint, key_db = _best_account(data_roots)
    crypto, version_label, methods, process_image, hook_required, dll_present = _resolve_account_crypto(
        account_dir,
        layout_hint,
        version_tuple=version_tuple,
        process_image=process_image,
    )
    return WeChatLocalStatus(
        process_running=running,
        data_root=account_dir,
        wxid=wxid,
        db_count=db_count,
        client_variant=crypto,
        key_db_found=key_db,
        weixin_version=version_label,
        process_image=process_image,
        key_methods=methods,
        requires_wx_key_hook=hook_required,
        wx_key_dll_present=dll_present,
    )
