"""Discover WeCom (WXWork) data directories and encrypted databases."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from file_reader.wecom.crypto import PAGE_SZ, is_plain_sqlite_page, is_wxsqlite3_aes128_page1


@dataclass(frozen=True)
class WeComDataRoot:
    """One local WeCom account data directory."""

    data_dir: Path
    account_label: str
    db_mtime: float
    encrypted_db_count: int


DbFileEntry = Tuple[str, Path, int, str, bytes]


def wxwork_documents_root() -> Path:
    """Return ``%UserProfile%\\Documents\\WXWork``."""
    profile = os.environ.get("USERPROFILE", "")
    return Path(profile) / "Documents" / "WXWork"


def _data_dir_mtime(data_dir: Path) -> float:
    latest = 0.0
    for root, dirs, files in os.walk(data_dir):
        dirs[:] = [name for name in dirs if name not in ("-journal",)]
        for name in files:
            if not name.endswith((".db", ".db-wal", ".db-shm")):
                continue
            path = Path(root) / name
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    try:
        latest = max(latest, data_dir.stat().st_mtime)
    except OSError:
        pass
    return latest


def _has_encrypted_db(data_dir: Path) -> bool:
    for _rel, _path, _size, _salt, page1 in collect_db_files(data_dir):
        if not is_plain_sqlite_page(page1):
            return True
    return False


def iter_wxwork_data_dirs(root: Optional[Path] = None) -> Iterator[Path]:
    """Yield ``...\\Data`` directories under ``Documents\\WXWork``."""
    base = root or wxwork_documents_root()
    if not base.is_dir():
        return
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        direct = entry / "Data"
        if direct.is_dir():
            yield direct
            continue
        for nested in sorted(entry.iterdir()):
            if nested.is_dir():
                candidate = nested / "Data"
                if candidate.is_dir():
                    yield candidate


def iter_account_candidates(root: Optional[Path] = None) -> Iterator[WeComDataRoot]:
    """Yield WXWork data roots that contain at least one encrypted database."""
    for data_dir in iter_wxwork_data_dirs(root):
        entries = collect_db_files(data_dir)
        encrypted = [entry for entry in entries if not is_plain_sqlite_page(entry[4])]
        if not encrypted:
            continue
        label = data_dir.parent.name
        if data_dir.parent.parent.name.lower() != "wxwork":
            label = f"{data_dir.parent.parent.name}/{label}"
        yield WeComDataRoot(
            data_dir=data_dir,
            account_label=label,
            db_mtime=_data_dir_mtime(data_dir),
            encrypted_db_count=len(encrypted),
        )


def pick_best_account(candidates: List[WeComDataRoot]) -> Optional[WeComDataRoot]:
    """Prefer the most recently active account data directory."""
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.db_mtime, reverse=True)[0]


def collect_db_files(data_dir: Path) -> List[DbFileEntry]:
    """Collect ``.db`` files with page-1 salt fingerprints."""
    db_files: List[DbFileEntry] = []
    for root, dirs, files in os.walk(data_dir):
        dirs[:] = [name for name in dirs if name not in ("-journal",)]
        for name in files:
            if not name.endswith(".db") or name.endswith("-wal") or name.endswith("-shm"):
                continue
            path = Path(root) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size < PAGE_SZ:
                continue
            try:
                page1 = path.read_bytes()[:PAGE_SZ]
            except OSError:
                continue
            rel = path.relative_to(data_dir).as_posix()
            salt = page1[:16].hex()
            db_files.append((rel, path, size, salt, page1))
    return db_files


def salt_to_rels(db_files: List[DbFileEntry]) -> Dict[str, List[str]]:
    """Map salt hex strings to relative database paths."""
    mapping: Dict[str, List[str]] = {}
    for rel, _path, _size, salt, _page1 in db_files:
        mapping.setdefault(salt, []).append(rel)
    return mapping


def infer_user_id(data_dir: Path) -> Optional[int]:
    """Best-effort numeric user id from the data directory path."""
    for part in reversed(data_dir.parts):
        if part.isdigit() and len(part) >= 6:
            return int(part)
    return None


def count_wxsqlite3_dbs(db_files: List[DbFileEntry]) -> int:
    """Count databases whose page 1 matches wxSQLite3 AES-128 layout."""
    return sum(1 for _rel, _path, _size, _salt, page1 in db_files if is_wxsqlite3_aes128_page1(page1))


def normalize_db_rel(rel: str) -> str:
    """Normalize a database relative path to forward slashes."""
    return rel.replace("\\", "/")


def is_session_db_rel(rel: str) -> bool:
    """Return True for ``session.db`` in flat or nested WeCom layouts."""
    return normalize_db_rel(rel) in ("session.db", "session/session.db")


def is_chat_db_rel(rel: str) -> bool:
    """Return True for databases needed to list chats (not CRM/calendar/etc.)."""
    norm = normalize_db_rel(rel)
    if is_session_db_rel(norm):
        return True
    if norm in ("user.db", "user/user.db", "message.db"):
        return True
    if norm.startswith("message_") and norm.endswith(".db"):
        return True
    return norm.startswith("message/") and norm.endswith(".db")
