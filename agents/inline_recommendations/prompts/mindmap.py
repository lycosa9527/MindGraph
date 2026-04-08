"""Mindmap inline recommendation prompts.

Aligned with prompts/node_palette.get_mindmap_branches_prompt,
get_mindmap_children_prompt.
"""

from typing import Any, Dict, List, Optional

from ._common import append_batch_note, is_chinese_inline_prompt_language, THINKING_APPROACH, thinking_locale_key


def build_mindmap_branches_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for mindmap branch recommendations."""
    topic = (context.get("topic") or "").strip()
    branch_names = context.get("branch_names") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    thinking = THINKING_APPROACH["mindmap"][thinking_locale_key(language)]
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        topic_ctx = f"为以下主题生成{count}个思维导图分支想法：{topic}" if topic else "主题未设置"
        prompt = f"""{topic_ctx}

教学背景：{context_desc}

你能够绘制思维导图，进行发散思维和头脑风暴。
思维方式：{thinking}
1. 从多个角度对中心主题进行联想
2. 分支要覆盖不同的维度和方面
3. 每个分支要简洁明了，使用名词或名词短语
4. 鼓励创造性和多样性思考"""
        if branch_names:
            prompt += f"""

图中已有分支：{", ".join(branch_names)}。请生成更聚焦、互补的分支推荐，与已有分支形成补充，避免重复。"""
        prompt += f"""

要求：每个分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出分支文本，每行一个。

生成{count}个分支想法："""
    else:
        topic_ctx = f"Generate {count} Mind Map branch ideas for: {topic}" if topic else "Topic not set"
        prompt = f"""{topic_ctx}

Educational Context: {context_desc}

You can draw a mind map for divergent thinking and brainstorming.
Thinking approach: {thinking}
1. Associate from multiple angles around the central topic
2. Branches should cover different dimensions and aspects
3. Each branch should be concise, using nouns or noun phrases
4. Encourage creative and diverse thinking"""
        if branch_names:
            branches = ", ".join(branch_names)
            prompt += (
                f"\n\nThe diagram already has branches: {branches}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Requirements: Each branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only the branch text, one per line.

Generate {count} branch ideas:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_mindmap_children_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for mindmap children (sub-branches) recommendations.

    Second-stage: we are working on branch X, it has children Y.
    Generate more focused recommendations that build on these.
    """
    topic = (context.get("topic") or "").strip()
    branch_name = (context.get("branch_name") or "").strip()
    children_texts = context.get("children_texts") or []
    context_desc = context.get("context_desc") or "General K12 teaching"
    existing = existing or []

    if is_chinese_inline_prompt_language(language):
        topic_ctx = f"主题：{topic}" if topic else "主题未设置"
        prompt = f"""为思维导图分支「{branch_name}」生成{count}个子分支想法

{topic_ctx}
上级分支：{branch_name}

教学背景：{context_desc}

你能够为思维导图分支生成子想法，进一步细化和展开这个分支。
思维方式：深入、细化、展开
1. 围绕「{branch_name}」这个分支进行更深入的思考
2. 子分支应该是该分支的具体展开或细节
3. 每个子分支要简洁明了，使用名词或名词短语
4. 保持与上级分支的逻辑关联性"""
        if children_texts:
            prompt += f"""

我们正在分支「{branch_name}」下工作，该分支已有子节点：{", ".join(children_texts)}。请生成更聚焦、互补的子分支推荐，与已有子节点形成补充，避免重复。"""
        prompt += f"""

要求：每个子分支想法要简洁明了（1-5个词），不要使用完整句子，不要编号。只输出子分支文本，每行一个。

生成{count}个子分支想法："""
    else:
        topic_ctx = f"Topic: {topic}" if topic else "Topic not set"
        prompt = f"""Generate {count} sub-branch ideas for mind map branch: {branch_name}

{topic_ctx}
Parent branch: {branch_name}

Educational Context: {context_desc}

You can generate sub-ideas for mind map branches to refine and expand.
Thinking approach: In-depth, Refinement, Expansion
1. Think more deeply around the branch "{branch_name}"
2. Sub-branches should be concrete expansions or details of this branch
3. Each sub-branch should be concise, using nouns or noun phrases
4. Maintain logical connection with the parent branch"""
        if children_texts:
            children = ", ".join(children_texts)
            prompt += (
                f'\n\nWe are working on branch "{branch_name}". '
                f"It has existing children: {children}. "
                "Generate more focused, complementary sub-branch recommendations "
                "that build on these, avoid repetition."
            )
        prompt += f"""

Requirements: Each sub-branch idea should be concise (1-5 words), avoid full sentences, no numbering. Output only sub-branch text, one per line.

Generate {count} sub-branch ideas:"""

    return append_batch_note(prompt, language, batch_num, existing)
