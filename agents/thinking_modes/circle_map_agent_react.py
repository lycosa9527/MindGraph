"""
Circle Map Thinking Mode Agent (ReAct Pattern)
================================================

Guides K12 teachers through Socratic refinement of Circle Maps using ReAct pattern.
Inherits from BaseThinkingAgent and provides Circle Map-specific behavior.

Circle Map Purpose: Define a topic in context through observations

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator, List

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent
from agents.thinking_modes.circle_map_actions import CircleMapActionHandler
from prompts.thinking_modes.circle_map import get_prompt

logger = logging.getLogger(__name__)


class CircleMapState(Enum):
    """State machine for Circle Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    EDUCATIONAL_ANALYSIS = "EDUCATIONAL_ANALYSIS"
    ANALYSIS = "ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class CircleMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Circle Maps.
    
    Circle Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Educational Analysis: Analyze each observation's relevance
    3. Analysis: Socratic questioning about observations
    4. Refinement 1: N → 8 observations
    5. Refinement 2: 8 → 6 observations
    6. Final Refinement: 6 → 5 core observations
    """
    
    def __init__(self):
        """Initialize Circle Map agent"""
        super().__init__(diagram_type='circle_map')
        self.action_handler = CircleMapActionHandler(self)
    
    # ===== DIAGRAM-SPECIFIC: INTENT DETECTION =====
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """
        Detect user intent for Circle Map operations.
        
        Circle Map-specific actions:
        - change_center: Change the center topic being defined
        - update_node: Modify an observation
        - delete_node: Remove an observation
        - update_properties: Change node styling
        - add_nodes: Add new observations
        - discuss: Just talking, no diagram changes
        """
        if not message:
            return {'action': 'discuss'}
        
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        children = diagram_data.get('children', [])
        language = session.get('language', 'en')
        
        # Build node list for context
        nodes_list = '\n'.join([f"{i+1}. {node['text']}" for i, node in enumerate(children)])
        
        # LLM-based intent detection
        if language == 'zh':
            system_prompt = f"""你是意图识别专家。分析用户想对圆圈图做什么操作。

当前工作流阶段：{current_state}

返回JSON格式：
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "discuss",
  "target": "目标文本",
  "node_index": 节点序号（1-based），
  "properties": {{"fillColor": "#颜色代码", "bold": true/false, "italic": true/false}}
}}

操作说明：
- change_center: 改变中心主题
- update_node: 修改某个观察节点的文字
- delete_node: 删除某个观察节点
- update_properties: 修改节点样式（颜色、粗体、斜体等）
- add_nodes: 明确要求添加新的观察节点
- discuss: 只是讨论，不修改图表

⚠️ 在CONTEXT_GATHERING阶段，除非用户明确说"添加"、"生成"，否则返回"discuss"

颜色映射：红色→#F44336, 蓝色→#2196F3, 绿色→#4CAF50, 黄色→#FFEB3B, 橙色→#FF9800, 紫色→#9C27B0

只返回JSON，不要其他文字。"""
            
            user_prompt = f"""当前圆圈图：
中心主题：{center_text}
观察节点 ({len(children)}个)：
{nodes_list if nodes_list else '（暂无节点）'}

用户消息：{message}"""
        else:
            system_prompt = f"""You are an intent recognition expert. Analyze what the user wants to do with the Circle Map.

Current workflow stage: {current_state}

Return JSON format:
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "discuss",
  "target": "target text",
  "node_index": node number (1-based),
  "properties": {{"fillColor": "#color", "bold": true/false, "italic": true/false}}
}}

Action descriptions:
- change_center: Change the center topic being defined
- update_node: Modify an observation node's text
- delete_node: Remove an observation node
- update_properties: Change node styling (color, bold, italic, etc.)
- add_nodes: Explicitly add new observation nodes
- discuss: Just discussing, no diagram changes

⚠️ During CONTEXT_GATHERING, unless user explicitly says "add", "generate", return "discuss"

Color mapping: red→#F44336, blue→#2196F3, green→#4CAF50, yellow→#FFEB3B, orange→#FF9800, purple→#9C27B0

Return only JSON, no other text."""
            
            user_prompt = f"""Current Circle Map:
Center topic: {center_text}
Observation nodes ({len(children)} total):
{nodes_list if nodes_list else '(no nodes yet)'}

