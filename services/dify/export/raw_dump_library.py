"""
Merge raw dump snapshots into a cumulative Dify library per server label.

Each import appends into ``library/{dify|neodify}/`` (CSVs + manifest).
MindMate export and filters read the library, not individual snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from services.dify.export.raw_dump_config import CORE_DUMP_TABLES, DUMP_TABLES, slot_for_label
from services.dify.export.raw_dump_manifest import DumpSnapshot, snapshot_finished_epoch, snapshot_from_dir
from services.dify.export.raw_message_adapter import conversation_updated_at

logger = logging.getLogger(__name__)

LIBRARY_DIRNAME = "library"
LIBRARY_STORE_KIND = "library"


def library_path_for_label(base_dir: Path, label: str) -> Path:
    """Directory holding merged CSV library for one server label."""
    return base_dir / LIBRARY_DIRNAME / label.strip().lower()


def _read_csv_table(path: Path, table: str = "") -> Tuple[List[str], Dict[str, dict]]:
    if not path.is_file():
        return [], {}
    rows_by_key: Dict[str, dict] = {}
    fieldnames: List[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            key = _row_key(table, row, fieldnames)
            if key is None:
                continue
            rows_by_key[key] = dict(row)
    return fieldnames, rows_by_key


def _write_csv_table(path: Path, fieldnames: List[str], rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_fields = list(fieldnames)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered_fields, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _row_key(table: str, row: dict, _fieldnames: List[str]) -> Optional[str]:
    if table == "api_tokens":
        token = str(row.get("token") or "").strip()
        return token or None
    if table == "message_feedbacks":
        message_id = str(row.get("message_id") or "").strip()
        return message_id or None
    row_id = str(row.get("id") or "").strip()
    if row_id:
        return row_id
    if _fieldnames:
        fallback = str(row.get(_fieldnames[0]) or "").strip()
        return fallback or None
    return None


def _merge_fieldnames(existing: List[str], incoming: List[str]) -> List[str]:
    merged = list(existing)
    for name in incoming:
        if name not in merged:
            merged.append(name)
    return merged


def _should_replace_row(table: str, existing: dict, incoming: dict) -> bool:
    if table == "conversations":
        return conversation_updated_at(incoming) >= conversation_updated_at(existing)
    return True


def merge_csv_table(
    library_dir: Path,
    snapshot_dir: Path,
    table: str,
) -> int:
    """Upsert one table CSV from snapshot into the library directory."""
    snap_csv = snapshot_dir / f"{table}.csv"
    if not snap_csv.is_file():
        lib_csv = library_dir / f"{table}.csv"
        if not lib_csv.is_file():
            return 0
        _, existing = _read_csv_table(lib_csv, table)
        return len(existing)

    lib_csv = library_dir / f"{table}.csv"
    lib_fields, lib_rows = _read_csv_table(lib_csv, table)
    snap_fields, snap_map = _read_csv_table(snap_csv, table)
    fieldnames = _merge_fieldnames(lib_fields, snap_fields)

    for key, row in snap_map.items():
        if key in lib_rows and not _should_replace_row(table, lib_rows[key], row):
            continue
        lib_rows[key] = row

    return _write_csv_table(lib_csv, fieldnames, lib_rows.values())


def _load_library_manifest(library_dir: Path) -> dict:
    path = library_dir / "manifest.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _count_table_rows(library_dir: Path, table: str) -> int:
    csv_path = library_dir / f"{table}.csv"
    if not csv_path.is_file():
        return 0
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return sum(1 for _ in reader)


def _build_tables_summary(library_dir: Path) -> dict:
    summary: dict = {}
    for table in DUMP_TABLES:
        rows = _count_table_rows(library_dir, table)
        if rows > 0:
            summary[table] = {"status": "done", "rows": rows}
    for name in CORE_DUMP_TABLES:
        if name not in summary:
            summary[name] = {"status": "missing", "rows": 0}
    return summary


def _write_library_manifest(
    library_dir: Path,
    *,
    label: str,
    snapshot: DumpSnapshot,
    merged_snapshot_id: str,
    prior: dict,
) -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    merged_list = list(prior.get("merged_snapshots") or [])
    if not isinstance(merged_list, list):
        merged_list = []
    entry = {
        "snapshot_id": merged_snapshot_id,
        "finished_at": snapshot.manifest.get("finished_at"),
        "merged_at": now,
    }
    if not merged_list or merged_list[-1].get("snapshot_id") != merged_snapshot_id:
        merged_list.append(entry)
    slot = slot_for_label(label)
    manifest = {
        "status": "complete",
        "store_kind": LIBRARY_STORE_KIND,
        "server_label": label,
        "mindgraph_server_slot": slot,
        "started_at": prior.get("started_at") or snapshot.manifest.get("started_at") or now,
        "finished_at": snapshot.manifest.get("finished_at") or now,
        "last_merged_at": now,
        "duration_seconds": snapshot.manifest.get("duration_seconds"),
        "merged_snapshots": merged_list,
        "tables": _build_tables_summary(library_dir),
        "errors": [],
    }
    with (library_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


def merge_snapshot_into_library(base_dir: Path, snapshot_dir: Path) -> Path:
    """
    Merge one extracted snapshot directory into library/{label}/.

    Returns path to the library directory.
    """
    snapshot = snapshot_from_dir(snapshot_dir)
    if not snapshot.is_usable():
        raise ValueError(f"snapshot not usable for library merge: {snapshot_dir}")
    label = snapshot.label
    library_dir = library_path_for_label(base_dir, label)
    library_dir.mkdir(parents=True, exist_ok=True)
    prior = _load_library_manifest(library_dir)

    tables_present = [
        table for table in DUMP_TABLES if (snapshot_dir / f"{table}.csv").is_file()
    ]
    for table in tables_present:
        merge_csv_table(library_dir, snapshot_dir, table)

    snapshot_id = snapshot_dir.name
    _write_library_manifest(
        library_dir,
        label=label,
        snapshot=snapshot,
        merged_snapshot_id=snapshot_id,
        prior=prior,
    )
    logger.info(
        "[RawDump] merged snapshot %s into library/%s (tables=%s)",
        snapshot_id,
        label,
        len(tables_present),
    )
    return library_dir


def find_library_snapshot(base_dir: Path, label: str) -> Optional[DumpSnapshot]:
    """Return usable library DumpSnapshot for label when present."""
    library_dir = library_path_for_label(base_dir, label)
    if not (library_dir / "manifest.json").is_file():
        return None
    try:
        snapshot = snapshot_from_dir(library_dir)
    except ValueError as exc:
        logger.warning("[RawDump] library manifest invalid for %s: %s", label, exc)
        return None
    if snapshot.is_usable():
        return snapshot
    return None


def rebuild_library_from_snapshots(base_dir: Path, label: str) -> Optional[Path]:
    """Rebuild library/{label}/ from all archived snapshots (newest merge order)."""
    label_dir = base_dir / label
    if not label_dir.is_dir():
        return None
    library_dir = library_path_for_label(base_dir, label)
    if library_dir.exists():
        shutil.rmtree(library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        [
            child
            for child in label_dir.iterdir()
            if child.is_dir() and (child / "manifest.json").is_file()
        ],
        key=snapshot_finished_epoch,
    )
    merged_any = False
    for candidate in candidates:
        try:
            merge_snapshot_into_library(base_dir, candidate)
            merged_any = True
        except ValueError as exc:
            logger.warning("[RawDump] skip rebuild merge %s: %s", candidate, exc)
    if not merged_any:
        shutil.rmtree(library_dir, ignore_errors=True)
        return None
    return library_dir


def library_inventory_row(base_dir: Path, label: str) -> Optional[dict]:
    """Serializable library summary for admin UI."""
    snapshot = find_library_snapshot(base_dir, label)
    if snapshot is None:
        return None
    manifest = snapshot.manifest
    merged = manifest.get("merged_snapshots")
    merged_count = len(merged) if isinstance(merged, list) else 0
    tables = manifest.get("tables")
    message_rows = 0
    conversation_rows = 0
    if isinstance(tables, dict):
        messages_entry = tables.get("messages")
        if isinstance(messages_entry, dict):
            message_rows = int(messages_entry.get("rows") or 0)
        conv_entry = tables.get("conversations")
        if isinstance(conv_entry, dict):
            conversation_rows = int(conv_entry.get("rows") or 0)
    return {
        "label": label,
        "mindgraph_server_slot": snapshot.mindgraph_slot,
        "merged_snapshot_count": merged_count,
        "last_merged_at": manifest.get("last_merged_at"),
        "message_rows": message_rows,
        "conversation_rows": conversation_rows,
        "usable": True,
    }
