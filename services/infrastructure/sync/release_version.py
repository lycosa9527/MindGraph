"""
Semver-style release version comparison for COS mirror sync.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations


def compare_release_versions(left: str, right: str) -> int:
    """Return -1 if left<right, 0 if equal, 1 if left>right."""

    def _parts(value: str) -> list[int]:
        return [int(part) for part in value.lstrip("v").split(".") if part.isdigit()]

    left_parts = _parts(left)
    right_parts = _parts(right)
    length = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (length - len(left_parts)))
    right_parts.extend([0] * (length - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0
