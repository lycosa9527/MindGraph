"""
Resolve active Dify dump store (merged library preferred over latest snapshot).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.dify.export.raw_dump_config import DUMP_MAX_AGE_SECONDS, DUMP_SERVER_LABELS, resolve_raw_dump_dir
from services.dify.export.raw_dump_library import find_library_snapshot
from services.dify.export.raw_dump_manifest import DumpStoreState, find_latest_snapshot_for_label


def resolve_dump_store(
    base_dir: Optional[Path] = None,
    *,
    max_age_seconds: int = DUMP_MAX_AGE_SECONDS,
) -> DumpStoreState:
    """Resolve merged library per label, falling back to latest snapshot."""
    root = base_dir or resolve_raw_dump_dir()
    state = DumpStoreState()
    for label in DUMP_SERVER_LABELS:
        snapshot = find_library_snapshot(root, label)
        if snapshot is None:
            snapshot = find_latest_snapshot_for_label(root, label)
        if snapshot is None:
            continue
        state.snapshots[label] = snapshot
        if str(snapshot.manifest.get("store_kind") or "").strip().lower() != "library" and snapshot.is_stale(
            max_age_seconds
        ):
            state.warnings.append(f"dump_stale: label={label} path={snapshot.path}")
    return state
