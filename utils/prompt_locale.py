"""
Map API language codes to prompt-registry template keys and optional LLM output hints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from utils.prompt_output_languages import (
    OUTPUT_LANGUAGE_ENGLISH_NAMES,
    is_prompt_output_language,
)


def template_lang_for_registry(lang: str) -> str:
    """Registry keys exist for zh and en only; map Chinese variants to zh, else en."""
    normalized = (lang or "en").lower().strip()
    if normalized in ("zh", "zh-hant"):
        return "zh"
    return "en"


def output_language_instruction(lang: str) -> str:
    """
    Meta-instruction appended to LLM prompts so generation matches the API language.

    Registry templates may be Chinese or English; for other codes, templates still
    load English keys — this block tells the model the target output language.
    """
    normalized = (lang or "en").lower().strip()
    if not is_prompt_output_language(normalized):
        normalized = "en"
    separator = "\n\n---\n"
    if normalized == "zh":
        return (
            f"{separator}"
            "【输出语言】请使用**简体中文**撰写全部面向用户的文本"
            "（含 JSON 字符串值、标签、说明、枚举等）。\n"
            "Output language: **Simplified Chinese** for all user-visible text."
        )
    if normalized in ("zh-hant", "zh-tw"):
        return (
            f"{separator}"
            "【輸出語言】請使用**繁體中文**撰寫全部面向使用者的文字"
            "（含 JSON 字串值、標籤、說明、枚舉等）。\n"
            "Output language: **Traditional Chinese** for all user-visible text."
        )
    if normalized == "az":
        return (
            f"{separator}"
            "Output language: **Azerbaijani** (Latin script) for all user-visible text "
            "(including JSON string values, labels, and explanations).\n"
            "İstifadəçiyə görünən bütün mətnlər Azərbaycan dilində (latın əlifbası) olsun."
        )
    if normalized == "en":
        return (
            f"{separator}"
            "Output language: **English** for all user-visible text "
            "(including JSON string values, labels, and explanations)."
        )
    label = OUTPUT_LANGUAGE_ENGLISH_NAMES.get(normalized, "English")
    return (
        f"{separator}"
        f"Output language: **{label}** for all user-visible text "
        "(including JSON string values, labels, and explanations)."
    )
