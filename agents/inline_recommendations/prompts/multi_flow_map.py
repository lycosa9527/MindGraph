"""Multi flow map inline recommendation prompts."""

from typing import Any, Dict, List, Optional

from ._common import append_batch_note, THINKING_APPROACH


def build_multi_flow_causes_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for multi flow map cause recommendations."""
    event = (context.get("event") or "").strip()
    cause_texts = context.get("cause_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["multi_flow_map"][language]
    existing = existing or []

    if language == "zh":
        event_ctx = f"事件：{event}" if event else "事件未设置"
        prompt = f"""用户正在创建复流程图。{event_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个原因推荐。要求：
1. 原因导致该事件发生
2. 每个原因简洁（1-6个词）
3. 只输出原因文本，每行一个，不要编号"""
        if cause_texts:
            prompt += f"""

图中已有原因：{", ".join(cause_texts)}。请生成更聚焦、互补的原因推荐，与已有原因形成补充，避免重复。"""
        prompt += f"""

生成{count}个原因："""
    else:
        event_ctx = f"Event: {event}" if event else "Event not set"
        prompt = f"""The user is creating a multi flow map. {event_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} cause recommendations. Requirements:
1. Causes lead to this event
2. Each cause concise (1-6 words)
3. Output only cause text, one per line, no numbering"""
        if cause_texts:
            causes = ", ".join(cause_texts)
            prompt += (
                f"\n\nThe diagram already has causes: {causes}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} causes:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_multi_flow_effects_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for multi flow map effect recommendations."""
    event = (context.get("event") or "").strip()
    effect_texts = context.get("effect_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["multi_flow_map"][language]
    existing = existing or []

    if language == "zh":
        event_ctx = f"事件：{event}" if event else "事件未设置"
        prompt = f"""用户正在创建复流程图。{event_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个结果推荐。要求：
1. 结果是该事件导致的
2. 每个结果简洁（1-6个词）
3. 只输出结果文本，每行一个，不要编号"""
        if effect_texts:
            prompt += f"""

图中已有结果：{", ".join(effect_texts)}。请生成更聚焦、互补的结果推荐，与已有结果形成补充，避免重复。"""
        prompt += f"""

生成{count}个结果："""
    else:
        event_ctx = f"Event: {event}" if event else "Event not set"
        prompt = f"""The user is creating a multi flow map. {event_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} effect recommendations. Requirements:
1. Effects result from this event
2. Each effect concise (1-6 words)
3. Output only effect text, one per line, no numbering"""
        if effect_texts:
            effects = ", ".join(effect_texts)
            prompt += (
                f"\n\nThe diagram already has effects: {effects}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} effects:"""

    return append_batch_note(prompt, language, batch_num, existing)
