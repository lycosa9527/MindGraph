"""
Unit tests for Simplified Chinese detection and thinking-mode language overrides.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from utils.chinese_language_policy import (
    effective_language_for_thinking_user,
    is_chinese_ui_error_language,
    text_contains_simplified_chinese_glyphs,
)


class _AllowsSc:
    def __init__(self, allows: bool) -> None:
        self.allows_simplified_chinese = allows


def test_text_contains_simplified_chinese_glyphs_common_han_false() -> None:
    """Shared single characters with no SC-specific form should not flip s2t."""
    assert text_contains_simplified_chinese_glyphs("\u4e00") is False


def test_text_contains_simplified_chinese_glyphs_sc_word_true() -> None:
    """Typical simplified-only word should change under OpenCC s2t."""
    assert text_contains_simplified_chinese_glyphs("\u8f6f\u4ef6") is True


def test_text_contains_simplified_chinese_glyphs_empty() -> None:
    assert text_contains_simplified_chinese_glyphs("") is False
    assert text_contains_simplified_chinese_glyphs("   ") is False


def test_effective_language_allows_sc_passthrough() -> None:
    user = _AllowsSc(True)
    assert effective_language_for_thinking_user(user, "en", "\u8f6f\u4ef6") == "en"
    assert effective_language_for_thinking_user(user, "zh", "") == "zh"


def test_effective_language_no_sc_explicit_zh_to_zh_tw() -> None:
    user = _AllowsSc(False)
    assert effective_language_for_thinking_user(user, "zh", "") == "zh-tw"


def test_effective_language_no_sc_detected_sc_to_zh_tw() -> None:
    user = _AllowsSc(False)
    assert effective_language_for_thinking_user(user, "en", "\u8f6f\u4ef6") == "zh-tw"


def test_effective_language_no_sc_no_detection_keeps_en() -> None:
    user = _AllowsSc(False)
    assert effective_language_for_thinking_user(user, "en", "\u4e00") == "en"


def test_effective_language_no_sc_none_user_treated_allowing() -> None:
    assert effective_language_for_thinking_user(None, "zh", "") == "zh"


def test_is_chinese_ui_error_language() -> None:
    assert is_chinese_ui_error_language("zh") is True
    assert is_chinese_ui_error_language("zh-TW") is True
    assert is_chinese_ui_error_language("zh-hant") is True
    assert is_chinese_ui_error_language("en") is False
