"""Flow map inline recommendation prompts.

Aligned with prompts/node_palette.get_flow_steps_prompt,
get_flow_substeps_prompt.
"""
from typing import Any, Dict, List, Optional

from ._common import append_batch_note


def build_flow_steps_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for flow map step recommendations."""
    topic = (context.get('topic') or '').strip()
    step_names = context.get('step_names') or []
    context_desc = context.get('context_desc') or 'General K12 teaching'
    existing = existing or []

    if language == 'zh':
        topic_ctx = f"为流程「{topic}」生成{count}个按时间顺序排列的步骤" if topic else "流程未设置"
        prompt = f"""{topic_ctx}

教学背景：{context_desc}

你能够绘制流程图，展示过程的各个步骤。
思维方式：顺序、流程
1. 步骤要按时间顺序排列（从早到晚，从开始到结束）
2. 每个步骤要简洁明了，不要使用完整句子
3. 使用动宾短语或名词短语描述步骤
4. 步骤之间要有逻辑关联"""
        if step_names:
            prompt += f"""

图中已有步骤：{', '.join(step_names)}。请生成更聚焦、互补的步骤推荐，与已有步骤形成补充，避免重复。"""
        prompt += """

要求：每个步骤要简洁明了（1-6个词），不要标点符号，不要编号前缀。只输出步骤文本，每行一个。请按照时间顺序从早到晚排列步骤。

生成{count}个按顺序的步骤："""
    else:
        topic_ctx = (
            f"Generate {count} chronologically ordered steps for: {topic}"
            if topic
            else "Flow not set"
        )
        prompt = f"""{topic_ctx}

Educational Context: {context_desc}

You can draw a flow map to show the steps of a process.
Thinking approach: Sequential, Procedural
1. Steps should be in chronological order (from beginning to end)
2. Each step should be concise and clear, avoid full sentences
3. Use action phrases or noun phrases to describe steps
4. Steps should be logically connected"""
        if step_names:
            steps = ', '.join(step_names)
            prompt += (
                f"\n\nThe diagram already has steps: {steps}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += """

Requirements: Each step concise (1-6 words), no punctuation, no numbering prefixes. Output only step text, one per line. Arrange steps in chronological order from earliest to latest.

Generate {count} ordered steps:"""

    return append_batch_note(prompt, language, batch_num, existing)


def build_flow_substeps_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for flow map substep recommendations.

    Second-stage: we are working on step X, it has substeps Y.
    Generate more focused recommendations that build on these.
    """
    topic = (context.get('topic') or '').strip()
    step_name = (context.get('step_name') or '').strip()
    substep_texts = context.get('substep_texts') or []
    context_desc = context.get('context_desc') or 'General K12 teaching'
    existing = existing or []

    if language == 'zh':
        topic_ctx = f"流程：{topic}" if topic else "流程未设置"
        prompt = f"""为步骤「{step_name}」生成{count}个子步骤

{topic_ctx}

教学背景：{context_desc}

你能够绘制流程图，展示过程的子步骤。
思维方式：细化、展开
1. 子步骤必须属于「{step_name}」，是具体执行动作
2. 每个子步骤要简洁明了（1-7个词），不要重复主要步骤
3. 使用动宾短语或名词短语
4. 只输出子步骤文本，每行一个，不要编号"""
        if substep_texts:
            prompt += f"""

我们正在步骤「{step_name}」下工作，该步骤已有子步骤：{', '.join(substep_texts)}。请生成更聚焦、互补的子步骤推荐，与已有子步骤形成补充，避免重复。"""
        prompt += f"""

生成{count}个子步骤："""
    else:
        topic_ctx = f"Flow: {topic}" if topic else "Flow not set"
        prompt = f"""Generate {count} substeps for step: {step_name}

{topic_ctx}

Educational Context: {context_desc}

You can draw a flow map to show substeps of a process.
Thinking approach: Refinement, Expansion
1. Substeps must belong to "{step_name}", concrete actions
2. Each substep concise (1-7 words), avoid repeating the step text
3. Use action phrases or noun phrases
4. Output only substep text, one per line, no numbering"""
        if substep_texts:
            substeps = ', '.join(substep_texts)
            prompt += (
                f"\n\nWe are working on step \"{step_name}\". "
                f"It has existing substeps: {substeps}. "
                "Generate more focused, complementary substep recommendations "
                "that build on these, avoid repetition."
            )
        prompt += f"""

Generate {count} substeps:"""

    return append_batch_note(prompt, language, batch_num, existing)
