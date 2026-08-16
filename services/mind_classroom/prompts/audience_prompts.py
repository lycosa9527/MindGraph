"""专业程度 briefs for classroom lecture scripts.

Matches canvas 专业内容 levels: general / primary / junior / senior /
university / adult / expert. Native zh and en — not slot-assembled translations.
"""

from __future__ import annotations

from typing import Any

AUDIENCE_LEVEL_IDS = frozenset({"general", "primary", "junior", "senior", "university", "adult", "expert"})

_LABELS = {
    "general": {"zh": "通用", "en": "General"},
    "primary": {"zh": "小学", "en": "Primary"},
    "junior": {"zh": "初中", "en": "Middle school"},
    "senior": {"zh": "高中", "en": "High school"},
    "university": {"zh": "大学", "en": "University"},
    "adult": {"zh": "成人", "en": "Adult"},
    "expert": {"zh": "专家", "en": "Expert"},
}

_BRIEFS_ZH = {
    "general": ("专业程度：通用。不额外压低或拔高；按导图本身的用语与概念密度讲解。不要强行小学化，也不要专家腔。"),
    "primary": (
        "专业程度：小学。"
        "用语只用日常具体词，禁止术语、抽象概念名和英文缩写。"
        "短句，能朗读给小学生听。"
        "只假设生活常识，不假设任何学科基础。"
        "深度：指认、举例、说「是什么」；不要原理、分类框架或因果链。"
    ),
    "junior": (
        "专业程度：初中。"
        "清晰白话；可少量学科词，首次出现用生活说法带过。"
        "短到中等句子，一层意思一句。"
        "假设义务教育常识，不假设高中专项。"
        "深度：是什么、简单分类与直接用途；少谈争议与理论模型。"
    ),
    "senior": (
        "专业程度：高中。"
        "可用规范学科用语，少科普铺垫。"
        "句子完整，把概念关系写清楚。"
        "假设高中该科常见概念。"
        "深度：抽象完整；写清因果、对比与适用条件；不要大学论文腔。"
    ),
    "university": (
        "专业程度：大学。"
        "用学科术语与理论视角，不必解释入门词。"
        "按论证组织，可稍长。"
        "假设本科通识与该科基础。"
        "深度：机制、证据与限度；可点出模型或流派，避免中小学教案口吻。"
    ),
    "adult": (
        "专业程度：成人。"
        "清晰专业，少课堂口吻。"
        "句子直接，面向做事。"
        "假设职场常识，不假设学历阶梯。"
        "深度：场景、决策与利弊；少定理推导与考试知识点罗列。"
    ),
    "expert": (
        "专业程度：专家。"
        "领域术语，禁止科普开场。"
        "句子密、准、短，去掉过渡句。"
        "假设同行背景。"
        "深度：机制、边界、争议与反例；不要定义课或教学脚手架。"
        "叙事或举例形式听 tone_brief。"
    ),
}

_BRIEFS_EN = {
    "general": (
        "Expertise: general. "
        "Do not force a school stage. Follow the map’s own wording and density. "
        "Neither primary-school nor expert-peer voice."
    ),
    "primary": (
        "Expertise: primary school. "
        "Everyday concrete words only — no jargon, abstract labels, or acronyms. "
        "Short sentences, easy to read aloud to a child. "
        "Assume daily life only. "
        "Depth: name things and give examples. No mechanisms or taxonomies."
    ),
    "junior": (
        "Expertise: middle school. "
        "Clear everyday language; gloss a subject word on first use. "
        "One idea per sentence. "
        "Assume compulsory-education knowledge, not high-school specialization. "
        "Depth: what it is, simple grouping, direct use."
    ),
    "senior": (
        "Expertise: high school. "
        "Standard subject terms are fine; skip popular-science padding. "
        "Make relationships explicit. "
        "Assume common high-school concepts. "
        "Depth: cause and effect, contrast, when it applies — not a university paper."
    ),
    "university": (
        "Expertise: university. "
        "Disciplinary terms; do not define introductory words. "
        "Organize as an argument. "
        "Assume undergraduate literacy. "
        "Depth: mechanism, evidence, limits; name models. No K–12 lesson tone."
    ),
    "adult": (
        "Expertise: adult professional. "
        "Clear and professional; little classroom tone. "
        "Direct and action-oriented. "
        "Assume workplace common sense, not a school ladder. "
        "Depth: scenarios, decisions, trade-offs."
    ),
    "expert": (
        "Expertise: expert peer. "
        "Domain terminology; no popular-science opening. "
        "Dense, precise, short. "
        "Assume a colleague in the field. "
        "Depth: mechanisms, bounds, disagreements, counterexamples. "
        "No definition-lesson scaffolding. Story or example form follows tone_brief."
    ),
}


def normalize_audience_level(raw: Any) -> str:
    """Return a valid 专业程度 id, defaulting to general."""
    value = str(raw or "").strip()
    return value if value in AUDIENCE_LEVEL_IDS else "general"


def audience_label(level: str, language: str) -> str:
    """UI label for a 专业程度 id."""
    lang = "zh" if str(language or "zh").startswith("zh") else "en"
    return _LABELS[normalize_audience_level(level)][lang]


def audience_brief(level: str, language: str) -> str:
    """Instruction block so the LLM knows this diagram’s expertise level."""
    key = normalize_audience_level(level)
    if str(language or "zh").startswith("zh"):
        return _BRIEFS_ZH[key]
    return _BRIEFS_EN[key]
