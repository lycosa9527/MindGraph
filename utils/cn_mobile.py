"""
Chinese mainland mobile number predicate (11 digits, starts with 1).

Matches registration rules in models/requests/requests_auth.py RegisterRequest.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional


def is_cn_mainland_mobile(phone: Optional[str]) -> bool:
    """True if the value is an 11-digit mainland China mobile number (starts with 1)."""
    if not phone:
        return False
    candidate = str(phone).strip()
    if len(candidate) != 11:
        return False
    if not candidate.isdigit():
        return False
    return candidate.startswith("1")
