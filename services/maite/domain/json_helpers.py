"""
JSON parsing helpers for Maite LLM outputs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Optional

from agents.core.json_parser import extract_json_from_response
from services.utils.error_types import JSON_PARSE_ERRORS


def parse_llm_json(raw: str, *, fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Parse JSON from an LLM response with repair and fallback."""
    parsed = extract_json_from_response(raw, allow_partial=True)
    if isinstance(parsed, dict):
        return parsed
    try:
        loaded = json.loads(raw.strip())
        if isinstance(loaded, dict):
            return loaded
    except (*JSON_PARSE_ERRORS,):
        pass
    return dict(fallback or {})
