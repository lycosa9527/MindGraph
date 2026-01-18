"""
Invitation code utilities

Author: lycosa9527
Made by: MindSpring Team

Functions to generate standardized invitation codes for organizations.
Pattern: 4 letters (from name/code) + '-' + 5 uppercase letters/digits

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional
import random
import re
import string


INVITE_PATTERN = re.compile(r"^[A-Z]{4}-[A-Z0-9]{5}$")


def _extract_alpha_prefix(source: Optional[str]) -> str:
    if not source:
        return ""
    # Keep only ASCII letters and uppercase
    letters = re.findall(r"[A-Za-z]", source)
    prefix = ("".join(letters)).upper()[:4]
    return prefix


def generate_invitation_code(name: Optional[str], code: Optional[str]) -> str:
    """
    Generate an invitation code using the pattern: AAAA-XXXXX
    - Prefix AAAA: first 4 ASCII letters from school name; fallback to code; pad with X
    - Suffix XXXXX: 5 random uppercase letters/digits
    """
    prefix = _extract_alpha_prefix(name)
    if len(prefix) < 1:
        prefix = _extract_alpha_prefix(code)
    if len(prefix) < 4:
        prefix = (prefix + "XXXX")[:4]

    suffix_chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(suffix_chars, k=5))
    return f"{prefix}-{suffix}"


def normalize_or_generate(invitation_code: Optional[str], name: Optional[str], code: Optional[str]) -> str:
    """
    If invitation_code matches the expected pattern, return normalized uppercase.
    Otherwise, generate a new one from name/code.
    """
    if invitation_code:
        candidate = invitation_code.strip().upper()
        if INVITE_PATTERN.fullmatch(candidate):
            return candidate
    return generate_invitation_code(name, code)
