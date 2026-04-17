"""Tree map inline recommendation prompts.

Aligned with prompts/node_palette.get_tree_dimensions_prompt,
get_tree_categories_prompt, get_tree_items_prompt.
"""

from typing import Any, Dict, List, Optional

from ._common import (
    append_batch_note,
    is_chinese_inline_prompt_language,
    TREE_DIMENSION_TYPES_ZH,
    TREE_DIMENSION_TYPES_EN,
)


def build_tree_dimensions_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for tree map dimension recommendations.

    Extracts topic and asks LLM to generate topic-specific classification
    dimensions. Aligned with prompts/node_palette.get_tree_dimensions_prompt.
    """
    topic = (context.get("topic") or "").strip()
    context_desc = context.get("context_desc") or "General K12 teaching"
    dim_types = TREE_DIMENSION_TYPES_ZH if is_chinese_inline_prompt_language(language) else TREE_DIMENSION_TYPES_EN
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        topic_ctx = f'"{topic}"' if topic else "（主题未设置）"
        prompt = f"""为主题{topic_ctx}生成{count}个可能的分类维度。

教学背景：{context_desc}

树状图可以使用不同的维度来分类主题。请思考这个主题可以用哪些维度进行分类。

{dim_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地分类这个主题
4. 只输出维度名称，每行一个，不要编号

生成{count}个分类维度："""
    else:
        topic_ctx = f'"{topic}"' if topic else "(topic not set)"
        prompt = f"""Generate {count} possible classification dimensions for topic: {topic_ctx}

Educational Context: {context_desc}

A tree map can classify a topic using DIFFERENT DIMENSIONS. Think about what dimensions could be used to classify this topic.

{dim_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for classifying this topic
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_tree_categories_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for tree map category recommendations."""
    topic = (context.get("topic") or "").strip()
    dimension = (context.get("dimension") or "").strip()
    category_names = context.get("category_names") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        header = (
            f"为主题「{topic}」生成{count}个分类类别，使用分类维度：{dimension}"
            if dimension
            else f"为主题「{topic}」生成{count}个树状图分类类别"
        )
        dim_req = f"，遵循「{dimension}」" if dimension else ""
        prompt = f"""{header}

教学背景：{context_desc}

要求：
1. 从同一个分类维度进行分类{dim_req}
2. 类别要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出类别名称，每行一个，不要编号
5. 不要生成具体的子项目，只生成类别名称"""
        if category_names:
            prompt += f"""

图中已有类别：{", ".join(category_names)}。请生成更聚焦、互补的类别推荐，与已有类别形成补充，避免重复。"""
        prompt += f"""

生成{count}个类别："""
    else:
        header = (
            f"Generate {count} categories for: {topic}, using dimension: {dimension}"
            if dimension
            else f"Generate {count} categories for: {topic}"
        )
        req1 = (
            f'1. ALL categories MUST follow the "{dimension}" dimension'
            if dimension
            else "1. Classify using a consistent dimension"
        )
        prompt = f"""{header}

Educational Context: {context_desc}

Requirements:
{req1}
2. Categories should be clear, mutually exclusive, collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only category names, one per line, no numbering
5. Do NOT generate sub-items, only category names"""
        if category_names:
            cats = ", ".join(category_names)
            prompt += (
                f"\n\nThe diagram already has categories: {cats}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} categories:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_tree_items_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for tree map item recommendations.

    Second-stage: we are working on category X, it has items Y.
    Generate more focused recommendations that build on these.
    """
    topic = (context.get("topic") or "").strip()
    dimension = (context.get("dimension") or "").strip()
    category_name = (context.get("category_name") or "").strip()
    item_texts = context.get("item_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        topic_ctx = f"主题：{topic}" if topic else "主题未设置"
        prompt = f"""为类别「{category_name}」生成{count}个具体条目

{topic_ctx}
分类维度：{dimension}

教学背景：{context_desc}

要求：
1. 所有条目必须属于「{category_name}」且遵循「{dimension}」维度
2. 条目要清晰、互不重叠
3. 使用名词或名词短语，2-8个字
4. 只输出条目名称，每行一个，不要编号"""
        if item_texts:
            prompt += f"""

我们正在类别「{category_name}」下工作，该类别已有条目：{", ".join(item_texts)}。请生成更聚焦、互补的条目推荐，与已有条目形成补充，避免重复。"""
        prompt += f"""

生成{count}个条目："""
    else:
        topic_ctx = f"Topic: {topic}" if topic else "Topic not set"
        prompt = f"""Generate {count} items for category: {category_name}

{topic_ctx}
Classification dimension: {dimension}

Educational Context: {context_desc}

Requirements:
1. ALL items must belong to "{category_name}" and follow the "{dimension}" dimension
2. Items should be clear and non-overlapping
3. Use nouns or noun phrases, 2-8 words
4. Output only item names, one per line, no numbering"""
        if item_texts:
            items = ", ".join(item_texts)
            prompt += (
                f'\n\nWe are working on category "{category_name}". '
                f"It has existing items: {items}. "
                "Generate more focused, complementary item recommendations "
                "that build on these, avoid repetition."
            )
        prompt += f"""

Generate {count} items:"""

    return append_batch_note(prompt, language, batch_num, existing)
