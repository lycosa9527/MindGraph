"""
double bubble palette module.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Double Bubble Map Palette Generator
====================================

Generates nodes for Double Bubble Map with TWO modes:
1. Similarities: individual shared attributes
2. Differences: paired contrasting attributes

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class DoubleBubblePaletteGenerator(BasePaletteGenerator):
    """
    Double Bubble Map specific palette generator.

    Supports TWO generation modes:
    - 'similarities': Generate individual shared nodes
    - 'differences': Generate paired contrasting nodes
    """

    def __init__(self):
        super().__init__()
        # Mode-specific session storage
        self.current_mode = {}  # session_id -> 'similarities' | 'differences'
        # Note: Mode is passed through educational_context to avoid race conditions
        # with parallel catapults (no shared instance state!)

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,  # Will be "Topic1 vs Topic2"
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        mode: str = 'similarities',  # NEW: 'similarities' or 'differences'
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with mode support.

        Args:
            mode: 'similarities' for shared attributes, 'differences' for pairs
        """
        # Store mode for this session
        self.current_mode[session_id] = mode

        # Pass mode through educational_context to avoid race conditions
        # (Don't use instance variable - it's shared between parallel catapults!)
        if educational_context is None:
            educational_context = {}
        educational_context = dict(educational_context)  # Make a copy
        educational_context['_mode'] = mode  # Embed mode in context

        # Call parent's generate_batch (handles LLM streaming)
        async for chunk in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path
        ):
            # Add mode field to every node for explicit tracking
            if chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                node['mode'] = mode  # Tag node with its generation mode
                logger.debug("[DoubleBubble] Node tagged with mode='%s' | ID: %s", mode, node.get('id', 'unknown'))

            # For similarities mode, filter out any pipe-separated format (wrong format)
            if mode == 'similarities' and chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                text = node.get('text', '')

                # Similarities should be simple text - skip if it has pipe separator
                if '|' in text:
                    logger.warning("[DoubleBubble] SIMILARITIES mode - skipping node with pipe separator: '%s'", text)
                    continue  # Skip this node

            # For differences mode, parse pipe-separated pairs and add left/right fields
            if mode == 'differences' and chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                text = node.get('text', '')

                logger.debug("[DoubleBubble] DIFFERENCES mode - processing node with text: '%s'", text)

                # Differences MUST have pipe separator - skip if it doesn't
                if '|' not in text:
                    logger.warning("[DoubleBubble] DIFFERENCES mode - skipping node without pipe separator: '%s'", text)
                    continue  # Skip this node

                # Parse topics from center_topic for filtering
                left_topic, right_topic = self._parse_topics  # pylint: disable=protected-access(center_topic)
                left_topic_lower = left_topic.lower().strip()
                right_topic_lower = right_topic.lower().strip()

                # Parse pipe-separated format: "left_attr | right_attr | dimension" (dimension is optional)
                parts = text.split('|')  # Split on all pipes
                if len(parts) >= 2:
                    left_text = parts[0].strip()
                    right_text = parts[1].strip()
                    dimension = parts[2].strip() if len(parts) >= 3 else None

                    # Filter out invalid/unwanted nodes:
                    # 1. Main topic names only (e.g., "福特 | 大众")
                    if (left_text.lower() == left_topic_lower and right_text.lower() == right_topic_lower):
                        logger.debug("[DoubleBubble] Skipping main topic node: '%s | %s'", left_text, right_text)
                        continue

                    # 2. Empty or very short values (likely formatting artifacts)
                    if len(left_text) < 2 or len(right_text) < 2:
                        logger.debug("[DoubleBubble] Skipping too short: '%s | %s'", left_text, right_text)
                        continue

                    # 3. Markdown table separators (e.g., "| ---" or "---")
                    if left_text.startswith('-') or right_text.startswith('-'):
                        logger.debug("[DoubleBubble] Skipping markdown separator: '%s | %s'", left_text, right_text)
                        continue

                    # 4. Header-like patterns containing "vs" or similar
                    if ('vs' in left_text.lower() and 'vs' in right_text.lower()):
                        logger.debug("[DoubleBubble] Skipping header pattern: '%s | %s'", left_text, right_text)
                        continue

                    # Valid difference pair - add left, right, and optional dimension fields
                    node['left'] = left_text
                    node['right'] = right_text
                    if dimension and len(dimension) > 0:
                        node['dimension'] = dimension
                    # Keep text as-is for backwards compatibility
                    node['text'] = text

                    dim_info = " | dimension='%s'" % dimension if dimension else ""
                    logger.debug("[DoubleBubble] Parsed pair successfully: left='%s' | right='%s'%s", left_text, right_text, dim_info)
                    logger.debug("[DoubleBubble] Node now has: %s", list(node.keys()))
                else:
                    # Malformed pipe-separated format (has | but couldn't parse properly)
                    logger.warning("[DoubleBubble] DIFFERENCES mode - skipping malformed node: '%s'", text)
                    continue

            yield chunk

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Double Bubble Map prompt based on current mode.

        Args:
            center_topic: "Left Topic vs Right Topic" format
        """
        # Parse topics from center_topic
        # Expected format: "Cats vs Dogs" or "猫 vs 狗"
        left_topic, right_topic = self._parse_topics  # pylint: disable=protected-access(center_topic)

        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)

        # Get educational context
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Extract mode from educational_context (thread-safe, no race conditions!)
        mode = educational_context.get('_mode', 'similarities') if educational_context else 'similarities'
        logger.debug("[DoubleBubble] Building prompt for mode: %s", mode)

        # Build prompt based on mode
        if mode == 'similarities':
            return self._build_similarities_prompt(
                left_topic, right_topic, context_desc, count, batch_num, language
            )
        else:  # differences
            return self._build_differences_prompt(
                left_topic, right_topic, context_desc, count, batch_num, language
            )

    def _parse_topics(self, center_topic: str) -> tuple:
        """Parse 'Left vs Right' into (left, right)"""
        # Handle both "vs" and "VS" and Chinese "对比"
        separators = [' vs ', ' VS ', ' 对比 ', '对比']

        for sep in separators:
            if sep in center_topic:
                parts = center_topic.split(sep, 1)
                return (parts[0].strip(), parts[1].strip())

        # Fallback: assume two topics separated by space
        parts = center_topic.split(None, 1)
        if len(parts) == 2:
            return (parts[0], parts[1])

        return (center_topic, center_topic)

    def _build_similarities_prompt(
        self,
        left_topic: str,
        right_topic: str,
        context_desc: str,
        count: int,
        batch_num: int,
        language: str
    ) -> str:
        """Build prompt for similarities (shared attributes)"""
        if language == 'zh':
            prompt = f"""为以下两个主题生成{count}个共同属性（相似点）：{left_topic} 和 {right_topic}

