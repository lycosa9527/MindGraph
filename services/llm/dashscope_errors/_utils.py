import re


"""
Utility functions for DashScope error parsing.
"""



def has_chinese_characters(text: str) -> bool:
    """
    Check if text contains Chinese characters.
    More robust than checking for 'zh' substring.

    Args:
        text: Text to check

    Returns:
        True if text contains Chinese characters
    """
    return bool(re.search(r'[\u4e00-\u9fff]', text))
