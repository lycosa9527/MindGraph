"""Multi Flow Map Palette Generator.

Generates nodes for Multi Flow Map with TWO fixed tabs:
1. Causes: individual cause nodes
2. Effects: individual effect nodes

When mode='both', generates causes and effects concurrently (like double bubble).
"""

import asyncio
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

logger = logging.getLogger(__name__)


class MultiFlowPaletteGenerator(BasePaletteGenerator):
    """
    Multi Flow Map specific palette generator.

    Supports TWO fixed tabs with concurrent generation:
    - 'causes': Generate individual cause nodes
    - 'effects': Generate individual effect nodes
    - 'both': Generate causes and effects concurrently (default for start/next)
    """

    def __init__(self):
        super().__init__()
        self.current_mode = {}

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        _mode: Optional[str] = None,
        _stage: Optional[str] = None,
        _stage_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with mode support.

        Args:
            _mode: 'causes', 'effects', or 'both' (both = concurrent generation)
        """
        mode = _mode or "causes"
        self.current_mode[session_id] = mode

        if mode == "both":
            async for chunk in self._generate_both(
                session_id=session_id,
                center_topic=center_topic,
                educational_context=educational_context,
                nodes_per_llm=nodes_per_llm,
                user_id=user_id,
                organization_id=organization_id,
                diagram_type=diagram_type,
                endpoint_path=endpoint_path,
            ):
                yield chunk
            return

        ctx = dict(educational_context or {})
        ctx["_mode"] = mode
        async for chunk in self._stream_single_mode(
            session_id,
            center_topic,
            ctx,
            nodes_per_llm,
            mode,
            _stage,
            _stage_data,
            user_id,
            organization_id,
            diagram_type,
            endpoint_path,
        ):
            yield chunk

    async def _stream_single_mode(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Dict[str, Any],
        nodes_per_llm: int,
        mode: str,
        _stage: Optional[str],
        _stage_data: Optional[Dict[str, Any]],
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: Optional[str],
        endpoint_path: Optional[str],
    ) -> AsyncGenerator[Dict, None]:
        """Stream nodes for a single mode (causes or effects)."""
        async for chunk in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm,
            _mode=mode,
            _stage=_stage,
            _stage_data=_stage_data,
            user_id=user_id,
            organization_id=organization_id,
            diagram_type=diagram_type,
            endpoint_path=endpoint_path,
        ):
            if chunk.get("event") == "node_generated":
                node = chunk.get("node", {})
                node["mode"] = mode
                logger.debug(
                    "[MultiFlow] Node tagged with mode='%s' | ID: %s | Text: %s",
                    mode,
                    node.get("id", "unknown"),
                    node.get("text", ""),
                )
            yield chunk

    async def _generate_both(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        nodes_per_llm: int,
        user_id: Optional[int],
        organization_id: Optional[int],
        diagram_type: Optional[str],
        endpoint_path: Optional[str],
    ) -> AsyncGenerator[Dict, None]:
        """Run causes and effects generation concurrently, merge streams."""
        queue: asyncio.Queue = asyncio.Queue()
        opts = {
            "ctx": dict(educational_context or {}),
            "session_id": session_id,
            "center_topic": center_topic,
            "nodes_per_llm": nodes_per_llm,
            "user_id": user_id,
            "organization_id": organization_id,
            "diagram_type": diagram_type,
            "endpoint_path": endpoint_path,
        }

        async def run_mode(mode_val: str) -> None:
            sub_id = f"{opts['session_id']}_{mode_val}"
            try:
                async for chunk in self.generate_batch(
                    session_id=sub_id,
                    center_topic=opts["center_topic"],
                    educational_context={**opts["ctx"], "_mode": mode_val},
                    nodes_per_llm=opts["nodes_per_llm"],
                    _mode=mode_val,
                    user_id=opts["user_id"],
                    organization_id=opts["organization_id"],
                    diagram_type=opts["diagram_type"],
                    endpoint_path=opts["endpoint_path"],
                ):
                    await queue.put(("chunk", chunk))
            finally:
                await queue.put(("done", mode_val))

        tasks = [
            asyncio.create_task(run_mode("causes")),
            asyncio.create_task(run_mode("effects")),
        ]
        done_count = 0
        while done_count < 2:
            msg = await queue.get()
            if msg[0] == "done":
                done_count += 1
            else:
                yield msg[1]
        await asyncio.gather(*tasks)
        self.end_session(f"{session_id}_causes", "complete")
        self.end_session(f"{session_id}_effects", "complete")

    def _build_prompt(
        self,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]],
        count: int,
        batch_num: int,
    ) -> str:
        """
        Build Multi Flow Map prompt based on current mode.

        Args:
            center_topic: Central event/topic
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language(center_topic, educational_context)

        # Get educational context
        context_desc = (
            educational_context.get("raw_message", "General K12 teaching")
            if educational_context
            else "General K12 teaching"
        )

        # Extract mode from educational_context (thread-safe, no race conditions!)
        mode = educational_context.get("_mode", "causes") if educational_context else "causes"
        logger.debug("[MultiFlow] Building prompt for mode: %s", mode)

        # Build prompt based on mode
        if mode == "causes":
            return self._build_causes_prompt(center_topic, context_desc, count, batch_num, language)
        return self._build_effects_prompt(center_topic, context_desc, count, batch_num, language)

    def _build_causes_prompt(self, event: str, context_desc: str, count: int, batch_num: int, language: str) -> str:
        """Build prompt for causes (factors leading to the event)"""
        if language == "zh":
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

Requirements: Each cause should be concise and clear. More than 4 words is allowed,
but avoid long sentences. Use short phrases, not full sentences.
Output only the cause text, one per line, no numbering.

Generate {count} causes:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == "zh":
                prompt += (
                    f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度思考，避免与之前批次重复。"
                )
            else:
                prompt += (
                    f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity "
                    "from new dimensions and angles, avoid any repetition from previous batches."
                )

        return prompt

    def _build_effects_prompt(self, event: str, context_desc: str, count: int, batch_num: int, language: str) -> str:
        """Build prompt for effects (results and consequences of the event)"""
        if language == "zh":
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

Requirements: Each effect should be concise and clear. More than 4 words is allowed,
but avoid long sentences. Use short phrases, not full sentences.
Output only the effect text, one per line, no numbering.

Generate {count} effects:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == "zh":
                prompt += (
                    f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度思考，避免与之前批次重复。"
                )
            else:
                prompt += (
                    f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity "
                    "with new dimensions and angles of analysis, "
                    "avoid any repetition from previous batches."
                )

        return prompt

    def end_session(self, session_id: str, reason: str = "complete") -> None:
        """Clean up session including mode tracking"""
        super().end_session(session_id, reason)
        self.current_mode.pop(session_id, None)


MULTI_FLOW_PALETTE_CACHE: list = [None]


def get_multi_flow_palette_generator() -> MultiFlowPaletteGenerator:
    """Get singleton instance of Multi Flow Map palette generator"""
    if MULTI_FLOW_PALETTE_CACHE[0] is None:
        MULTI_FLOW_PALETTE_CACHE[0] = MultiFlowPaletteGenerator()
    return MULTI_FLOW_PALETTE_CACHE[0]
