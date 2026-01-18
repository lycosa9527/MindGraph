"""
bridge map palette module.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging

from agents.node_palette.base_palette_generator import BasePaletteGenerator

"""
Bridge Map Palette Generator
=============================

Bridge Map specific node palette generator.

Generates analogy pair nodes for Bridge Maps with paired left/right format.
Similar to double bubble map's differences, but for analogies.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""



logger = logging.getLogger(__name__)


class BridgeMapPaletteGenerator(BasePaletteGenerator):
    """
    Bridge Map specific palette generator.

    Generates analogy pair nodes for Bridge Maps.
    Uses pipe-separated format: "left | right | dimension"
    similar to double bubble differences.
    """

    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with analogy pair parsing.

        Args:
            session_id: Session identifier
            center_topic: The relationship/dimension being explored
            educational_context: Educational context
            nodes_per_llm: Number of nodes per LLM
        """
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
            # Parse pipe-separated pairs for analogy nodes
            if chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                text = node.get('text', '')

                logger.debug("[BridgeMap] Processing node with text: '%s'", text)

                # Analogies MUST have pipe separator - skip if it doesn't
                if '|' not in text:
                    logger.warning("[BridgeMap] Skipping node without pipe separator: '%s'", text)
                    continue  # Skip this node

                # Parse pipe-separated format: "left | right | dimension" (dimension is optional)
                parts = text.split('|')  # Split on all pipes
                if len(parts) >= 2:
                    left_text = parts[0].strip()
                    right_text = parts[1].strip()
                    dimension = parts[2].strip() if len(parts) >= 3 else None

                    # Filter out invalid/unwanted nodes:
                    # 1. Empty or very short values (likely formatting artifacts)
                    if len(left_text) < 2 or len(right_text) < 2:
                        logger.debug("[BridgeMap] Skipping too short: '%s | %s'", left_text, right_text)
                        continue

                    # 2. Markdown table separators (e.g., "| ---" or "---")
                    if left_text.startswith('-') or right_text.startswith('-'):
                        logger.debug("[BridgeMap] Skipping markdown separator: '%s | %s'", left_text, right_text)
                        continue

                    # 3. Header-like patterns containing "as" repeated
                    if ('as' in left_text.lower() and 'as' in right_text.lower()):
                        logger.debug("[BridgeMap] Skipping header pattern: '%s | %s'", left_text, right_text)
                        continue

                    # Valid analogy pair - add left, right, and optional dimension fields
                    node['left'] = left_text
                    node['right'] = right_text
                    if dimension and len(dimension) > 0:
                        node['dimension'] = dimension
                    # Keep text as-is for backwards compatibility
                    node['text'] = text

                    dim_info = " | dimension='%s'" % dimension if dimension else ""
                    logger.debug("[BridgeMap] Parsed pair successfully: left='%s' | right='%s'%s", left_text, right_text, dim_info)
                    logger.debug("[BridgeMap] Node now has: %s", list(node.keys()))
                else:
                    # Malformed pipe-separated format (has | but couldn't parse properly)
                    logger.warning("[BridgeMap] Skipping malformed node: '%s'", text)
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
        Build Bridge Map prompt for analogy pairs.

        Uses the dimension field from diagram spec:
        - If dimension field is filled → User specified a relationship → Focus on that ONE relationship
        - If dimension field is empty → User wants variety → Generate DIVERSE relationships

        Args:
            center_topic: The dimension field value from bridge map spec
            educational_context: Educational context dict
            count: Number of analogy pairs to request
            batch_num: Current batch number

        Returns:
            Formatted prompt for Bridge Map analogy generation
        """
        # Detect language from content (Chinese topic = Chinese prompt)
        language = self._detect_language  # pylint: disable=protected-access(center_topic, educational_context)

        # Use same context extraction as auto-complete
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'

        # Check if user specified a dimension (simple empty check)
        is_specific_relationship = bool(center_topic and center_topic.strip())

        logger.debug("[BridgeMap-Prompt] Dimension field: '%s' | User specified: %s", center_topic, is_specific_relationship)

        # Build prompt based on language (derived from BRIDGE_MAP_GENERATION prompts)
        if language == 'zh':
            # Conditional instructions based on specificity
            if is_specific_relationship:
                # User filled in the dimension field - focus on that ONE relationship
                focus_instruction = f"""
⚠️ 重要：用户在桥形图的"关系维度"字段中指定了「{center_topic}」
- 所有{count}组类比必须遵循完全相同的关系维度
- 关系维度统一为：{center_topic}
- 只改变左项和右项的具体内容，关系保持一致

例如，如果关系是「首都到国家」，所有类比都应该是：
巴黎 | 法国 | 首都关系
柏林 | 德国 | 首都关系
东京 | 日本 | 首都关系
（所有类比都是首都→国家，不要混入其他关系）
"""
                topic_text = center_topic
            else:
                # User left dimension field empty - generate diverse relationships
                focus_instruction = """
💡 用户未指定关系维度（字段为空），请生成多样化的类比：
- 从多个不同的关系维度思考
- 每2-3组类比可以换一个新的关系维度
- 展示丰富的思维角度和关系类型

例如，可以包含多种关系：
巴黎 | 法国 | 首都关系
锤子 | 木匠 | 工具关系
雨 | 洪水 | 因果关系
轮子 | 汽车 | 组成关系
（混合多种不同的关系维度）
"""
                topic_text = "多种关系的类比"

            prompt = f"""为以下生成{count}组类比对：{topic_text}

教学背景：{context_desc}

你能够绘制桥形图，通过类比帮助理解抽象概念。
思维方式：类比、联想
1. 找出符合相同关系模式的事物对
2. 类比要清晰易懂，帮助学生理解
3. 使用简洁的名词或名词短语
4. 每组类比包含左项、右项和关系维度
{focus_instruction}

常见类比关系参考：
- 首都到国家：巴黎 | 法国 | 首都关系
- 作者到作品：莎士比亚 | 哈姆雷特 | 创作关系
- 功能到对象：飞 | 鸟 | 功能关系
- 部分到整体：轮子 | 汽车 | 组成关系
- 工具到工作者：锤子 | 木匠 | 工具关系
- 因到果：雨 | 洪水 | 因果关系

输出格式：每行一组类比，用 | 分隔，格式如下：
左项 | 右项 | 关系维度

要求：每个项要简洁明了（2-8个字），关系维度要简洁（2-6个字），每行一对，用竖线分隔，不要编号。

生成{count}组类比："""
        else:
            # Conditional instructions based on specificity
            if is_specific_relationship:
                # User filled in the dimension field - focus on that ONE relationship
                focus_instruction = f"""
⚠️ IMPORTANT: User specified a relationship in the bridge map's "dimension" field: "{center_topic}"
- ALL {count} analogies MUST follow the EXACT SAME relationship dimension
- Relationship dimension should be: {center_topic}
- Only vary the left and right items, keep the relationship consistent

For example, if the relationship is "Capital to Country", all analogies should be:
Paris | France | Capital Relationship
Berlin | Germany | Capital Relationship
Tokyo | Japan | Capital Relationship
(All analogies are capital→country, don't mix other relationships)
"""
                topic_text = center_topic
            else:
                # User left dimension field empty - generate diverse relationships
                focus_instruction = """
💡 User left the dimension field EMPTY, generate DIVERSE analogies:
- Think from multiple DIFFERENT relationship dimensions
- Switch to a new relationship dimension every 2-3 analogies
- Show rich perspectives and relationship types

For example, include multiple relationships:
Paris | France | Capital Relationship
Hammer | Carpenter | Tool Relationship
Rain | Flood | Causal Relationship
Wheel | Car | Component Relationship
(Mix multiple different relationship dimensions)
"""
                topic_text = "various relationships"

            prompt = f"""Generate {count} Bridge Map analogy pairs for: {topic_text}

Educational Context: {context_desc}

You can draw a bridge map to help understand abstract concepts through analogies.
Thinking approach: Analogy, Association
1. Find pairs of things that follow the same relationship pattern
2. Analogies should be clear and help students understand
3. Use concise nouns or noun phrases
4. Each analogy contains left item, right item, and relationship dimension
{focus_instruction}

Common analogy relationships reference:
- Capital to Country: Paris | France | Capital Relationship
- Author to Work: Shakespeare | Hamlet | Creation Relationship
- Function to Object: Fly | Bird | Function Relationship
- Part to Whole: Wheel | Car | Composition Relationship
- Tool to Worker: Hammer | Carpenter | Tool Relationship
- Cause to Effect: Rain | Flood | Causal Relationship

Output format: One analogy per line, separated by |, format:
left item | right item | relationship dimension

Requirements: Each item should be concise (2-8 words). Dimension should be concise (2-6 words). One pair per line, separated by pipe character, no numbering.

Generate {count} analogies:"""

        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的领域和角度寻找类比，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity from new domains and angles, avoid any repetition from previous batches."

        return prompt

# Global singleton  # pylint: disable=global-statement instance for Bridge Map
_bridge_map_palette_generator = None

def get_bridge_map_palette_generator() -> BridgeMapPaletteGenerator:
    """Get singleton instance of Bridge Map palette generator"""
    global _bridge_map_palette_generator  # pylint: disable=global-statement
    if _bridge_map_palette_generator is None:
        _bridge_map_palette_generator = BridgeMapPaletteGenerator()
    return _bridge_map_palette_generator

