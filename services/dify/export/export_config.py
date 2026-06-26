"""
MindMate export tunables (env-backed).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os

from services.dify.export.raw_dump_config import (
    get_export_source,
    resolve_raw_dump_dir,
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


SYNC_MAX_USERS = _env_int("MINDMATE_EXPORT_SYNC_MAX_USERS", 50)
SYNC_MAX_CONVERSATIONS = _env_int("MINDMATE_EXPORT_SYNC_MAX_CONVERSATIONS", 500)
USER_BATCH_SIZE = _env_int("MINDMATE_EXPORT_USER_BATCH_SIZE", 50)
LIST_PAGE_DEFAULT = _env_int("MINDMATE_EXPORT_LIST_PAGE_SIZE", 100)
LIST_PAGE_MAX = 200
BLOCK_ON_GAPS = os.getenv("MINDMATE_EXPORT_BLOCK_ON_GAPS", "false").lower() in ("1", "true", "yes")
SPOT_CHECK_N = _env_int("MINDMATE_EXPORT_VERIFY_SPOT_CHECK_N", 0)
ARTIFACT_TTL_SECONDS = _env_int("MINDMATE_EXPORT_ARTIFACT_TTL_SECONDS", 86400)
STUCK_JOB_SECONDS = _env_int("MINDMATE_EXPORT_STUCK_SECONDS", 1800)

RAW_DUMP_DIR = str(resolve_raw_dump_dir())
EXPORT_SOURCE = get_export_source()
