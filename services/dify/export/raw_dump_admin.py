"""
Admin operations for Dify raw dump zips and extracted snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.dify.export.raw_dump_config import (
    DUMP_SERVER_LABELS,
    get_dump_max_age_seconds,
    get_dump_max_upload_bytes,
    is_valid_dump_label,
    resolve_raw_dump_dir,
)
from services.dify.export.raw_dump_import import (
    INCOMING_DIRNAME,
    import_pending_zips,
    import_zip_file,
    peek_manifest_from_zip,
)
from services.dify.export.raw_dump_library import (
    find_library_snapshot,
    library_inventory_row,
    rebuild_library_from_snapshots,
)
from services.dify.export.raw_dump_index import MultiServerDumpStore
from services.dify.export.raw_dump_manifest import (
    DumpSnapshot,
    snapshot_finished_epoch,
    find_latest_snapshot_for_label,
    snapshot_from_dir,
)

_SAFE_ZIP_NAME = re.compile(r"^[A-Za-z0-9._-]+\.zip$")


def dump_root() -> Path:
    """Resolved absolute dump directory."""
    return resolve_raw_dump_dir()


def _incoming_dir(root: Path) -> Path:
    path = root / INCOMING_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_incoming_filename(raw: str) -> str:
    """Validate upload filename; raise ValueError when unsafe."""
    name = Path(raw).name.strip()
    if not name or not _SAFE_ZIP_NAME.match(name):
        raise ValueError("filename must match [A-Za-z0-9._-]+.zip")
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("invalid filename")
    return name


def _snapshot_row(snapshot: DumpSnapshot) -> dict:
    manifest = snapshot.manifest
    tables = manifest.get("tables")
    message_rows = 0
    if isinstance(tables, dict):
        messages_entry = tables.get("messages")
        if isinstance(messages_entry, dict):
            message_rows = int(messages_entry.get("rows") or 0)
    return {
        "label": snapshot.label,
        "mindgraph_server_slot": snapshot.mindgraph_slot,
        "timestamp": snapshot.path.name,
        "status": snapshot.status,
        "usable": snapshot.is_usable(),
        "stale": snapshot.is_stale(),
        "finished_at": manifest.get("finished_at"),
        "duration_seconds": manifest.get("duration_seconds"),
        "message_rows": message_rows,
    }


def _incoming_row(path: Path) -> dict:
    row: dict = {
        "name": path.name,
        "bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "server_label": None,
        "manifest_status": None,
        "peek_error": None,
    }
    try:
        manifest = peek_manifest_from_zip(path)
        row["server_label"] = str(manifest.get("server_label") or "").lower() or None
        row["manifest_status"] = manifest.get("status")
    except (OSError, ValueError) as exc:
        row["peek_error"] = str(exc)
    return row


def list_dump_inventory(base_dir: Optional[Path] = None) -> dict:
    """Full inventory for admin UI: incoming zips + snapshots per label."""
    root = base_dir or dump_root()
    incoming = _incoming_dir(root)
    incoming_rows = sorted(
        [_incoming_row(item) for item in incoming.glob("*.zip") if item.is_file()],
        key=lambda item: str(item["name"]),
        reverse=True,
    )
    labels_payload: Dict[str, dict] = {}
    for label in DUMP_SERVER_LABELS:
        label_dir = root / label
        snapshots: List[dict] = []
        if label_dir.is_dir():
            for child in sorted(label_dir.iterdir(), key=snapshot_finished_epoch, reverse=True):
                if not child.is_dir() or not (child / "manifest.json").is_file():
                    continue
                try:
                    snapshots.append(_snapshot_row(snapshot_from_dir(child)))
                except ValueError:
                    continue
        active = find_library_snapshot(root, label)
        if active is None:
            active = find_latest_snapshot_for_label(root, label)
        labels_payload[label] = {
            "library": library_inventory_row(root, label),
            "active_snapshot": _snapshot_row(active) if active is not None else None,
            "snapshots": snapshots,
        }
    store = MultiServerDumpStore.load(root)
    return {
        "dump_root": str(root.resolve()),
        "max_upload_bytes": get_dump_max_upload_bytes(),
        "max_age_seconds": get_dump_max_age_seconds(),
        "incoming": incoming_rows,
        "labels": labels_payload,
        "data_source_summary": store.data_source_summary(),
    }


@dataclass
class UploadResult:
    """Outcome of saving one uploaded zip to incoming/."""

    path: Path
    bytes_written: int
    server_label: Optional[str]


async def save_uploaded_zip(
    filename: str,
    stream,
    *,
    base_dir: Optional[Path] = None,
) -> UploadResult:
    """
    Stream an uploaded zip into incoming/.

    ``stream`` must support async read(size) (FastAPI UploadFile).
    """
    root = base_dir or dump_root()
    safe_name = safe_incoming_filename(filename)
    dest = _incoming_dir(root) / safe_name
    partial = dest.with_suffix(dest.suffix + ".partial")
    if dest.exists():
        raise ValueError(f"incoming zip already exists: {safe_name}")
    total = 0
    try:
        with partial.open("wb") as handle:
            while True:
                chunk = await stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                max_upload = get_dump_max_upload_bytes()
                if total > max_upload:
                    raise ValueError(f"upload exceeds max size ({max_upload} bytes)")
                handle.write(chunk)
        partial.replace(dest)
    except (OSError, ValueError):
        partial.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise
    server_label: Optional[str] = None
    try:
        manifest = peek_manifest_from_zip(dest)
        server_label = str(manifest.get("server_label") or "").lower() or None
    except (OSError, ValueError):
        server_label = None
    return UploadResult(path=dest, bytes_written=total, server_label=server_label)


def import_pending(base_dir: Optional[Path] = None) -> dict:
    """Import all zips in incoming/; return serializable result."""
    result = import_pending_zips(base_dir)
    return {
        "imported": [str(path) for path in result.imported],
        "skipped": list(result.skipped),
        "errors": list(result.errors),
    }


def import_incoming_file(filename: str, base_dir: Optional[Path] = None) -> dict:
    """Import one named zip from incoming/."""
    root = base_dir or dump_root()
    safe_name = safe_incoming_filename(filename)
    zip_path = _incoming_dir(root) / safe_name
    if not zip_path.is_file():
        raise FileNotFoundError(safe_name)
    extracted = import_zip_file(zip_path, root, move_to_done=True)
    return {"imported": str(extracted), "name": safe_name}


def delete_incoming_file(filename: str, base_dir: Optional[Path] = None) -> None:
    """Remove one zip from incoming/ (not .done/)."""
    root = base_dir or dump_root()
    safe_name = safe_incoming_filename(filename)
    zip_path = _incoming_dir(root) / safe_name
    if not zip_path.is_file():
        raise FileNotFoundError(safe_name)
    zip_path.unlink()


def delete_snapshot(label: str, timestamp: str, base_dir: Optional[Path] = None) -> None:
    """Remove one extracted snapshot directory and rebuild the merged library."""
    normalized_label = label.strip().lower()
    if not is_valid_dump_label(normalized_label):
        raise ValueError(f"invalid label: {label}")
    if not timestamp or "/" in timestamp or "\\" in timestamp or ".." in timestamp:
        raise ValueError("invalid snapshot timestamp")
    root = base_dir or dump_root()
    target = (root / normalized_label / timestamp).resolve()
    label_root = (root / normalized_label).resolve()
    try:
        target.relative_to(label_root)
    except ValueError as exc:
        raise ValueError("snapshot path outside dump root") from exc
    if not target.is_dir():
        raise FileNotFoundError(str(target))
    shutil.rmtree(target)
    rebuild_library_from_snapshots(root, normalized_label)
