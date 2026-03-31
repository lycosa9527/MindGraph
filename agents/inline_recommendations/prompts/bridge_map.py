"""Bridge map inline recommendation prompts."""

from typing import Any, Dict, List, Optional

from ._common import (
    append_batch_note,
    THINKING_APPROACH,
    BRIDGE_DIMENSION_TYPES_ZH,
    BRIDGE_DIMENSION_TYPES_EN,
)


def build_bridge_dimensions_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for bridge map dimension recommendations."""
    dimension = (context.get("dimension") or "").strip()
    pair_texts = context.get("pair_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["bridge_map"][language]
    dim_types = BRIDGE_DIMENSION_TYPES_ZH if language == "zh" else BRIDGE_DIMENSION_TYPES_EN
    existing = existing or []

    if language == "zh":
        dim_ctx = f"当前维度：{dimension}" if dimension else "请推荐类比关系维度"
        prompt = f"""用户正在创建桥型图。{dim_ctx}

教学背景：{context_desc}
思维方式：{thinking}

{dim_types}

请生成{count}个类比关系维度推荐。要求：
1. 维度用于类比（如：部分与整体、原因与结果）
2. 每个维度简洁（2-6个字）
3. 只输出维度名称，每行一个，不要编号"""
        if pair_texts:
            prompt += f"""

图中已有类比对：{", ".join(pair_texts)}。请生成更聚焦、互补的维度推荐，与已有类比对形成补充，避免重复。"""
        prompt += f"""

生成{count}个维度："""
    else:
        dim_ctx = f"Current dimension: {dimension}" if dimension else "Recommend analogy dimensions"
        prompt = f"""The user is creating a bridge map. {dim_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

{dim_types}

Generate {count} analogy dimension recommendations. Requirements:
1. Dimensions for analogies (e.g. part-whole, cause-effect)
2. Each dimension concise (2-6 words)
3. Output only dimension names, one per line, no numbering"""
        if pair_texts:
            pairs = ", ".join(pair_texts)
            prompt += (
                f"\n\nThe diagram already has pairs: {pairs}. "
                "Generate more focused, complementary dimension recommendations, "
                "avoid repetition."
            )
        prompt += f"""

Generate {count} dimensions:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_bridge_pairs_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for bridge map analogy pair recommendations."""
    dimension = (context.get("dimension") or "").strip()
    pair_texts = context.get("pair_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["bridge_map"][language]
    existing = existing or []

    if language == "zh":
        dim_ctx = f"类比维度：{dimension}" if dimension else "请遵循同一类比关系"
        prompt = f"""用户正在创建桥型图。{dim_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个类比对推荐，格式为「左 | 右」。要求：
1. 每对遵循同一类比维度
2. 左与右具有类比关系
3. 每边简洁（2-8个字）
4. 只输出「左 | 右」格式，每行一对，不要编号"""
        if pair_texts:
            prompt += f"""

图中已有类比对：{", ".join(pair_texts)}。请生成更聚焦、互补的类比对推荐，与已有类比对形成补充，避免重复。"""
        prompt += f"""

生成{count}个类比对："""
    else:
        dim_ctx = f"Dimension: {dimension}" if dimension else "Follow same analogy relation"
        prompt = f"""The user is creating a bridge map. {dim_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} analogy pair recommendations, format "left | right". Requirements:
1. Each pair follows the same analogy dimension
2. Left and right have analogy relation
3. Each side concise (2-8 words)
4. Output only "left | right" format, one per line, no numbering"""
        if pair_texts:
            pairs = ", ".join(pair_texts)
            prompt += (
                f"\n\nThe diagram already has pairs: {pairs}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} analogy pairs:"""

    return append_batch_note(prompt, language, batch_num, existing)
