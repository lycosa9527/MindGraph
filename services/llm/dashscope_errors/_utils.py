"""
Utility functions for DashScope error parsing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import re


def has_chinese_characters(text: str) -> bool:
    """
    Check if text contains Chinese characters.
    More robust than checking for 'zh' substring.

    Args:
        text: Text to check

    Returns:
        True if text contains Chinese characters
    """
    return bool(re.search(r"[\u4e00-\u9fff]", text))
