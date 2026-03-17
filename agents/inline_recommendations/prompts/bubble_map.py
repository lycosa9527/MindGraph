"""Bubble map inline recommendation prompts.

Aligned with agents/node_palette/bubble_map_palette.py.
Follows concept map relationship label prompt structure (concrete examples, RULES, OUTPUT).
"""
from typing import Any, Dict, List, Optional

from ._common import append_batch_note, THINKING_APPROACH


def build_bubble_attributes_prompt(
    context: Dict[str, Any],
    language: str,
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """Build prompt for bubble map attribute recommendations."""
    topic = (context.get('topic') or '').strip()
    attribute_texts = context.get('attribute_texts') or []
    context_desc = context.get('context_desc') or 'General K12 teaching'
    thinking = THINKING_APPROACH['bubble_map'][language]
    existing = existing or []

    if language == 'zh':
        topic_ctx = f"为以下主题生成{count}个气泡图属性词：{topic}" if topic else "主题未设置"
        prompt = f"""{topic_ctx}

教学背景：{context_desc}

你能够生成气泡图属性，使用形容词或描述性短语来描述核心主题的属性。
思维方式：{thinking}
1. 使用形容词或形容词短语
2. 从多个维度对中心词进行描述
3. 能够从多个角度进行发散、联想，角度越广越好
4. 特征词要尽可能简洁"""
        if attribute_texts:
            prompt += f"""

图中已有属性：{', '.join(attribute_texts)}。请生成更聚焦、互补的属性推荐，与已有属性形成补充，避免重复。"""
        prompt += f"""

规则：
- 每条只输出一个属性词文本。每行一个。不要编号、不要前缀、不要括号注释。
- 使用形容词或形容词短语，简洁明了，避免完整句子。
- 必须输出至少{count}个，每个占一行。

多行输出示例（每行一个属性词）：
水果：
甜美多汁
色彩丰富
富含维生素
形态多样
香气怡人

动物：
灵活敏捷
善于适应
种类繁多
栖息多样

输出：至少{count}行。每行一个属性词。"""
    else:
        topic_ctx = (
            f"Generate {count} Bubble Map attribute words for: {topic}"
            if topic
            else "Topic not set"
        )
        prompt = f"""{topic_ctx}

Educational Context: {context_desc}

You can generate bubble map attributes using adjectives or descriptive phrases to describe the attributes of the core topic.
Thinking approach: {thinking}
1. Use adjectives or adjectival phrases
2. Describe the central topic from multiple dimensions
3. Be able to diverge and associate from multiple angles, the wider the angle the better
4. Feature words should be as concise as possible"""
        if attribute_texts:
            attrs = ', '.join(attribute_texts)
            prompt += (
                f"\n\nThe diagram already has attributes: {attrs}. "
                "Generate more focused, complementary recommendations, avoid repetition."
            )
        prompt += f"""

RULES:
- Output only one attribute per line. No numbering. No prefix. No parenthetical notes.
- Use adjectives or adjectival phrases. Keep concise. Avoid full sentences.
- You must output at least {count} items, one per line.

MULTI-LINE OUTPUT EXAMPLES (each line = one attribute):
fruit:
sweet and juicy
colorful
rich in vitamins
diverse shapes
pleasant aroma

animal:
agile and flexible
adaptable
diverse species
varied habitats

OUTPUT: At least {count} lines. Each line = one attribute. Minimum {count}."""

    return append_batch_note(prompt, language, batch_num, existing)
