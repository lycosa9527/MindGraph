"""
Mind-map 专业程度 prompt builder.

Native zh/en templates must stay in lockstep with
frontend/src/composables/mindMap/audience/aiContentLevelInstructions.*.ts
"""

from __future__ import annotations

import re
from typing import Match, Optional, Pattern

from services.utils.ai_content_level import (
    AI_CONTENT_LEVEL_SET,
    DEFAULT_AI_CONTENT_LEVEL,
)

# Keep in sync with frontend aiContentLevelInstructions.zh.ts
MIND_MAP_AUDIENCE_ZH: dict[str, Optional[str]] = {
    "general": None,
    "primary": (
        "请按「小学」专业程度生成内容。\n"
        "用语：只用日常具体词，禁止术语、抽象概念名和英文缩写。\n"
        "句子：短句；每条宜在十余字内，能朗读给小学生听。\n"
        "前提：只假设生活常识，不假设任何学科基础。\n"
        "深度：能指认、举例、说“是什么”；不要原理、分类框架或因果链。"
    ),
    "junior": (
        "请按「初中」专业程度生成内容。\n"
        "用语：清晰白话；可少量学科词，首次出现用生活说法带过。\n"
        "句子：短到中等，一层意思一句。\n"
        "前提：假设义务教育常识，不假设高中专项。\n"
        "深度：覆盖是什么、简单分类与直接用途；少谈争议与理论模型。"
    ),
    "senior": (
        "请按「高中」专业程度生成内容。\n"
        "用语：可用规范学科用语，少科普铺垫。\n"
        "句子：完整，把概念关系写清楚。\n"
        "前提：假设高中该科常见概念。\n"
        "深度：抽象完整；写清因果、对比与适用条件；不要大学论文腔。"
    ),
    "university": (
        "请按「大学」专业程度生成内容。\n"
        "用语：用学科术语与理论视角，不必解释入门词。\n"
        "句子：按论证组织，可稍长。\n"
        "前提：假设本科通识与该科基础。\n"
        "深度：按学科框架写机制、证据与限度；可点出模型或流派，避免中小学教案口吻。"
    ),
    "adult": (
        "请按「成人」专业程度生成内容。\n"
        "用语：清晰专业，少课堂口吻。\n"
        "句子：直接，面向做事。\n"
        "前提：假设职场常识，不假设学历阶梯。\n"
        "深度：侧重场景、决策与利弊；少定理推导与考试知识点罗列。"
    ),
    "expert": (
        "请按「专家」专业程度生成内容。\n"
        "用语：领域术语，禁止科普开场。\n"
        "句子：密、准、短，去掉过渡句。\n"
        "前提：假设同行背景。\n"
        "深度：写机制、边界、争议与反例；不要定义课、类比故事或教学脚手架。"
    ),
}

# Keep in sync with frontend aiContentLevelInstructions.en.ts
MIND_MAP_AUDIENCE_EN: dict[str, Optional[str]] = {
    "general": None,
    "primary": (
        "Write this content for a primary-school classroom.\n"
        "Voice: everyday concrete words only — no jargon, abstract labels, or acronyms.\n"
        "Length: short sentences; each line should be easy to read aloud to a child.\n"
        "Assume: daily life only. Do not assume any subject background.\n"
        "Depth: name things and give examples. No mechanisms, taxonomies, or cause-and-effect chains."
    ),
    "junior": (
        "Write this content for a middle-school classroom.\n"
        "Voice: clear everyday language. A light subject word is fine if you gloss it on first use.\n"
        "Length: short to medium sentences; one idea per sentence.\n"
        "Assume: general compulsory-education knowledge. Do not assume high-school specialization.\n"
        "Depth: what it is, simple grouping, and direct use. Little debate or theoretical models."
    ),
    "senior": (
        "Write this content for a high-school classroom.\n"
        "Voice: standard subject terminology is fine. Skip popular-science padding.\n"
        "Length: complete sentences that make relationships explicit.\n"
        "Assume: common high-school concepts in the subject.\n"
        "Depth: be abstract and complete — cause and effect, contrast, and when it applies. "
        "Not a university paper."
    ),
    "university": (
        "Write this content for a university course.\n"
        "Voice: disciplinary and academic terms. Do not define introductory words.\n"
        "Length: organize as an argument; slightly longer sentences are fine.\n"
        "Assume: undergraduate literacy and the basics of the field.\n"
        "Depth: use a disciplinary frame — mechanism, evidence, and limits. Name models or schools. "
        "No K–12 lesson tone."
    ),
    "adult": (
        "Write this content for adult professionals at work.\n"
        "Voice: clear and professional. Little classroom tone.\n"
        "Length: direct and action-oriented.\n"
        "Assume: workplace common sense. Do not assume a school-stage ladder.\n"
        "Depth: scenarios, decisions, and trade-offs. Little theorem-proving or exam-point lists."
    ),
    "expert": (
        "Write this content for an expert peer.\n"
        "Voice: domain terminology. No popular-science opening.\n"
        "Length: dense, precise, and short. Drop transition filler.\n"
        "Assume: a colleague in the field.\n"
        "Depth: mechanisms, bounds, disagreements, and counterexamples. "
        "No definition lessons, analogy stories, or teaching scaffolds."
    ),
}

