"""Normalize ``Diagram.spec`` values read from PostgreSQL JSONB.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict


def coerce_diagram_spec(raw: Any) -> Dict[str, Any]:
    """
    Return a dict spec from a JSONB column value.

    A leftover full-flush path stored ``json.dumps(snapshot)`` as a JSON string
    scalar. Readers must unwrap that so live-spec seed and library GET stay
    objects. Invalid or non-object values become ``{}``.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace")
    elif isinstance(raw, str):
        text = raw
    else:
        return {}
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
