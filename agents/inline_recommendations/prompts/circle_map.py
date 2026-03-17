"""Circle map inline recommendation prompts."""
from typing import Any, Dict, List, Optional

from ._common import append_batch_note, THINKING_APPROACH


def build_circle_observations_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for circle map observation recommendations."""
    topic = (context.get('topic') or '').strip()
    context_texts = context.get('context_texts') or []
    context_desc = context.get('context_desc') or 'General K12 teaching'
    thinking = THINKING_APPROACH['circle_map'][language]
    existing = existing or []

    if language == 'zh':
        topic_ctx = f"主题：{topic}" if topic else "主题未设置"
        prompt = f"""用户正在创建圆圈图。{topic_ctx}

教学背景：{context_desc}
思维方式：{thinking}

请生成{count}个观察点/联想推荐。要求：
1. 围绕主题进行发散、联想
2. 从多个角度观察
3. 每个观察点简洁（1-6个词）
4. 只输出观察点文本，每行一个，不要编号"""
        if context_texts:
            prompt += f"""

图中已有观察点：{', '.join(context_texts)}。请生成更聚焦、互补的观察点推荐，与已有观察点形成补充，避免重复。"""
        prompt += f"""

生成{count}个观察点："""
    else:
        topic_ctx = f"Topic: {topic}" if topic else "Topic not set"
        prompt = f"""The user is creating a circle map. {topic_ctx}

Educational Context: {context_desc}
Thinking approach: {thinking}

Generate {count} observation/association recommendations. Requirements:
1. Diverge and associate around the topic
2. Observe from multiple angles
3. Each observation concise (1-6 words)
4. Output only observation text, one per line, no numbering"""
        if context_texts:
            obs = ', '.join(context_texts)
            prompt += (
                f"\n\nThe diagram already has observations: {obs}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

Generate {count} observations:"""

    return append_batch_note(prompt, language, batch_num, existing)
