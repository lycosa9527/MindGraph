"""
Double Bubble Map Palette Generator
====================================

Generates nodes for Double Bubble Map with TWO modes:
1. Similarities: individual shared attributes
2. Differences: paired contrasting attributes

Author: lycosa9527
Made by: MindSpring Team
"""

import re
import json
from typing import Optional, Dict, Any, AsyncGenerator

from agents.thinking_modes.node_palette.base_palette_generator import BasePaletteGenerator


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
    
    async def generate_batch(
        self,
        session_id: str,
        center_topic: str,  # Will be "Topic1 vs Topic2"
        educational_context: Optional[Dict[str, Any]] = None,
        nodes_per_llm: int = 15,
        mode: str = 'similarities'  # NEW: 'similarities' or 'differences'
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate batch with mode support.
        
        Args:
            mode: 'similarities' for shared attributes, 'differences' for pairs
        """
        # Store mode for this session
        self.current_mode[session_id] = mode
        
        # Call parent's generate_batch (handles LLM streaming)
        async for chunk in super().generate_batch(
            session_id=session_id,
            center_topic=center_topic,
            educational_context=educational_context,
            nodes_per_llm=nodes_per_llm
        ):
            # For differences mode, parse JSON and add left/right fields
            if mode == 'differences' and chunk.get('event') == 'node_generated':
                node = chunk.get('node', {})
                text = node.get('text', '')
                
                # Try to parse as JSON
                try:
                    # Check if text looks like JSON
                    if text.strip().startswith('{') and text.strip().endswith('}'):
                        pair_data = json.loads(text)
                        # Add left and right fields to node
                        node['left'] = pair_data.get('left', '')
                        node['right'] = pair_data.get('right', '')
                        # Keep text for backwards compatibility but prefer left/right
                        if not node.get('text') or node['text'] == text:
                            node['text'] = f"{node['left']} | {node['right']}"
                except json.JSONDecodeError:
                    # If parsing fails, treat as regular text
                    pass
            
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
        left_topic, right_topic = self._parse_topics(center_topic)
        
        # Detect language
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', center_topic))
        language = 'zh' if has_chinese else 'en'
        
        # Get educational context
        context_desc = educational_context.get('raw_message', 'General K12 teaching') if educational_context else 'General K12 teaching'
        
        # Get current mode (default to similarities if not set)
        mode = self.current_mode.get('default', 'similarities')
        
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

你能够生成双气泡图的相似属性，找出两个主题的共同点。
思维方式：找出两者都具备的特征。
1. 使用形容词或名词短语
2. 找出两者共享的特征
3. 从多个维度思考（外观、功能、习性等）
4. 特征词要简洁明了

要求：每个相似点要简洁明了，只输出共同属性文本，每行一个，不要编号。

生成{count}个相似点："""
        else:
            prompt = f"""Generate {count} shared attributes (similarities) for: {left_topic} and {right_topic}

Educational Context: {context_desc}

You can generate Double Bubble Map similarities by finding common attributes.
Thinking approach: Identify characteristics that BOTH topics share.
1. Use adjectives or noun phrases
2. Find shared features between both topics
3. Think from multiple dimensions (appearance, function, behavior, etc.)
4. Keep attributes concise and clear

Requirements: Each similarity should be concise. Output only the attribute text, one per line, no numbering.

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

你能够生成双气泡图的差异对，找出两个主题的对比特征。
思维方式：找出两者的不同点，形成对比。
1. 每组差异包含两个对比属性
2. 左边属性描述{left_topic}的独特特征
3. 右边属性描述{right_topic}的独特特征
4. 两个属性形成对比关系

输出格式：每行一个JSON对象
{{"left": "{left_topic}的属性", "right": "{right_topic}的对比属性"}}

要求：每个差异对要形成清晰的对比，输出纯JSON，每行一个对象，不要编号。

生成{count}个差异对："""
        else:
            prompt = f"""Generate {count} contrasting attribute pairs (difference pairs) for: {left_topic} vs {right_topic}

Educational Context: {context_desc}

You can generate Double Bubble Map difference pairs by finding contrasting features.
Thinking approach: Identify unique characteristics that differentiate the two topics.
1. Each pair contains two contrasting attributes
2. Left attribute describes a unique feature of {left_topic}
3. Right attribute describes a unique feature of {right_topic}
4. Attributes should form a clear contrast

Output format: One JSON object per line
{{"left": "attribute of {left_topic}", "right": "contrasting attribute of {right_topic}"}}

Requirements: Each pair should form a clear contrast. Output pure JSON, one object per line, no numbering.

Generate {count} difference pairs:"""
        
        # Add diversity note for later batches
        if batch_num > 1:
            if language == 'zh':
                prompt += f"\n\n注意：这是第{batch_num}批。确保最大程度的多样性，从新的维度和角度对比，避免与之前批次重复。"
            else:
                prompt += f"\n\nNote: This is batch {batch_num}. Ensure MAXIMUM diversity with new dimensions and angles of contrast, avoid any repetition from previous batches."
        
        return prompt
    
    def _get_system_message(self, educational_context: Optional[Dict[str, Any]]) -> str:
        """Get system message for Double Bubble Map node generation"""
        has_chinese = False
        if educational_context and educational_context.get('raw_message'):
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', educational_context['raw_message']))
        
        return '你是一个有帮助的K12教育助手。' if has_chinese else 'You are a helpful K12 education assistant.'
    
    def end_session(self, session_id: str, reason: str = "complete"):
        """Clean up session including mode tracking"""
        super().end_session(session_id, reason)
        self.current_mode.pop(session_id, None)


# Global singleton instance for Double Bubble Map
_double_bubble_palette_generator = None

def get_double_bubble_palette_generator() -> DoubleBubblePaletteGenerator:
    """Get singleton instance of Double Bubble Map palette generator"""
    global _double_bubble_palette_generator
    if _double_bubble_palette_generator is None:
        _double_bubble_palette_generator = DoubleBubblePaletteGenerator()
    return _double_bubble_palette_generator

