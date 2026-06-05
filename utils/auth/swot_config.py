"""
SWOT academic email env configuration (no imports from swot_academic or email policy).
"""

from __future__ import annotations

import os
from typing import FrozenSet

_DEFAULT_PURPOSES = "register"


def _parse_purpose_set(raw: str) -> FrozenSet[str]:
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return frozenset(parts) if parts else frozenset({"register"})


def swot_academic_email_required() -> bool:
    """Read SWOT_ACADEMIC_EMAIL_REQUIRED on each call (default false)."""
    return os.getenv("SWOT_ACADEMIC_EMAIL_REQUIRED", "false").strip().lower() == "true"


def swot_enforce_purposes() -> FrozenSet[str]:
    raw = os.getenv("SWOT_ACADEMIC_EMAIL_PURPOSES", _DEFAULT_PURPOSES).strip()
    return _parse_purpose_set(raw)


def is_swot_academic_required_for_purpose(purpose: str) -> bool:
    if not swot_academic_email_required():
        return False
    return purpose.lower() in swot_enforce_purposes()
