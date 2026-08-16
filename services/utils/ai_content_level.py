"""Mind-map 专业程度 allowlist for user preference persistence.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

AI_CONTENT_LEVELS = (
    "general",
    "primary",
    "junior",
    "senior",
    "university",
    "adult",
    "expert",
)

AI_CONTENT_LEVEL_SET = frozenset(AI_CONTENT_LEVELS)


def is_valid_ai_content_level(value: str | None) -> bool:
    """Return True when value is a known mind-map 专业程度 id."""
    if value is None:
        return False
    return value.strip() in AI_CONTENT_LEVEL_SET
