"""
Load and validate Dify raw dump manifest.json snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.dify.export.raw_dump_config import (
    CORE_DUMP_TABLES,
    DUMP_MAX_AGE_SECONDS,
    is_valid_dump_label,
    slot_for_label,
)

logger = logging.getLogger(__name__)


@dataclass
class DumpSnapshot:
    """One extracted raw dump directory with manifest metadata."""

    label: str
    path: Path
    manifest: dict
    mindgraph_slot: int

    @property
    def status(self) -> str:
        """Manifest status field (complete, partial, failed)."""
        return str(self.manifest.get("status") or "unknown")

    @property
    def finished_at(self) -> Optional[datetime]:
        """Parse finished_at from manifest when present."""
        raw = self.manifest.get("finished_at")
        if not raw:
            return None
        try:
            text = str(raw).replace("Z", "+00:00")
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def age_seconds(self, now: Optional[datetime] = None) -> Optional[float]:
        """Seconds since finished_at, or None when timestamp missing."""
        finished = self.finished_at
        if finished is None:
            return None
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=UTC)
        ref = now or datetime.now(UTC)
        return (ref - finished).total_seconds()

    def is_stale(self, max_age_seconds: int = DUMP_MAX_AGE_SECONDS) -> bool:
        """True when snapshot is older than max_age_seconds (library stores never stale)."""
        if str(self.manifest.get("store_kind") or "").strip().lower() == "library":
            return False
        age = self.age_seconds()
        if age is None:
            return True
        return age > float(max_age_seconds)

    def core_tables_present(self) -> bool:
        """True when manifest reports all core tables dumped successfully."""
        tables = self.manifest.get("tables")
        if not isinstance(tables, dict):
            return False
        for name in CORE_DUMP_TABLES:
            entry = tables.get(name)
            if not isinstance(entry, dict):
                return False
            if entry.get("status") != "done":
                return False
        return True

    def is_usable(self) -> bool:
        """True when snapshot can back MindMate export (core CSVs on disk)."""
        if self.status == "failed":
            return False
        if not self.core_tables_present():
            return False
        for name in CORE_DUMP_TABLES:
            csv_path = self.path / f"{name}.csv"
            if not csv_path.is_file():
                return False
        return True


@dataclass
class DumpStoreState:
    """Latest snapshot per server label plus import warnings."""

    snapshots: Dict[str, DumpSnapshot] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def load_manifest_file(path: Path) -> dict:
    """Load manifest.json from disk."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"manifest must be object: {path}")
    return payload


def validate_manifest(manifest: dict, *, expected_label: Optional[str] = None) -> None:
    """Raise ValueError when manifest is missing required fields."""
    label = str(manifest.get("server_label") or "").strip().lower()
    if not is_valid_dump_label(label):
        raise ValueError(f"invalid server_label in manifest: {label!r}")
    if expected_label is not None and label != expected_label.strip().lower():
        raise ValueError(f"manifest server_label={label!r} != expected {expected_label!r}")
    slot = slot_for_label(label)
    if slot is None:
        raise ValueError(f"no MindGraph slot for label {label!r}")


def snapshot_from_dir(path: Path) -> DumpSnapshot:
    """Build DumpSnapshot from an extracted directory."""
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing manifest.json in {path}")
    manifest = load_manifest_file(manifest_path)
    validate_manifest(manifest)
    label = str(manifest["server_label"]).strip().lower()
    slot = slot_for_label(label)
    if slot is None:
        raise ValueError(f"unsupported label {label}")
    return DumpSnapshot(label=label, path=path, manifest=manifest, mindgraph_slot=slot)


def snapshot_finished_epoch(path: Path) -> float:
    """Return finished_at from manifest as sortable epoch, or 0 when missing."""
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return 0.0
    try:
        manifest = load_manifest_file(manifest_path)
        raw = manifest.get("finished_at")
        if not raw:
            return 0.0
        text = str(raw).replace("Z", "+00:00")
        finished = datetime.fromisoformat(text)
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=UTC)
        return finished.timestamp()
    except (OSError, ValueError, TypeError):
        return 0.0


def find_latest_snapshot_for_label(base_dir: Path, label: str) -> Optional[DumpSnapshot]:
    """Return newest usable snapshot under base_dir/label/."""
    label_dir = base_dir / label
    if not label_dir.is_dir():
        return None
    candidates: List[Path] = [
        child for child in label_dir.iterdir() if child.is_dir() and (child / "manifest.json").is_file()
    ]
    if not candidates:
        return None
    for candidate in sorted(candidates, key=snapshot_finished_epoch, reverse=True):
        try:
            snapshot = snapshot_from_dir(candidate)
        except ValueError as exc:
            logger.warning("[RawDump] skip snapshot %s: %s", candidate, exc)
            continue
        if snapshot.is_usable():
            return snapshot
    return None
