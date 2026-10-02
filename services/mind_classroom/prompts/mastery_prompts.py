"""Familiarity-level briefs for classroom lecture scripts.

初识 / 复习巩固 / 备课讲授 must produce different captions and teacher_script,
not a single generic lecture with the mastery id pasted in.
"""

from __future__ import annotations

from typing import Any

from services.mind_classroom.prompts.audience_prompts import (
    audience_brief,
    audience_label,
    normalize_audience_level,
)
from services.mind_classroom.prompts.diagram_prompts import diagram_pref_fields
from services.mind_classroom.prompts.tone_prompts import normalize_tone, tone_brief, tone_label
from services.mind_classroom.prompts.tour_scope_prompts import (
    normalize_tour_scope,
    tour_scope_brief,
    tour_scope_label,
)

MASTERY_IDS = frozenset({"first_look", "review", "teach"})

_LABELS = {
    "first_look": {"zh": "初识", "en": "First look"},
    "review": {"zh": "复习巩固", "en": "Review"},
    "teach": {"zh": "备课讲授", "en": "Prep to teach"},
}

_BRIEFS_ZH = {
    "first_look": (
        "熟悉程度：初识（第一次看这张图）。"
        "假设听者还不认识这张图：先按 diagram_brief 点名中心和主节点，再按 tour_scope_brief 带路。"
        "每步只引入一个新概念；术语先用一句话解释。"
        "禁止「你已经知道」「如前所述」。"
        "不要写成给别人上课的教案；句数、问句和提纲形式听 tone_brief。"
        "收束：收成轮廓，可请听者圈出仍陌生的两三点（若 tone_brief 允许邀请）。"
    ),
    "review": (
        "熟悉程度：复习巩固（已经看过这张图）。"
        "假设听者认识主干：少做入门介绍，多用回忆、对照、易混点。"
        "可用「合上图能否说出…」这类轻回忆；不要从零定义每个词。"
        "不要写成给别人上课的教案；句数与口吻听 tone_brief。"
        "收束：合上书复述本图的主节点；卡壳再回到那一个节点。"
    ),
    "teach": (
        "熟悉程度：备课讲授（听者要拿这份讲稿去教别人）。"
        "讲稿是教师可照读的课堂旁白，并点出怎么教：开场钩子、可提问处、板书强调点。"
        "面向 audience 控制难度；可用「你可以问学生…」「这一处适合板书…」。节点叫法听 diagram_brief。"
        "不要写成自学笔记；不要假设学生已经会。"
        "句数与口吻听 tone_brief。"
        "收束：给出可照用的开场—展开—收束顺序，并建议把一个主节点拆成课堂提问。"
    ),
}

_BRIEFS_EN = {
    "first_look": (
        "Familiarity: first look (first time with this map). "
        "Assume the listener does not know this diagram: name the center and main nodes "
        "as diagram_brief calls them, then walk per tour_scope_brief. One new idea per step; gloss terms "
        "in one clause. Do not say “as you already know”. "
        "Do not write a lesson plan for teaching others. "
        "Sentence count, questions, and outline form follow tone_brief. "
        "Close with a contour; you may invite them to mark two or three still-unfamiliar "
        "points when tone_brief allows it."
    ),
    "review": (
        "Familiarity: review (they have seen this map). "
        "Assume they know the trunk: skip beginner intros; use recall, contrast, and mix-up points. "
        "Light prompts like “can you name this with the map closed?” are good. Do not redefine every term. "
        "Do not write a lesson plan for teaching others. "
        "Length and voice follow tone_brief. "
        "Close by asking them to retell this diagram’s main nodes; return to the node that sticks."
    ),
    "teach": (
        "Familiarity: prep to teach (the listener will teach this map to others). "
        "Write classroom-ready narration they can read aloud, plus how to teach: hook, questions, board emphasis. "
        "Match difficulty to audience. Phrases like “you can ask students…” are welcome. "
        "Do not write a self-study note; do not assume students already know it. "
        "Length and voice follow tone_brief. "
        "Close with a reusable open–develop–close order and suggest turning one main node into a class question. "
        "Node names follow diagram_brief."
    ),
}


def normalize_mastery(raw: Any) -> str:
    """Return a valid mastery id, defaulting to first_look."""
    value = str(raw or "").strip()
    return value if value in MASTERY_IDS else "first_look"


def mastery_label(mastery: str, language: str) -> str:
    """UI label for a mastery id."""
    lang = "zh" if str(language or "zh").startswith("zh") else "en"
    return _LABELS[normalize_mastery(mastery)][lang]


def mastery_brief(mastery: str, language: str) -> str:
    """Instruction block the LLM must follow for this familiarity level."""
    key = normalize_mastery(mastery)
    if str(language or "zh").startswith("zh"):
        return _BRIEFS_ZH[key]
    return _BRIEFS_EN[key]