User message: {message}"""
        
        try:
            result_text = await self.llm.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=0.1,
                max_tokens=500
            )
            
            # Extract JSON
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            intent = json.loads(result_text)
            logger.info(f"[CircleMapThinkingAgent] Detected intent: {intent}")
            return intent
        
        except Exception as e:
            logger.error(f"[CircleMapThinkingAgent] Intent detection error: {e}")
            return {'action': 'discuss'}
    
    # ===== DIAGRAM-SPECIFIC: ACTION HANDLER =====
    
    async def _handle_action(
        self,
        session: Dict,
        intent: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle Circle Map-specific actions.
        Delegates to CircleMapActionHandler.
        """
        action = intent.get('action')
        
        if action == 'change_center':
            new_topic = intent.get('target', '').strip()
            if new_topic:
                diagram_data = session.get('diagram_data', {})
                old_topic = diagram_data.get('center', {}).get('text', '')
                async for event in self.action_handler.handle_change_center(session, new_topic, old_topic):
                    yield event
        
        elif action == 'update_node':
            node_index = intent.get('node_index')
            new_text = intent.get('target', '').strip()
            if node_index is not None and new_text:
                async for event in self.action_handler.handle_update_node(session, int(node_index) - 1, new_text):
                    yield event
        
        elif action == 'delete_node':
            node_index = intent.get('node_index')
            if node_index is not None:
                async for event in self.action_handler.handle_delete_node(session, int(node_index) - 1):
                    yield event
        
        elif action == 'update_properties':
            node_index = intent.get('node_index')
            properties = intent.get('properties', {})
            if node_index is not None and properties:
                async for event in self.action_handler.handle_update_properties(session, int(node_index) - 1, properties):
                    yield event
        
        elif action == 'add_nodes':
            async for event in self.action_handler.handle_add_nodes(session, message):
                yield event
        
        else:
            # Unknown action, fallback to discussion
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    # ===== DIAGRAM-SPECIFIC: PROMPTS =====
    
    def _get_state_prompt(self, session: Dict, state: str) -> str:
        """Get Circle Map-specific prompt for current state"""
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        nodes = diagram_data.get('children', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        # Map state to prompt name
        state_to_prompt = {
            'CONTEXT_GATHERING': 'CONTEXT_GATHERING',
            'EDUCATIONAL_ANALYSIS': 'EDUCATIONAL_ANALYSIS',
            'ANALYSIS': 'ANALYSIS',
            'REFINEMENT_1': 'REFINEMENT_1',
            'REFINEMENT_2': 'REFINEMENT_2',
            'FINAL_REFINEMENT': 'FINAL_REFINEMENT'
        }
        
        prompt_name = state_to_prompt.get(state, 'CONTEXT_GATHERING')
        prompt_template = get_prompt(prompt_name, language)
        
        # Format prompt with context
        try:
            return prompt_template.format(
                center_node=center_text,
                nodes=', '.join([node['text'] for node in nodes]),
                node_count=len(nodes),
                grade_level=context.get('grade_level', 'not specified'),
                objective=context.get('objective', 'not specified'),
                removals=max(0, len(nodes) - 8)
            )
        except KeyError as e:
            logger.warning(f"[CircleMapThinkingAgent] Missing format key: {e}")
            return prompt_template
    
    # ===== DIAGRAM-SPECIFIC: NODE GENERATION =====
    
    async def _generate_suggested_nodes(self, session: Dict) -> List[Dict]:
        """
        Generate Circle Map-specific node suggestions.
        
        Circle Maps focus on OBSERVATIONS about the topic in context.
        Suggestions should be observable, concrete aspects.
        """
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        if language == 'zh':
            prompt = f"""你是K12教育专家。为圆圈图主题生成5个观察点。

主题：{center_text}
教学背景：{context.get('raw_message', '通用K12教学')}

圆圈图的目的：定义一个主题——观察到什么？在什么背景下？

要求：
1. 每项应该是可观察的具体方面（2-6个字）
2. 适合K12学生理解
3. 从不同角度观察
4. 只输出节点文本，每行一个，不要编号

生成5个观察点："""
        else:
            prompt = f"""You are a K12 education expert. Generate 5 observation points for a Circle Map topic.

Topic: {center_text}
Educational Context: {context.get('raw_message', 'General K12 teaching')}

Circle Map Purpose: Define a topic — What do we observe? In what context?

Requirements:
1. Each should be an observable, concrete aspect (2-6 words)
2. Appropriate for K12 students
3. Observe from different angles
4. Output only node text, one per line, no numbering

Generate 5 observations:"""
        
        try:
            content = await self.llm.chat(
                prompt=prompt,
                model=self.model,
                system_message='You are a helpful K12 education assistant.',
                temperature=0.7,
                max_tokens=200
            )
            
            # Parse response
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            nodes = []
            for line in lines:
                text = line.lstrip('0123456789.-、）) ')
                if text:
                    nodes.append({'text': text, 'position': 'auto'})
            
            logger.info(f"[CircleMapThinkingAgent] Generated {len(nodes)} observation nodes")
            return nodes[:5]
        
        except Exception as e:
            logger.error(f"[CircleMapThinkingAgent] Node generation error: {e}")
            return []

