"""Brace map inline recommendation prompts."""

from typing import Any, Dict, List, Optional

from ._common import (
    append_batch_note,
    is_chinese_inline_prompt_language,
    THINKING_APPROACH,
    thinking_locale_key,
    BRACE_DIMENSION_TYPES_ZH,
    BRACE_DIMENSION_TYPES_EN,
)


def build_brace_dimensions_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for brace map dimension recommendations.

    Extracts user's main topic (whole) and asks LLM to generate topic-specific
    decomposition dimensions. Aligned with prompts/node_palette.get_brace_dimensions_prompt.
    """
    whole = (context.get("whole") or "").strip()
    context_desc = context.get("context_desc") or "General K12 teaching"
    dim_types = (
        BRACE_DIMENSION_TYPES_ZH if is_chinese_inline_prompt_language(language) else BRACE_DIMENSION_TYPES_EN
    )
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        whole_ctx = f'"{whole}"' if whole else "（整体未设置）"
        prompt = f"""为主题{whole_ctx}生成{count}个可能的拆解维度。

教学背景：{context_desc}

括号图可以使用不同的维度来拆解整体。请思考这个整体可以用哪些维度进行拆解。

{dim_types}

要求：
1. 每个维度要简洁明了，2-6个字
2. 维度要互不重叠、各具特色
3. 每个维度都应该能有效地拆解这个整体
4. 只输出维度名称，每行一个，不要编号

生成{count}个拆解维度："""
    else:
        whole_ctx = f'"{whole}"' if whole else "(whole not set)"
        prompt = f"""Generate {count} possible decomposition dimensions for: {whole_ctx}

Educational Context: {context_desc}

A brace map can decompose a whole using DIFFERENT DIMENSIONS. Think about what dimensions could be used to break down this whole.

{dim_types}

Requirements:
1. Each dimension should be concise, 2-6 words
2. Dimensions should be distinct and non-overlapping
3. Each dimension should be valid for decomposing this whole
4. Output only dimension names, one per line, no numbering

Generate {count} dimensions:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_brace_parts_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for brace map part recommendations."""
    whole = (context.get("whole") or "").strip()
    dimension = (context.get("dimension") or "").strip()
    part_names = context.get("part_names") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["brace_map"][thinking_locale_key(language)]
    dim_types = (
        BRACE_DIMENSION_TYPES_ZH if is_chinese_inline_prompt_language(language) else BRACE_DIMENSION_TYPES_EN
    )
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        whole_ctx = f"整体：{whole}" if whole else "整体未设置"
        dim_ctx = f"拆解维度：{dimension}" if dimension else "请自选拆解维度"
        prompt = f"""用户正在创建括号图。{whole_ctx}
{dim_ctx}

教学背景：{context_desc}
思维方式：{thinking}

{dim_types}

请生成{count}个组成部分推荐。要求：
1. 从同一维度拆解整体
2. 部分清晰、互不重叠（MECE原则）
3. 每个部分简洁（2-8个字）
4. 只输出部分名称，每行一个，不要编号"""
        if part_names:
            prompt += f"""

图中已有部分：{", ".join(part_names)}。请生成更聚焦、互补的部分推荐，与已有部分形成补充，避免重复。"""
        prompt += f"""

生成{count}个部分推荐："""
    else:
        whole_ctx = f"Whole: {whole}" if whole else "Whole not set"
        dim_ctx = f"Dimension: {dimension}" if dimension else "Choose a dimension"
        prompt = f"""The user is creating a brace map. {whole_ctx}
{dim_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

{dim_types}

Generate {count} part recommendations. Requirements:
1. Decompose from the same dimension
2. Parts clear, mutually exclusive (MECE)
3. Each part concise (2-8 words)
4. Output only part names, one per line, no numbering"""
        if part_names:
            parts = ", ".join(part_names)
            prompt += (
                f"\n\nThe diagram already has parts: {parts}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} part recommendations:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_brace_subparts_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for brace map subpart recommendations.

    Second-stage: we are working on part X, it has subparts Y.
    Generate more focused recommendations that build on these.
    """
    whole = (context.get("whole") or "").strip()
    dimension = (context.get("dimension") or "").strip()
    part_name = (context.get("part_name") or "").strip()
    subpart_texts = context.get("subpart_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        whole_ctx = f"整体：{whole}" if whole else "整体未设置"
        prompt = (
            f"""为以下部分生成{count}个子部分：{part_name}

{whole_ctx}
拆解维度：{dimension}

教学背景：{context_desc}

你能够绘制括号图，对部分进行细分。
思维方式：细化、分解
1. 子部分必须属于「{part_name}」"""
            + (f"，且属于「{dimension}」的拆解视角" if dimension else "，从任一合理拆解视角细分")
            + """
2. 子部分要清晰、互不重叠、完全穷尽（MECE原则）
3. 使用名词或名词短语，2-8个字
4. 只输出子部分名称，每行一个，不要编号"""
        )
        if subpart_texts:
            prompt += f"""

我们正在部分「{part_name}」下工作，该部分已有子部分：{", ".join(subpart_texts)}。请生成更聚焦、互补的子部分推荐，与已有子部分形成补充，避免重复。"""
        prompt += f"""

生成{count}个子部分："""
    else:
        whole_ctx = f"Whole: {whole}" if whole else "Whole not set"
        prompt = (
            f"""Generate {count} subparts for: {part_name}

{whole_ctx}
Decomposition dimension: {dimension}

Educational Context: {context_desc}

You can draw a brace map to break down parts into subparts.
Thinking approach: Refinement, Decomposition
1. Subparts must belong to "{part_name}" """
            + (
                f'and follow the "{dimension}" perspective'
                if dimension
                else "from any reasonable decomposition perspective"
            )
            + """
2. Subparts should be clear, mutually exclusive, collectively exhaustive (MECE)
3. Use nouns or noun phrases, 2-8 words
4. Output only subpart names, one per line, no numbering"""
        )
        if subpart_texts:
            subparts = ", ".join(subpart_texts)
            prompt += (
                f'\n\nWe are working on part "{part_name}". '
                f"It has existing subparts: {subparts}. "
                "Generate more focused, complementary subpart recommendations "
                "that build on these, avoid repetition."
            )
        prompt += f"""

Generate {count} subparts:"""

    return append_batch_note(prompt, language, batch_num, existing)
