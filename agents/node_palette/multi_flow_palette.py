"""
multi flow palette module.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Multi Flow Map Palette Generator
=================================

Generates nodes for Multi Flow Map with TWO modes:
1. Causes: individual cause nodes
2. Effects: individual effect nodes

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class MultiFlowPaletteGenerator(BasePaletteGenerator):
    """
    Multi Flow Map specific palette generator.

    Supports TWO generation modes:
    - 'causes': Generate individual cause nodes
    - 'effects': Generate individual effect nodes
    """

    def __init__(self):
        super().__init__()
        # Mode-specific session storage
        self.current_mode = {}  # session_id -> 'causes' | 'effects'
        # Note: Mode is passed through educational_context to avoid race conditions
        # with parallel catapults (no shared instance state!)

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,  # Central event
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        mode: str = 'causes',  # NEW: 'causes' or 'effects'
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with mode support.

        Args:
            mode: 'causes' for cause nodes, 'effects' for effect nodes
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
                node_id = node.get('id', 'unknown')
                node_text = node.get('text', '')
                logger.debug("[MultiFlow] Node tagged with mode='%s' | ID: %s | Text: %s", mode, node_id, node_text)

            yield chunk

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int
    ) -> str:
        """
        Build Multi Flow Map prompt based on current mode.

        Args:
            center_topic: Central event/topic
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)

        # Get educational context
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Extract mode from educational_context (thread-safe, no race conditions!)
        mode = educational_context.get('_mode', 'causes') if educational_context else 'causes'
        logger.debug("[MultiFlow] Building prompt for mode: %s", mode)

        # Build prompt based on mode
        if mode == 'causes':
            return self._build_causes_prompt(
                center_topic, context_desc, count, batch_num, language
            )
        else:  # effects
            return self._build_effects_prompt(
                center_topic, context_desc, count, batch_num, language
            )

    def _build_causes_prompt(
        self,
        event: str,
        context_desc: str,
        count: int,
        batch_num: int,
        language: str
    ) -> str:
        """Build prompt for causes (factors leading to the event)"""
        if language == 'zh':
            prompt = f"""为以下事件生成{count}个原因（导致事件发生的因素）：{event}

教学背景：{context_desc}

你能够绘制复流程图，分析一个中心事件的因果关系。
思维方式：找出导致该事件发生的原因和因素。
1. 从多个角度分析原因
2. 简洁明了，不要使用长句
3. 使用名词短语描述各种导致事件发生的因素
4. 原因可以是直接原因或间接原因

要求：每个原因要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出原因文本，每行一个，不要编号。

生成{count}个原因："""
        else:
            prompt = f"""Generate {count} causes (factors leading to the event) for: {event}

Educational Context: {context_desc}

You can draw a multi-flow map to analyze cause-and-effect relationships of a central event.
Thinking approach: Identify factors that CAUSED this event to happen.
1. Analyze causes from multiple angles
2. Be concise and clear, avoid long sentences
3. Use noun phrases to describe various factors that led to the event
4. Causes can be direct or indirect

Requirements: Each cause should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the cause text, one per line, no numbering.

Generate {count} causes:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度思考，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity from new dimensions and angles, avoid any repetition from previous batches."

        return prompt

    def _build_effects_prompt(
        self,
        event: str,
        context_desc: str,
        count: int,
        batch_num: int,
        language: str
    ) -> str:
        """Build prompt for effects (results and consequences of the event)"""
        if language == 'zh':
            prompt = f"""为以下事件生成{count}个结果（事件导致的影响和后果）：{event}

教学背景：{context_desc}

你能够绘制复流程图，分析一个中心事件的因果关系。
思维方式：找出该事件导致的结果和影响。
1. 从多个角度分析结果
2. 简洁明了，不要使用长句
3. 使用名词短语描述事件产生的各种影响和后果
4. 结果可以是直接结果或间接结果

要求：每个结果要简洁明了，可以超过4个字，但不要太长，避免完整句子。只输出结果文本，每行一个，不要编号。

生成{count}个结果："""
        else:
            prompt = f"""Generate {count} effects (results and consequences of the event) for: {event}

Educational Context: {context_desc}

You can draw a multi-flow map to analyze cause-and-effect relationships of a central event.
Thinking approach: Identify outcomes and impacts RESULTING from this event.
1. Analyze effects from multiple angles
2. Be concise and clear, avoid long sentences
3. Use noun phrases to describe various outcomes and consequences of the event
4. Effects can be immediate or long-term

Requirements: Each effect should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences. Output only the effect text, one per line, no numbering.

Generate {count} effects:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度思考，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity with new dimensions and angles of analysis, avoid any repetition from previous batches."

        return prompt

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """Clean up session including mode tracking"""
        super().end_session(session_id, reason)
        self.current_mode.pop(session_id, None)


# Global singleton  # pylint: disable=global-statement instance for Multi Flow Map
_multi_flow_palette_generator = None

def get_multi_flow_palette_generator() -> MultiFlowPaletteGenerator:
    """Get singleton instance of Multi Flow Map palette generator"""
    global _multi_flow_palette_generator  # pylint: disable=global-statement
    if _multi_flow_palette_generator is None:
        _multi_flow_palette_generator = MultiFlowPaletteGenerator()
    return _multi_flow_palette_generator