_PROMPT_LEVEL_ALIASES: dict[str, str] = {
    "通用": "general",
    "一般": "general",
    "大众": "general",
    "默认": "general",
    "general": "general",
    "default": "general",
    "小学": "primary",
    "小学生": "primary",
    "primary": "primary",
    "primary school": "primary",
    "primary-school": "primary",
    "初中": "junior",
    "初中生": "junior",
    "中学": "junior",
    "junior": "junior",
    "middle": "junior",
    "middle school": "junior",
    "middle-school": "junior",
    "高中": "senior",
    "高中生": "senior",
    "senior": "senior",
    "high": "senior",
    "high school": "senior",
    "high-school": "senior",
    "大学": "university",
    "大学生": "university",
    "university": "university",
    "college": "university",
    "成人": "adult",
    "adult": "adult",
    "专家": "expert",
    "expert": "expert",
    "专业水平": "expert",
}

_ZH_LEVEL = r"小学生|初中生|高中生|大学生|小学|初中|中学|高中|大学|成人|专家|通用|一般|大众|默认"
_EN_SCHOOL = r"primary[\s-]+school|middle[\s-]+school|high[\s-]+school"
_EN_LEVEL = rf"{_EN_SCHOOL}|university|college|adult|expert|general|default|junior|senior|primary"
_ZH_DEGREE = r"专业程度|水平|程度|难度|级别"
_EDGE_CHARS = " ,，、;；的：:=-"
_PUNCT_JOIN = re.compile(r"[\s,，、;；]+")
_EDGE_JUNK = re.compile(r"^[ ,，、;；的：:=\-]+|[ ,，、;；的：:=\-]+$")


def _zh_pattern(source: str) -> Pattern[str]:
    return re.compile(source)


def _en_pattern(source: str) -> Pattern[str]:
    return re.compile(source, re.IGNORECASE)


_REQUEST_PATTERNS: tuple[Pattern[str], ...] = (
    _zh_pattern(
        rf"(?:专业内容|专业程度|内容水平|受众(?:难度)?|生成难度)"
        rf"\s*(?:改成|设为|换成|调成|设置成|设到|为|是)?[：:=]?\s*(?P<level>{_ZH_LEVEL})"
    ),
    _zh_pattern(rf"(?:按|按照)\s*(?P<level>{_ZH_LEVEL})\s*(?:的)?(?:{_ZH_DEGREE})"),
    _zh_pattern(r"(?:面向|适合|给)\s*(?P<level>小学生|初中生|高中生|大学生|成人|专家)(?:看|听|用)?"),
    _zh_pattern(rf"^(?P<level>{_ZH_LEVEL})(?:的)?(?:{_ZH_DEGREE})"),
    _zh_pattern(rf"(?P<level>{_ZH_LEVEL})(?:的)?(?:{_ZH_DEGREE})的"),
    _zh_pattern(rf"(?:[,，;；、]|\s)+(?P<level>{_ZH_LEVEL})(?:的)?(?:{_ZH_DEGREE})[。.!！？?\s]*$"),
    _zh_pattern(r"(?:^|[,，;；、\s])(?P<level>专业水平)(?=[。.!！？?\s]|$)"),
    _en_pattern(
        rf"(?:professional(?:\s+content)?|content|audience|expertise)\s+level"
        rf"\s*(?:to|as|:|=)\s*(?P<level>{_EN_LEVEL})"
    ),
    _en_pattern(
        rf"(?:for)\s+(?:a\s+|an\s+|the\s+)?(?P<level>{_EN_SCHOOL})"
        rf"(?:\s+(?:students?|classroom|kids?|children))?[.!?\s]*$"
    ),
    _en_pattern(
        rf"(?:for)\s+(?:a\s+|an\s+|the\s+)?(?P<level>{_EN_SCHOOL})"
        rf"\s+(?:students?|classroom|kids?|children|level)"
    ),
    _en_pattern(rf"[,;]\s*(?P<level>{_EN_SCHOOL})[.!?\s]*$"),
    _en_pattern(
        r"(?:for|at)\s+(?:a\s+|an\s+|the\s+)?"
        r"(?P<level>university|college|adult|expert|general|default|junior|senior|primary)"
        r"\s+(?:students?|classroom|level|course)"
    ),
    _en_pattern(rf"^(?P<level>{_EN_LEVEL})[\s-]+level"),
    _en_pattern(rf"(?:[,;]|\s)+(?P<level>{_EN_LEVEL})[\s-]+level[.!?\s]*$"),
)