def classroom_pref_fields(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Fields to embed in canvas-tour and slide-planner user payloads."""
    raw = settings if isinstance(settings, dict) else {}
    language = str(raw.get("language") or "zh")
    mastery = normalize_mastery(raw.get("mastery"))
    audience = normalize_audience_level(raw.get("audience_level"))
    tone = normalize_tone(raw.get("tone"))
    scope = normalize_tour_scope(raw.get("tour_scope"))
    title = str(raw.get("audience_title") or "").strip() or audience_label(audience, language)
    return {
        **diagram_pref_fields(raw),
        "mastery": mastery,
        "mastery_label": mastery_label(mastery, language),
        "mastery_brief": mastery_brief(mastery, language),
        "tone": tone,
        "tone_label": tone_label(tone, language),
        "tone_brief": tone_brief(tone, language),
        "audience_level": audience,
        "audience_title": title,
        "audience_brief": audience_brief(audience, language),
        "tour_scope": scope,
        "tour_scope_label": tour_scope_label(scope, language),
        "tour_scope_brief": tour_scope_brief(scope, language, raw.get("diagram_type")),
    }


def build_axis_contract_block(
    settings: dict[str, Any] | None,
    *,
    include_tour_scope: bool = True,
) -> str:
    """Assemble the four launch-axis briefs for a system message."""
    prefs = classroom_pref_fields(settings)
    language = str((settings or {}).get("language") or "zh")
    zh_lang = str(language).startswith("zh")
    if zh_lang:
        lines = ["# 本场选择（必须全部遵守）", ""]
        sections = [
            (f"## 图示 · {prefs['diagram_label']}", prefs["diagram_brief"]),
            (f"## 专业程度 · {prefs['audience_title']}", prefs["audience_brief"]),
            (f"## 熟悉程度 · {prefs['mastery_label']}", prefs["mastery_brief"]),
            (f"## 讲解语气 · {prefs['tone_label']}", prefs["tone_brief"]),
        ]
        if include_tour_scope:
            sections.insert(
                2,
                (f"## 巡讲粒度 · {prefs['tour_scope_label']}", prefs["tour_scope_brief"]),
            )
        for heading, body in sections:
            lines.extend([heading, body, ""])
        if include_tour_scope:
            lines.append(
                "分工：diagram_brief 管图示思维焦点和节点叫法；audience_brief 管用词与深度；"
                "mastery_brief 管听者立场；tour_scope_brief 管哪些节点成步；"
                "tone_brief 管怎么说（句数、问句、提纲或叙事）。"
            )
            lines.append(
                "冲突时：节点叫法听 diagram_brief 和 nodes[].role，走图听 tour_scope，"
                "口吻听 tone，用词听 audience，立场听 mastery。"
                "不要把本图示的节点改叫成另一种图示的分支或下属。"
            )
        else:
            lines.append(
                "分工：diagram_brief 管图示思维焦点和节点叫法；audience_brief 管用词与深度；"
                "mastery_brief 管听者立场；tone_brief 管怎么说（句数、问句、提纲或叙事）。"
            )
            lines.append("冲突时：节点叫法听 diagram_brief，口吻听 tone，用词听 audience，立场听 mastery。")
        return "\n".join(lines).rstrip()
    lines = ["# This session (follow every block)", ""]
    sections = [
        (f"## Diagram · {prefs['diagram_label']}", prefs["diagram_brief"]),
        (f"## Expertise · {prefs['audience_title']}", prefs["audience_brief"]),
        (f"## Familiarity · {prefs['mastery_label']}", prefs["mastery_brief"]),
        (f"## Tone · {prefs['tone_label']}", prefs["tone_brief"]),
    ]
    if include_tour_scope:
        sections.insert(
            2,
            (f"## Tour scope · {prefs['tour_scope_label']}", prefs["tour_scope_brief"]),
        )
    for heading, body in sections:
        lines.extend([heading, body, ""])
    if include_tour_scope:
        lines.append(
            "Split: diagram_brief = thinking focus and node names; "
            "audience_brief = wording and depth; mastery_brief = listener stance; "
            "tour_scope_brief = which nodes become steps; tone_brief = how it is spoken."
        )
        lines.append(
            "On conflict: node names follow diagram_brief and nodes[].role, "
            "the walk follows tour_scope, voice follows tone, wording follows audience, "
            "stance follows mastery. Do not rename this diagram’s nodes as another diagram’s branches."
        )
    else:
        lines.append(
            "Split: diagram_brief = thinking focus and node names; "
            "audience_brief = wording and depth; mastery_brief = listener stance; "
            "tone_brief = how it is spoken."
        )
        lines.append(
            "On conflict: node names follow diagram_brief, voice follows tone, "
            "wording follows audience, stance follows mastery."
        )
    return "\n".join(lines).rstrip()


def skip_forced_choice_frame(mastery: str) -> bool:
    """First-look decks should not force an A/B conflict frame."""
    return normalize_mastery(mastery) == "first_look"
