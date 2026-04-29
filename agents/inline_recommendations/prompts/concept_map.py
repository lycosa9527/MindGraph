"""Concept map inline Tab recommendations: concept labels vs relationship edge labels."""

from typing import Any, Dict, Optional

from ._common import (
    THINKING_APPROACH,
    append_batch_note,
    is_chinese_inline_prompt_language,
    thinking_locale_key,
)


def build_concept_map_relationship_labels_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[list[str]] = None,
) -> str:
    """
    Short relationship phrases for the directed link source → target (no concept names in lines).
    """
    topic = (context.get("topic") or "").strip()
    a_label = (context.get("relationship_concept_a") or "").strip()
    b_label = (context.get("relationship_concept_b") or "").strip()
    current = (context.get("relationship_current_label") or "").strip()
    context_desc = context.get("context_desc") or "General K12 teaching"
    on_map = context.get("relationship_labels_on_map") or []
    if isinstance(on_map, list):
        rel_on_map = [str(x).strip() for x in on_map if str(x).strip()]
    else:
        rel_on_map = []
    thinking = THINKING_APPROACH["bubble_map"][thinking_locale_key(language)]
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        topic_line = f"概念图主题：{topic}" if topic else "主题未设置"
        prompt = f"""{topic_line}

教学背景：{context_desc}

你在为概念图的有向连线编写关系标签。连线方向为：概念A → 概念B。
概念A：{a_label or "（未命名）"}
概念B：{b_label or "（未命名）"}

思维方式：优先清楚表达方向性关系（不同于简单“相关”）——因果关系、组成部分、依存、类比、例证等皆可；{thinking}
"""
        if current:
            prompt += f"\n当前这条连线上的标签为：「{current}」。可在此基础上给出更贴切或不同侧重点的备选。"
        if rel_on_map:
            prompt += (
                "\n图中其它连线已使用的关系措辞（避免重复措辞）："
                + "、".join(rel_on_map[:40])
                + "。"
            )
        prompt += f"""

规则：
- 每一行输出一个短语，描述从概念A指向概念B的关系（不要出现概念A、概念B的具体名称）。
- 避免空泛用语：诸如「有关」「相关联」「连接到」——除非在学科语境下有明确所指。
- 不要编号，不要前缀，不要括号说明，每条一行。
- 至少输出{count}行。"""

    else:
        topic_line = f"Concept-map topic: {topic}" if topic else "Topic not set"
        prompt = f"""{topic_line}

Educational Context: {context_desc}

Generate relationship labels for ONE directed link: Concept A → Concept B.

Concept A: {a_label or "(unnamed)"}
Concept B: {b_label or "(unnamed)"}

Thinking: prefer directional relations (cause, part-of, prerequisite, analogy, illustrates, etc.);
avoid vague connectives unless they are precise in-context — {thinking}
"""
        if current:
            prompt += (
                f'\nCurrent label on this link: "{current}". Improve it or propose distinct alternatives.'
            )
        if rel_on_map:
            joined = ", ".join(rel_on_map[:40])
            prompt += f"\n\nLabels already used on other edges in this map (avoid repeating): {joined}."
        prompt += f"""

RULES:
- Output one short phrase per line that labels the arrow from Concept A toward Concept B.
- Do NOT restate Concept A or Concept B verbatim in each line — only the relational phrase.
- Avoid generic phrases like "related to" / "associated with" unless they are narrowly meaningful.
- No numbering or prefixes — at least {count} lines."""

    return append_batch_note(prompt, language, batch_num, existing)
