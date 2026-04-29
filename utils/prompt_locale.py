"""
Map API language codes to prompt-registry template keys and optional LLM output hints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from utils.prompt_output_languages import (
    OUTPUT_LANGUAGE_ENGLISH_NAMES,
    is_prompt_output_language,
)


def is_chinese_prompt_shell_language(language: str) -> bool:
    """
    True when prompts should use Chinese-script instruction shells (简体中文-dominant
    copy in this repo). Matches :func:`output_language_instruction` Simplified and
    Traditional API groupings; exact output script remains defined by that footer.

    Includes common region tags (zh-cn, zh-hans, zh-sg, zh-tw, zh-hk, zh-mo, zh-hant).
    """
    lo = (language or "").strip().lower().replace("_", "-")
    if lo == "zh":
        return True
    if lo in ("zh-cn", "zh-hans", "zh-sg"):
        return True
    if lo in ("zh-hant", "zh-tw", "zh-hk", "zh-mo"):
        return True
    return False


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

    Chinese script variants are resolved before the registry guard so that codes
    like zh-tw / zh-hk / zh-mo always produce the correct Traditional Chinese footer
    even if they are not individually listed in the prompt output registry.
    """
    normalized = (lang or "en").lower().strip()
    separator = "\n\n---\n"
    if normalized == "zh":
        return (
            f"{separator}"
            "【输出语言】请使用**简体中文**撰写全部面向用户的文本"
            "（含 JSON 字符串值、标签、说明、枚举等）。\n"
            "Output language: **Simplified Chinese** for all user-visible text."
        )
    if normalized in ("zh-hant", "zh-tw", "zh-hk", "zh-mo"):
        return (
            f"{separator}"
            "【輸出語言】請使用**繁體中文**撰寫全部面向使用者的文字"
            "（含 JSON 字串值、標籤、說明、枚舉等）。\n"
            "Output language: **Traditional Chinese** for all user-visible text."
        )
    if not is_prompt_output_language(normalized):
        normalized = "en"
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


def build_web_page_content_user_block(
    page_content: str,
    language: str,
    content_format: str,
    page_title: Optional[str] = None,
    page_url: Optional[str] = None,
) -> str:
    """
    User message wrapper for web-content mind map generation.

    Simplified vs Traditional Chinese get matching labels; other languages use the English shell
    and rely on the system prompt + :func:`output_language_instruction` for target output.
    """
    title_raw = (page_title or "").strip()
    url_raw = (page_url or "").strip()
    lang = (language or "en").lower().strip().replace("_", "-")
    is_markdown = content_format == "text/markdown"
    fmt_latin = "markdown" if is_markdown else "plain text"
    fmt_zh_s = "Markdown" if is_markdown else "纯文本"
    fmt_zh_t = "Markdown" if is_markdown else "純文字"

    if lang in ("zh", "zh-cn", "zh-hans", "zh-sg"):
        title_line = title_raw or "（无标题）"
        url_line = url_raw or "（无 URL）"
        return (
            f"页面 URL：{url_line}\n"
            f"页面标题：{title_line}\n"
            f"内容格式：{fmt_zh_s}\n\n"
            f"--- 正文开始 ---\n{page_content}\n--- 正文结束 ---"
        )
    if lang in ("zh-hant", "zh-tw", "zh-hk", "zh-mo"):
        title_line = title_raw or "（無標題）"
        url_line = url_raw or "（無 URL）"
        return (
            f"頁面 URL：{url_line}\n"
            f"頁面標題：{title_line}\n"
            f"內容格式：{fmt_zh_t}\n\n"
            f"--- 正文開始 ---\n{page_content}\n--- 正文結束 ---"
        )

    title_line = title_raw or "(no title)"
    url_line = url_raw or "(no url)"
    return (
        f"Page URL: {url_line}\n"
        f"Page title: {title_line}\n"
        f"Content format: {fmt_latin}\n\n"
        f"--- Content start ---\n{page_content}\n--- Content end ---"
    )
