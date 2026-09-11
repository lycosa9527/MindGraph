"""Voice phrases for AI content level and mind-map branch numbering.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

CONTENT_LEVEL_IDS = (
    "general",
    "primary",
    "junior",
    "senior",
    "university",
    "adult",
    "expert",
)

CONTENT_LEVEL_LABELS: Dict[str, Dict[str, str]] = {
    "general": {"zh": "通用", "en": "General"},
    "primary": {"zh": "小学", "en": "Primary"},
    "junior": {"zh": "初中", "en": "Middle school"},
    "senior": {"zh": "高中", "en": "High school"},
    "university": {"zh": "大学", "en": "University"},
    "adult": {"zh": "成人", "en": "Adult"},
    "expert": {"zh": "专家", "en": "Expert"},
}

_LEVEL_ALIASES: Dict[str, str] = {
    "通用": "general",
    "一般": "general",
    "大众": "general",
    "默认": "general",
    "general": "general",
    "default": "general",
    "小学": "primary",
    "小学生": "primary",
    "小学水平": "primary",
    "primary": "primary",
    "primary school": "primary",
    "初中": "junior",
    "中学": "junior",
    "初中水平": "junior",
    "junior": "junior",
    "middle school": "junior",
    "高中": "senior",
    "高中水平": "senior",
    "senior": "senior",
    "high school": "senior",
    "大学": "university",
    "大学水平": "university",
    "university": "university",
    "college": "university",
    "成人": "adult",
    "成人水平": "adult",
    "adult": "adult",
    "专家": "expert",
    "专家水平": "expert",
    "专业": "expert",
    "专业水平": "expert",
    "expert": "expert",
    "professional": "expert",
}

_STRIP_TRAILING = re.compile(r"[。.!！？?\s]+$")
_CONTENT_LEVEL_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:把)?"
    r"(?:专业内容|内容水平|受众(?:难度)?|AI内容|生成难度)"
    r"(?:改成|设为|换成|调成|设置成|设到)"
    r"(?P<level>.+)$"
)
_CONTENT_LEVEL_ZH_SHORT = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:改成|设为|换成|调成)"
    r"(?P<level>.+?)"
    r"(?:水平|程度|难度)$"
)
_CONTENT_LEVEL_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:set|change|switch)\s+"
    r"(?:the\s+)?"
    r"(?:content(?:\s+level)?|audience|difficulty|professional\s+content)"
    r"\s+(?:to|as)\s+"
    r"(?P<level>.+)$",
    re.IGNORECASE,
)
TOOLBAR_NUMBERING_PREFIX_IDS = (
    "decimal",
    "decimalParen",
    "paren",
    "circled",
    "chinese",
    "chineseParen",
    "chineseChapter",
    "chineseArticle",
    "upperAlpha",
    "lowerAlpha",
    "lowerAlphaParen",
)

NUMBERING_STYLE_LABELS: Dict[str, Dict[str, str]] = {
    "decimal": {"zh": "数字", "en": "decimal"},
    "decimalParen": {"zh": "数字括号", "en": "decimal paren"},
    "paren": {"zh": "括号", "en": "parentheses"},
    "circled": {"zh": "圆圈", "en": "circled"},
    "chinese": {"zh": "中文", "en": "Chinese"},
    "chineseParen": {"zh": "中文括号", "en": "Chinese paren"},
    "chineseChapter": {"zh": "章节", "en": "chapter"},
    "chineseArticle": {"zh": "条文", "en": "article"},
    "upperAlpha": {"zh": "字母", "en": "letter"},
    "lowerAlpha": {"zh": "小写字母", "en": "lowercase"},
    "lowerAlphaParen": {"zh": "小写字母括号", "en": "lowercase paren"},
}

_STYLE_ALIASES: Dict[str, str] = {
    "数字": "decimal",
    "阿拉伯数字": "decimal",
    "阿拉伯": "decimal",
    "decimal": "decimal",
    "number": "decimal",
    "numbers": "decimal",
    "numeric": "decimal",
    "中文": "chinese",
    "汉字": "chinese",
    "chinese": "chinese",
    "圆圈": "circled",
    "圈": "circled",
    "circled": "circled",
    "字母": "upperAlpha",
    "英文": "upperAlpha",
    "letter": "upperAlpha",
    "letters": "upperAlpha",
    "abc": "upperAlpha",
    "章节": "chineseChapter",
    "章": "chineseChapter",
    "chapter": "chineseChapter",
    "chapters": "chineseChapter",
    "括号": "paren",
    "paren": "paren",
    "parentheses": "paren",
    "条文": "chineseArticle",
    "条款": "chineseArticle",
    "article": "chineseArticle",
    "数字括号": "decimalParen",
    "括号数字": "decimalParen",
    "中文括号": "chineseParen",
    "小写字母": "lowerAlpha",
}

_NUMBERING_ON_ZH = re.compile(r"^(?:请)?(?:帮我)?(?:启用|打开|开启|显示)(?:节点)?编号$")
_NUMBERING_OFF_ZH = re.compile(r"^(?:请)?(?:帮我)?(?:隐藏|关闭|关掉|关闭显示)(?:节点)?编号$")
_NUMBERING_ON_EN = re.compile(
    r"^(?:please\s+)?(?:enable|show|turn\s+on)\s+(?:branch\s+)?(?:numbering|numbers)$",
    re.IGNORECASE,
)
_NUMBERING_OFF_EN = re.compile(
    r"^(?:please\s+)?(?:hide|disable|turn\s+off)\s+(?:branch\s+)?(?:numbering|numbers)$",
    re.IGNORECASE,
)
_NUMBERING_STYLE_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:启用|打开|开启|显示|改成|换成|设为|使用)"
    r"(?P<style>.+?)"
    r"编号$"
)
_NUMBERING_STYLE_ZH_SWAP = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:把)?编号"
    r"(?:改成|换成|设为|设置成)"
    r"(?P<style>.+)$"
)
_NUMBERING_STYLE_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:enable|show|use|switch\s+to|change\s+to)\s+"
    r"(?P<style>.+?)\s+"
    r"(?:branch\s+)?(?:numbering|numbers)$",
    re.IGNORECASE,
)
_NUMBERING_STYLE_BARE_ZH = re.compile(r"^(?P<style>.+?)编号$")
_NUMBERING_STYLE_BARE_EN = re.compile(
    r"^(?P<style>.+?)\s+(?:branch\s+)?(?:numbering|numbers)$",
    re.IGNORECASE,
)


def normalize_content_level(raw: Any) -> Optional[str]:
    """Map a spoken or tool level string to a catalog id."""
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if not key:
        return None
    if key in CONTENT_LEVEL_IDS:
        return key
    folded = raw.strip()
    mapped = _LEVEL_ALIASES.get(folded) or _LEVEL_ALIASES.get(folded.lower())
    if mapped:
        return mapped
    stripped = re.sub(r"(?:水平|程度|难度|模式)$", "", folded).strip()
    if stripped and stripped != folded:
        return normalize_content_level(stripped)
    return None


def normalize_numbering_style(raw: Any) -> Optional[str]:
    """Map a spoken style to a prefix glyph id."""
    if not isinstance(raw, str):
        return None
    folded = raw.strip()
    if not folded:
        return None
    if folded in TOOLBAR_NUMBERING_PREFIX_IDS:
        return folded
    mapped = _STYLE_ALIASES.get(folded) or _STYLE_ALIASES.get(folded.lower())
    if mapped:
        return mapped
    stripped = re.sub(
        r"(?:编号|風格|风格|样式|格式|numbering|numbers)$",
        "",
        folded,
        flags=re.IGNORECASE,
    ).strip()
    if stripped and stripped != folded:
        return normalize_numbering_style(stripped)
    return None


def numbering_style_label(style: str, lang: str) -> str:
    """Localized short title for a numbering prefix style."""
    row = NUMBERING_STYLE_LABELS.get(style) or {}
    if lang == "en":
        return row.get("en") or style
    return row.get("zh") or style


def content_level_label(level: str, lang: str) -> str:
    """Localized short title for an audience level."""
    row = CONTENT_LEVEL_LABELS.get(level) or {}
    if lang == "en":
        return row.get("en") or level
    return row.get("zh") or level


def heuristic_preference_command(command_text: str) -> Optional[Dict[str, Any]]:
    """Map 专业内容 / 编号 phrases. None when the text is something else."""
    text = _STRIP_TRAILING.sub("", (command_text or "").strip())
    if not text:
        return None
    if _NUMBERING_OFF_ZH.match(text) or _NUMBERING_OFF_EN.match(text):
        return {"action": "set_branch_numbering", "enabled": False, "confidence": 0.95}
    for pattern in (
        _NUMBERING_STYLE_ZH,
        _NUMBERING_STYLE_ZH_SWAP,
        _NUMBERING_STYLE_EN,
        _NUMBERING_STYLE_BARE_ZH,
        _NUMBERING_STYLE_BARE_EN,
    ):
        match = pattern.match(text)
        if match is None:
            continue
        style = normalize_numbering_style(match.group("style"))
        if style:
            return {
                "action": "set_branch_numbering",
                "enabled": True,
                "prefix": style,
                "confidence": 0.95,
            }
    if _NUMBERING_ON_ZH.match(text) or _NUMBERING_ON_EN.match(text):
        return {"action": "set_branch_numbering", "enabled": True, "confidence": 0.95}
    for pattern in (_CONTENT_LEVEL_ZH, _CONTENT_LEVEL_ZH_SHORT, _CONTENT_LEVEL_EN):
        match = pattern.match(text)
        if match is None:
            continue
        level = normalize_content_level(match.group("level"))
        if level:
            return {"action": "set_content_level", "level": level, "confidence": 0.95}
    return None