教学背景：{context_desc}

你能够绘制双气泡图，对两个中心词进行对比，输出他们的相同点。
思维方式：找出两者都具备的特征。
1. 从多个角度进行对比
2. 简洁明了，不要使用长句
3. 使用形容词或名词短语描述两者共享的特征

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出共同属性文本，每行一个，不要编号。

生成{count}个相似点："""
        else:
            prompt = f"""Generate {count} shared attributes (similarities) for: {left_topic} and {right_topic}

Educational Context: {context_desc}

You can draw a double bubble map to compare two central topics and output their similarities.
Thinking approach: Identify characteristics that BOTH topics share.
1. Compare from multiple angles
2. Be concise and clear, avoid long sentences
3. Use adjectives or noun phrases to describe shared features

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the attribute text, one per line, no numbering.

Generate {count} similarities:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度思考，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity from new dimensions, avoid any repetition from previous batches."

        return prompt

    def _build_differences_prompt(
        self,
        left_topic: str,
        right_topic: str,
        context_desc: str,
        count: int,
        batch_num: int,
        language: str
    ) -> str:
        """Build prompt for differences (paired contrasting attributes)"""
        if language == 'zh':
            prompt = f"""为以下两个主题生成{count}组对比属性（差异对）：{left_topic} vs {right_topic}

教学背景：{context_desc}

你能够绘制双气泡图，对两个中心词进行对比，输出他们的不同点。
思维方式：找出两者的不同点，形成对比。
1. 从多个角度进行对比
2. 简洁明了，不要使用长句
3. 不同点要一一对应。例如对比苹果和香蕉，如果{left_topic}的属性是"红色"，那么{right_topic}的对比属性必须是"黄色"，都属于颜色维度
4. 每组差异包含两个对比属性和对比维度

输出格式：每行一对，用 | 分隔，格式如下：
{left_topic}的属性 | {right_topic}的对比属性 | 对比维度

示例：
强调动力与载重性能 | 强调操控与燃油效率 | 性能侧重点
皮卡销量占比高 | 旅行车销量占比高 | 车型结构

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。对比维度要简洁（2-6个字），每行一对，用竖线分隔，不要编号。

生成{count}个差异对："""
        else:
            prompt = f"""Generate {count} contrasting attribute pairs (difference pairs) for: {left_topic} vs {right_topic}

Educational Context: {context_desc}

You can draw a double bubble map to compare two central topics and output their differences.
Thinking approach: Identify unique characteristics that differentiate the two topics.
1. Compare from multiple angles
2. Be concise and clear, avoid long sentences
3. Differences should correspond one-to-one. For example, when comparing apples and bananas, if {left_topic}'s attribute is "red", then {right_topic}'s contrasting attribute must be "yellow", both belonging to the color dimension
4. Each pair contains two contrasting attributes and a comparison dimension

Output format: One pair per line, separated by |
attribute of {left_topic} | contrasting attribute of {right_topic} | comparison dimension

Examples:
Emphasizes power and payload | Emphasizes handling and fuel efficiency | Performance Focus
Pickup truck dominant | Hatchback dominant | Vehicle Type

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Dimension should be concise (2-6 words). One pair per line, separated by pipe character, no numbering.

Generate {count} difference pairs:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度对比，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity with new dimensions and angles of contrast, avoid any repetition from previous batches."

        return prompt

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """Clean up session including mode tracking"""
        super().end_session(session_id, reason)
        self.current_mode.pop(session_id, None)


# Global singleton  # pylint: disable=global-statement instance for Double Bubble Map
_double_bubble_palette_generator = None

def get_double_bubble_palette_generator() -> DoubleBubblePaletteGenerator:
    """Get singleton instance of Double Bubble Map palette generator"""
    global _double_bubble_palette_generator  # pylint: disable=global-statement
    if _double_bubble_palette_generator is None:
        _double_bubble_palette_generator = DoubleBubblePaletteGenerator()
    return _double_bubble_palette_generator

