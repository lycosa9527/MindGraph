"""
Raw Dify dump paths and MindGraph server-label mapping.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

DumpServerLabel = Literal["dify", "neodify"]

DUMP_SERVER_LABELS: tuple[DumpServerLabel, ...] = ("dify", "neodify")

LABEL_TO_MINDGRAPH_SLOT: dict[str, int] = {
    "dify": 1,
    "neodify": 2,
}

SLOT_TO_LABEL: dict[int, DumpServerLabel] = {
    1: "dify",
    2: "neodify",
}

DUMP_TABLES: tuple[str, ...] = (
    "dify_setups",
    "tenants",
    "apps",
    "api_tokens",
    "workflows",
    "end_users",
    "conversations",
    "messages",
    "message_files",
    "message_feedbacks",
    "upload_files",
    "message_chains",
    "message_agent_thoughts",
    "dataset_retriever_resources",
    "workflow_runs",
    "workflow_conversation_variables",
    "workflow_app_logs",
)

CORE_DUMP_TABLES: frozenset[str] = frozenset({"messages", "conversations", "end_users", "apps", "api_tokens"})

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DUMP_REL = "data/dify-dumps"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def resolve_raw_dump_dir() -> Path:
    """
    Absolute path to raw dump storage.

    Relative ``MINDMATE_EXPORT_RAW_DUMP_DIR`` values resolve against the
    MindGraph project root (same anchor as ``temp_exports/``), so Celery
    workers find dumps regardless of process CWD.
    """
    raw = os.getenv("MINDMATE_EXPORT_RAW_DUMP_DIR", _DEFAULT_DUMP_REL).strip() or _DEFAULT_DUMP_REL
    path = Path(raw)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path


def get_export_source() -> str:
    """Export source is dump-only; live Dify API collection is disabled."""
    return "dump"


def get_dump_max_upload_bytes() -> int:
    """Read max admin upload size from env at call time."""
    return _env_int("MINDMATE_EXPORT_DUMP_MAX_UPLOAD_BYTES", 5 * 1024 * 1024 * 1024)


def get_dump_max_age_seconds() -> int:
    """Read max snapshot age from env at call time."""
    return _env_int("MINDMATE_EXPORT_DUMP_MAX_AGE_SECONDS", 7 * 24 * 3600)


DUMP_MAX_AGE_SECONDS = get_dump_max_age_seconds()
DUMP_MAX_UPLOAD_BYTES = get_dump_max_upload_bytes()
DUMP_MAX_EXTRACT_BYTES = _env_int(
    "MINDMATE_EXPORT_DUMP_MAX_EXTRACT_BYTES",
    DUMP_MAX_UPLOAD_BYTES * 3,
)
DUMP_MAX_ZIP_MEMBERS = _env_int("MINDMATE_EXPORT_DUMP_MAX_ZIP_MEMBERS", 512)


def label_for_slot(server: int) -> Optional[DumpServerLabel]:
    """Map MindGraph export server slot to dump folder label."""
    return SLOT_TO_LABEL.get(int(server))


def slot_for_label(label: str) -> Optional[int]:
    """Map dump manifest server_label to MindGraph export server slot."""
    normalized = label.strip().lower()
    return LABEL_TO_MINDGRAPH_SLOT.get(normalized)


def is_valid_dump_label(label: str) -> bool:
    """Return True when label is a supported dump server name."""
    return label.strip().lower() in LABEL_TO_MINDGRAPH_SLOT
