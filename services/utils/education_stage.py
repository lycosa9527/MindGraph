"""Education-stage (学段) allowlist for AI diagram generation prefs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

EDUCATION_STAGES = (
    "小学",
    "初中",
    "高中",
    "大学",
    "成人",
    "专家",
)

EDUCATION_STAGE_SET = frozenset(EDUCATION_STAGES)


def is_valid_education_stage(value: str | None) -> bool:
    """Return True when value is a known education stage label."""
    if value is None:
        return False
    return value.strip() in EDUCATION_STAGE_SET
