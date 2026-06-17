"""
Invitation code utilities

Author: lycosa9527
Made by: MindSpring Team

Functions to generate standardized invitation codes for organizations.
Pattern: XXX-XXX (3 safe chars, dash, 3 safe chars).
Excludes confusing chars: 0, O, 1, I, L (and lowercase o, i, l).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import random
import re
import string
from typing import Optional

# Exclude confusing letters/digits: O, 0, 1, I, L (and lowercase o, i, l)
_CONFUSING_CHARS = frozenset("oO0iIlL1")
_SAFE_CHARS = "".join(c for c in string.ascii_uppercase + string.digits if c not in _CONFUSING_CHARS)

INVITE_PATTERN = re.compile(rf"^[{re.escape(_SAFE_CHARS)}]{{3}}-[{re.escape(_SAFE_CHARS)}]{{3}}$")
# Previous format (AAAA-XXXXX); accepted for lookup until codes are refreshed.
INVITE_PATTERN_LEGACY = re.compile(r"^[A-Z]{4}-[A-Z0-9]{5}$")


def invitation_code_is_valid(candidate: str) -> bool:
    """True if candidate matches the current or legacy invitation code format."""
    return bool(INVITE_PATTERN.fullmatch(candidate) or INVITE_PATTERN_LEGACY.fullmatch(candidate))


def _random_part() -> str:
    """Random part."""
    return "".join(random.choices(_SAFE_CHARS, k=3))


def generate_invitation_code(
    _name: Optional[str] = None,
    _code: Optional[str] = None,
) -> str:
    """
    Generate a random invitation code using the pattern XXX-XXX.

    Legacy callers may pass organization name/code; they are ignored.
    """
    return f"{_random_part()}-{_random_part()}"


def normalize_or_generate(
    invitation_code: Optional[str],
    name: Optional[str],
    code: Optional[str],
) -> str:
    """
    If invitation_code matches the expected pattern, return normalized uppercase.
    Otherwise, generate a new random XXX-XXX code.
    """
    if invitation_code:
        candidate = invitation_code.strip().upper()
        if invitation_code_is_valid(candidate):
            return candidate
    return generate_invitation_code(name, code)