def _is_chinese_prompt_language(language: str) -> bool:
    return (language or "").lower().startswith("zh")


def build_mind_map_audience_instructions(level: str, language: str) -> Optional[str]:
    """Return the canvas 专业程度 block, or None for general / unknown."""
    key = (level or "").strip().lower()
    if key not in AI_CONTENT_LEVEL_SET:
        return None
    templates = MIND_MAP_AUDIENCE_ZH if _is_chinese_prompt_language(language) else MIND_MAP_AUDIENCE_EN
    return templates[key]


def normalize_prompt_content_level(raw: str) -> Optional[str]:
    """Map a captured prompt phrase onto a catalog id."""
    folded = re.sub(r"[\s-]+", " ", (raw or "").strip()).lower()
    if not folded:
        return None
    mapped = _PROMPT_LEVEL_ALIASES.get(folded) or _PROMPT_LEVEL_ALIASES.get(raw.strip())
    if mapped:
        return mapped
    stripped = re.sub(r"(?:生|学生|students?|classroom|school)$", "", folded).strip()
    if stripped and stripped != folded:
        return normalize_prompt_content_level(stripped)
    return None


def _better_span(current: Optional[tuple[str, int, int]], match: Match[str], level: str) -> tuple[str, int, int]:
    candidate = (level, match.start(), match.end())
    if current is None:
        return candidate
    if match.start() > current[1]:
        return candidate
    if match.start() == current[1] and match.end() > current[2]:
        return candidate
    return current


def find_prompt_audience_request(prompt: str) -> Optional[tuple[str, int, int]]:
    """Return (level_id, start, end) for the rightmost explicit 专业程度 request."""
    text = prompt or ""
    best: Optional[tuple[str, int, int]] = None
    for pattern in _REQUEST_PATTERNS:
        for match in pattern.finditer(text):
            level = normalize_prompt_content_level(match.group("level"))
            if level is None:
                continue
            best = _better_span(best, match, level)
    return best


def detect_ai_content_level_from_prompt(prompt: str) -> str:
    """Return a catalog id; default general when the prompt does not request a level."""
    found = find_prompt_audience_request(prompt)
    if found is None:
        return DEFAULT_AI_CONTENT_LEVEL
    return found[0]


def _strip_span(text: str, start: int, end: int) -> str:
    left = text[:start].rstrip(_EDGE_CHARS)
    right = text[end:].lstrip(_EDGE_CHARS)
    if left and right:
        joined = f"{left} {right}"
    else:
        joined = f"{left}{right}"
    return _EDGE_JUNK.sub("", _PUNCT_JOIN.sub(" ", joined)).strip()


def resolve_prompt_audience(prompt: str, language: str) -> tuple[str, str, Optional[str]]:
    """Return (topic_prompt, level_id, canvas_instruction_block)."""
    text = (prompt or "").strip()
    found = find_prompt_audience_request(text)
    if found is None:
        return text, DEFAULT_AI_CONTENT_LEVEL, None
    level, start, end = found
    cleaned = _strip_span(text, start, end)
    topic = cleaned or text
    return topic, level, build_mind_map_audience_instructions(level, language)
