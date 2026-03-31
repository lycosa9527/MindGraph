"""Double bubble map inline recommendation prompts."""

from typing import Any, Dict, List, Optional

from ._common import append_batch_note, THINKING_APPROACH


def build_double_bubble_similarities_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for double bubble map similarity recommendations."""
    left = (context.get("left_topic") or "").strip()
    right = (context.get("right_topic") or "").strip()
    sim_texts = context.get("similarity_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["double_bubble_map"][language]
    existing = existing or []

    if language == "zh":
        topics_ctx = f"左主题：{left}，右主题：{right}" if left and right else "主题未设置"
        prompt = f"""用户正在创建双气泡图。{topics_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个相似点推荐（两个主题共有的特征）。要求：
1. 相似点必须是两个主题都具备的
2. 每个相似点简洁（1-6个词）
3. 只输出相似点文本，每行一个，不要编号"""
        if sim_texts:
            prompt += f"""

图中已有相似点：{", ".join(sim_texts)}。请生成更聚焦、互补的相似点推荐，与已有相似点形成补充，避免重复。"""
        prompt += f"""

生成{count}个相似点："""
    else:
        topics_ctx = f"Left: {left}, Right: {right}" if left and right else "Topics not set"
        prompt = f"""The user is creating a double bubble map. {topics_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} similarity recommendations (shared by both topics). Requirements:
1. Similarities must apply to BOTH topics
2. Each similarity concise (1-6 words)
3. Output only similarity text, one per line, no numbering"""
        if sim_texts:
            sims = ", ".join(sim_texts)
            prompt += (
                f"\n\nThe diagram already has similarities: {sims}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} similarities:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_double_bubble_differences_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for double bubble map difference pair recommendations."""
    left = (context.get("left_topic") or "").strip()
    right = (context.get("right_topic") or "").strip()
    diff_texts = context.get("difference_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["double_bubble_map"][language]
    existing = existing or []

    if language == "zh":
        topics_ctx = f"左主题：{left}，右主题：{right}" if left and right else "主题未设置"
        prompt = f"""用户正在创建双气泡图。{topics_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个不同点对推荐，格式为「左主题特征 | 右主题特征」。要求：
1. 每对是左右主题的对比（左对应左主题，右对应右主题）
2. 每边简洁（1-6个词）
3. 只输出「左 | 右」格式，每行一对，不要编号"""
        if diff_texts:
            prompt += f"""

图中已有不同点对：{", ".join(diff_texts)}。请生成更聚焦、互补的不同点对推荐，与已有不同点对形成补充，避免重复。"""
        prompt += f"""

生成{count}个不同点对："""
    else:
        topics_ctx = f"Left: {left}, Right: {right}" if left and right else "Topics not set"
        prompt = f"""The user is creating a double bubble map. {topics_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} difference pair recommendations, format "left | right". Requirements:
1. Each pair contrasts left vs right topic (left side for left topic, right for right)
2. Each side concise (1-6 words)
3. Output only "left | right" format, one per line, no numbering"""
        if diff_texts:
            diffs = ", ".join(diff_texts)
            prompt += (
                f"\n\nThe diagram already has differences: {diffs}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} difference pairs:"""

    return append_batch_note(prompt, language, batch_num, existing)
