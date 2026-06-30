"""
Local Qdrant COS update state (version tracking for install/rollback audit).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _state_path() -> Path:
    override = os.getenv("QDRANT_UPDATE_STATE_FILE", "").strip()
    if override:
        path = Path(override)
        return path if path.is_absolute() else Path(__file__).resolve().parents[3] / path
    return Path(__file__).resolve().parents[3] / "data" / "qdrant" / "update_state.json"


def read_qdrant_update_state() -> Optional[Dict[str, Any]]:
    """Load last recorded Qdrant COS update."""
    path = _state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_qdrant_update_state(payload: Dict[str, Any]) -> Path:
    """Persist update outcome."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path
