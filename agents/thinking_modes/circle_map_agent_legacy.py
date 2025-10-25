"""
Circle Map Thinking Mode Agent (LEGACY)
=========================================

⚠️ DEPRECATED: This file is kept for reference only.
Please use the new ReAct-based implementation instead:
→ agents/thinking_modes/circle_map_agent_react.py

The new implementation:
- Uses ReAct pattern (Reason → Act → Observe)
- Inherits from BaseThinkingAgent
- Split into smaller files (< 500 lines each)
- Enables diagram-specific behavior
- See docs/THINKGUIDE_REACT_ARCHITECTURE.md

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator, Optional

from config.settings import config
from services.llm_service import llm_service
from prompts.thinking_modes.circle_map import (
    CONTEXT_GATHERING_PROMPT_EN,
    CONTEXT_GATHERING_PROMPT_ZH,
    EDUCATIONAL_ANALYSIS_PROMPT_EN,
    EDUCATIONAL_ANALYSIS_PROMPT_ZH,
    ANALYSIS_PROMPT_EN,
    ANALYSIS_PROMPT_ZH,
    REFINEMENT_1_PROMPT_EN,
    REFINEMENT_1_PROMPT_ZH,
    REFINEMENT_2_PROMPT_EN,
    REFINEMENT_2_PROMPT_ZH,
    FINAL_REFINEMENT_PROMPT_EN,
    FINAL_REFINEMENT_PROMPT_ZH,
    EVALUATE_REASONING_PROMPT_EN,
    EVALUATE_REASONING_PROMPT_ZH,
    get_prompt
)

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


class CircleMapThinkingAgent:
    """
    ThinkGuide agent for Circle Maps.
    Uses Socratic method to guide critical thinking.
    """
    
    def __init__(self):
        """Initialize agent with LLM Service"""
        # Use centralized LLM Service
        self.llm = llm_service
        self.model = 'qwen-plus'  # Better reasoning than qwen-turbo
        
        # Session storage (in-memory for MVP)
        self.sessions: Dict[str, Dict] = {}
    
    def _detect_language(self, text: str) -> str:
        """Detect if text is primarily Chinese or English"""
        if not text:
            return 'en'
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return 'zh' if chinese_chars > len(text) * 0.3 else 'en'
    
    def _get_prompt(self, prompt_name: str, session: Dict, **kwargs) -> str:
        """Get language-appropriate prompt"""
        language = session.get('language', 'en')
        prompt_map = {
            'CONTEXT_GATHERING': (CONTEXT_GATHERING_PROMPT_EN, CONTEXT_GATHERING_PROMPT_ZH),
            'EDUCATIONAL_ANALYSIS': (EDUCATIONAL_ANALYSIS_PROMPT_EN, EDUCATIONAL_ANALYSIS_PROMPT_ZH),
            'ANALYSIS': (ANALYSIS_PROMPT_EN, ANALYSIS_PROMPT_ZH),
            'REFINEMENT_1': (REFINEMENT_1_PROMPT_EN, REFINEMENT_1_PROMPT_ZH),
            'REFINEMENT_2': (REFINEMENT_2_PROMPT_EN, REFINEMENT_2_PROMPT_ZH),
            'FINAL_REFINEMENT': (FINAL_REFINEMENT_PROMPT_EN, FINAL_REFINEMENT_PROMPT_ZH),
            'EVALUATE_REASONING': (EVALUATE_REASONING_PROMPT_EN, EVALUATE_REASONING_PROMPT_ZH),
        }
        prompts = prompt_map.get(prompt_name)
        if not prompts:
            return ""
        prompt = prompts[1] if language == 'zh' else prompts[0]
        return prompt.format(**kwargs)
    
    def _should_suggest_nodes(self, session: Dict, message: str) -> bool:
        """
        Detect if we should suggest diagram nodes.
        Returns True if:
        - User explicitly asks for suggestions/auto-complete
        - Diagram is sparse (< 3 nodes) AND we have gathered sufficient context
        
        NOTE: During CONTEXT_GATHERING, only add nodes if explicitly requested!
        """
        diagram_data = session.get('diagram_data', {})
        children = diagram_data.get('children', [])
        workflow_state = session.get('workflow_state', 'CONTEXT_GATHERING')
        
        # Check if user explicitly requests (always honor explicit requests)
        if message:
            message_lower = message.lower()
            keywords_en = ['auto', 'complete', 'suggest', 'add', 'help me fill', 'generate', 'more nodes']
            keywords_zh = ['自动', '完成', '建议', '添加', '帮我', '生成', '更多节点', '补充']
            
            if any(kw in message_lower for kw in keywords_en + keywords_zh):
                return True
        
        # Only auto-suggest for sparse diagrams AFTER context gathering
        # During CONTEXT_GATHERING, we should just ask questions, not force nodes
        if workflow_state != 'CONTEXT_GATHERING' and len(children) < 3:
            return True
        
        return False
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """
        Generate suggested nodes based on center topic and educational context.
        Uses LLM to create meaningful, pedagogically sound suggestions.
        """
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        if language == 'zh':
            prompt = f"""你是一位经验丰富的K12教育专家。请为以下圆圈图（Circle Map）主题生成5个合适的观察点或关联项。

主题：{center_text}

教学背景：
{context.get('raw_message', '通用K12教学')}

要求：
1. 每个项目应该简洁（2-6个字）
2. 适合K12学生理解
3. 具有教育意义
4. 涵盖不同角度或方面
5. 只输出节点文本，每行一个，不要编号

请生成5个节点："""
        else:
            prompt = f"""You are an experienced K12 education expert. Generate 5 appropriate observation points or related items for the following Circle Map topic.

Topic: {center_text}

Educational Context:
{context.get('raw_message', 'General K12 teaching')}

Requirements:
1. Each item should be concise (2-6 words)
2. Appropriate for K12 students
3. Educational value
4. Cover different aspects or angles
5. Output only node text, one per line, no numbering

Generate 5 nodes:"""
        
        try:
            content = await self.llm.chat(
                prompt=prompt,
                model=self.model,
                system_message='You are a helpful K12 education assistant.',
                temperature=0.7,
                max_tokens=200
            )
            
            # Parse response into node list
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            # Remove any numbering (1., 2., etc.)
            nodes = []
            for line in lines:
                # Remove common numbering patterns
                text = line.lstrip('0123456789.-、）) ')
                if text:
                    nodes.append({
                        'text': text,
                        'position': 'auto'
                    })
            
            logger.info(f"[ThinkGuide] Generated {len(nodes)} suggested nodes: {nodes}")
            return nodes[:5]  # Limit to 5 nodes
            
        except Exception as e:
            logger.error(f"[ThinkGuide] Error generating nodes: {e}")
            return []
    
    async def _detect_user_intent(self, session: Dict, message: str) -> Dict:
        """
        Use LLM to understand user intent and extract structured information.
        Returns a structured intent object.
        
        This is how LangChain agents work - using LLM for intent detection,
        not brittle keyword matching.
        """
        if not message:
            return {'action': 'discuss'}
        
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        children = diagram_data.get('children', [])
        language = session.get('language', 'en')
        
        # Build context about current diagram
        nodes_list = '\n'.join([f"{i+1}. {node['text']}" for i, node in enumerate(children)])
        
        workflow_state = session.get('workflow_state', 'CONTEXT_GATHERING')
        
        if language == 'zh':
            system_prompt = f"""你是一个意图识别专家。分析用户的消息，判断他们想要对圆圈图做什么操作。

当前工作流阶段：{workflow_state}
{'' if workflow_state == 'CONTEXT_GATHERING' else '（已收集到背景信息）'}

请以JSON格式返回：
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "discuss",
  "target": "具体目标（主题名称、节点文本或新属性值）",
  "node_index": 节点序号（仅当action为update_node、delete_node、update_properties或update_position时）,
  "properties": {{
    "fillColor": "颜色代码（如#FF5722）",
    "textColor": "文字颜色",
    "strokeColor": "边框颜色",
    "bold": true/false,
    "italic": true/false,
    "fontSize": 数字
  }},
  "position": {{
    "angle": 角度（0-360），
    "rotate": 旋转度数,
    "swap_with": 目标节点序号
  }}
}}

操作类型说明：
- change_center: 用户想改变圆圈图的中心主题
- update_node: 用户想修改某个具体的外围节点文字
- delete_node: 用户想删除某个节点
- update_properties: 用户想修改节点的视觉属性（颜色、字体粗细、斜体等）
- update_position: 用户想移动节点位置（旋转、换位等）
- add_nodes: 用户**明确要求**添加新节点或自动补充（如果只是初步沟通，应该选discuss）
- discuss: 只是讨论、提供信息、回答问题，不需要修改图表

⚠️ 重要：在CONTEXT_GATHERING阶段，除非用户明确说"添加节点"、"帮我生成"等，否则应该返回"discuss"

位置控制（仅用于update_position）：
- "angle": 角度值（0-360度，顺时针方向，0度在顶部）
- "rotate": 旋转度数（正数顺时针，负数逆时针）
- "swap_with": 交换目标节点序号

颜色识别：
- 红色/红 → #F44336
- 蓝色/蓝 → #2196F3
- 绿色/绿 → #4CAF50
- 黄色/黄 → #FFEB3B
- 橙色/橙 → #FF9800
- 紫色/紫 → #9C27B0
- 粉色/粉 → #E91E63

只返回JSON，不要其他文字。"""
            
            user_prompt = f"""当前圆圈图状态：
中心主题：{center_text}
外围节点（{len(children)}个）：
{nodes_list if nodes_list else '（暂无节点）'}

用户消息：{message}"""
        else:
            system_prompt = f"""You are an intent recognition expert. Analyze the user's message to determine what operation they want to perform on the Circle Map.

Current workflow stage: {workflow_state}
{'' if workflow_state == 'CONTEXT_GATHERING' else '(Context already gathered)'}

Return JSON format:
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "discuss",
  "target": "specific target (topic name, node text, or new property value)",
  "node_index": node number (only for update_node, delete_node, update_properties, or update_position),
  "properties": {{
    "fillColor": "color code (e.g. #FF5722)",
    "textColor": "text color",
    "strokeColor": "border color",
    "bold": true/false,
    "italic": true/false,
    "fontSize": number
  }},
  "position": {{
    "angle": angle value (0-360),
    "rotate": rotation amount,
    "swap_with": target node index
  }}
}}

Action types:
- change_center: User wants to change the center topic
- update_node: User wants to modify a specific outer node's text
- delete_node: User wants to delete a node
- update_properties: User wants to modify node visual properties (color, font weight, italic, etc.)
- update_position: User wants to move/rotate nodes or swap positions
- add_nodes: User **explicitly requests** to add nodes or auto-complete (if just chatting, use 'discuss')
- discuss: Just discussing, providing info, answering questions - no diagram changes needed

⚠️ Important: During CONTEXT_GATHERING, unless user explicitly says "add nodes", "generate", etc., return "discuss"

Position control (for update_position only):
- "angle": absolute angle (0-360 degrees, clockwise, 0 is top)
- "rotate": rotation amount (positive = clockwise, negative = counterclockwise)
- "swap_with": swap with target node index

Color recognition:
- red → #F44336
- blue → #2196F3
- green → #4CAF50
- yellow → #FFEB3B
- orange → #FF9800
- purple → #9C27B0
- pink → #E91E63

Return only JSON, no other text."""
            
            user_prompt = f"""Current Circle Map state:
Center topic: {center_text}
Outer nodes ({len(children)} total):
{nodes_list if nodes_list else '(no nodes yet)'}

User message: {message}"""
        
        try:
            # Use LLM Service to understand intent
            result_text = await self.llm.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=0.1,  # Low temperature for consistent intent detection
                max_tokens=500
            )
            
            # Extract JSON (handle markdown code blocks if present)
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            intent = json.loads(result_text)
            
            logger.info(f"[ThinkGuide] LLM detected intent: {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"[ThinkGuide] Error detecting intent: {e}")
            # Fallback to discuss mode
            return {'action': 'discuss'}
    
    async def _check_and_suggest_nodes(
        self,
        session: Dict,
        message: str,
        stage: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Universal helper to check and suggest nodes at ANY workflow stage.
        This makes ThinkGuide truly two-way at all times.
        
        Args:
            session: Current session data
            message: User's message
            stage: Current workflow stage (for logging)
        """
        # Log current diagram state for transparency
        diagram_data = session.get('diagram_data', {})
        current_nodes = len(diagram_data.get('children', []))
        center = diagram_data.get('center', {}).get('text', 'N/A')
        
        logger.info(f"[ThinkGuide-{stage}] Current diagram: '{center}' with {current_nodes} nodes")
        
        # 🆕 LLM-BASED INTENT DETECTION (not keyword matching!)
        if message:
            intent = await self._detect_user_intent(session, message)
            action = intent.get('action')
            
            # Handle different actions based on LLM's understanding
            if action == 'change_center':
                new_topic = intent.get('target', '').strip()
                if new_topic:
                    logger.info(f"[ThinkGuide-{stage}] LLM detected topic change: '{center}' → '{new_topic}'")
                    
                    # Generate verbal acknowledgment using LLM for natural language
                    language = session.get('language', 'en')
                    if language == 'zh':
                        acknowledgment_prompt = f"""用户想要修改圆圈图。

当前中心主题：{center}
新主题：{new_topic}

请用1-2句话确认你理解了用户的意图，然后说你会立即更新。要自然、简洁。"""
                    else:
                        acknowledgment_prompt = f"""User wants to modify the Circle Map.

Current center topic: {center}
New topic: {new_topic}

Confirm you understand the user's intent in 1-2 sentences, then say you'll update it. Be natural and concise."""
                    
                    # Stream the acknowledgment
                    async for chunk in self._stream_llm_response(acknowledgment_prompt, session):
                        yield chunk
                    
                    # Now update session diagram data
                    diagram_data['center']['text'] = new_topic
                    
                    # Send diagram update event
                    yield {
                        'event': 'diagram_update',
                        'action': 'update_center',
                        'updates': {
                            'new_text': new_topic
                        }
                    }
                    
                    # Provide completion confirmation using LLM
                    if language == 'zh':
                        completion_prompt = f"""我刚刚成功更新了圆圈图的中心主题为「{new_topic}」。

请用1-2句话：
1. 确认更新完成
2. 鼓励用户继续完善这个新主题的圆圈图

要简洁、积极、有教育意义。"""
                    else:
                        completion_prompt = f"""I just successfully updated the Circle Map's center topic to "{new_topic}".

In 1-2 sentences:
1. Confirm the update is complete
2. Encourage the user to continue refining this new topic

Be concise, positive, and educational."""
                    
                    async for chunk in self._stream_llm_response(completion_prompt, session):
                        yield chunk
                    
                    logger.info(f"[ThinkGuide-{stage}] Topic updated with verbal confirmation")
                    return
            
            elif action in ('update_node', 'delete_node', 'update_properties', 'update_position'):
                node_index = intent.get('node_index')
                if node_index is not None:
                    node_index = int(node_index) - 1  # Convert to 0-based
                    
                    if 0 <= node_index < len(diagram_data['children']):
                        target_node = diagram_data['children'][node_index]
                        logger.info(f"[ThinkGuide-{stage}] LLM detected {action} for node {node_index+1}: '{target_node.get('text')}'")
                        
                        if action == 'delete_node':
                            language = session.get('language', 'en')
                            old_text = target_node.get('text', '')
                            
                            # Verbal acknowledgment using LLM
                            if language == 'zh':
                                ack_prompt = f"用户要删除第{node_index+1}个节点「{old_text}」。用1句话确认你理解并会删除它。"
                            else:
                                ack_prompt = f"User wants to delete node #{node_index+1}: \"{old_text}\". Confirm in 1 sentence you understand and will remove it."
                            
                            async for chunk in self._stream_llm_response(ack_prompt, session):
                                yield chunk
                            
                            # Delete the node
                            diagram_data['children'] = [n for n in diagram_data['children'] if n['id'] != target_node['id']]
                            
                            yield {
                                'event': 'diagram_update',
                                'action': 'remove_nodes',
                                'updates': {
                                    'node_ids': [target_node['id']]
                                }
                            }
                            
                            # Completion confirmation using LLM
                            if language == 'zh':
                                done_prompt = f"成功删除了节点「{old_text}」，现在图中有{len(diagram_data['children'])}个节点。用1句话简洁确认。"
                            else:
                                done_prompt = f"Successfully deleted node \"{old_text}\". Now {len(diagram_data['children'])} nodes remain. Confirm briefly in 1 sentence."
                            
                            async for chunk in self._stream_llm_response(done_prompt, session):
                                yield chunk
                            
                            logger.info(f"[ThinkGuide-{stage}] Node deleted with confirmation")
                            return
                        
                        elif action == 'update_node':
                            new_text = intent.get('target', '').strip()
                            if new_text:
                                language = session.get('language', 'en')
                                old_text = target_node.get('text', '')
                                
                                # Verbal acknowledgment using LLM
                                if language == 'zh':
                                    ack_prompt = f"用户要将第{node_index+1}个节点从「{old_text}」改为「{new_text}」。用1句话确认并说会更新。"
                                else:
                                    ack_prompt = f"User wants to change node #{node_index+1} from \"{old_text}\" to \"{new_text}\". Confirm in 1 sentence and say you'll update it."
                                
                                async for chunk in self._stream_llm_response(ack_prompt, session):
                                    yield chunk
                                
                                # Update the node text
                                for node in diagram_data['children']:
                                    if node['id'] == target_node['id']:
                                        node['text'] = new_text
                                        break
                                
                                yield {
                                    'event': 'diagram_update',
                                    'action': 'update_nodes',
                                    'updates': [{
                                        'node_id': target_node['id'],
                                        'new_text': new_text
                                    }]
                                }
                                
                                # Completion confirmation using LLM
                                if language == 'zh':
                                    done_prompt = f"成功更新节点为「{new_text}」。用1句话简洁确认。"
                                else:
                                    done_prompt = f"Successfully updated node to \"{new_text}\". Confirm briefly in 1 sentence."
                                
                                async for chunk in self._stream_llm_response(done_prompt, session):
                                    yield chunk
                                
                                logger.info(f"[ThinkGuide-{stage}] Node updated with confirmation")
                                return
                        
                        elif action == 'update_properties':
                            properties = intent.get('properties', {})
                            if properties:
                                language = session.get('language', 'en')
                                node_text = target_node.get('text', '')
                                
                                # Build description of property changes
                                prop_desc = []
                                if 'fillColor' in properties:
                                    prop_desc.append('颜色' if language == 'zh' else 'color')
                                if 'bold' in properties:
                                    prop_desc.append('粗体' if language == 'zh' else 'bold')
                                if 'italic' in properties:
                                    prop_desc.append('斜体' if language == 'zh' else 'italic')
                                
                                props_str = '、'.join(prop_desc) if language == 'zh' else ', '.join(prop_desc)
                                
                                # Verbal acknowledgment using LLM
                                if language == 'zh':
                                    ack_prompt = f"用户要修改第{node_index+1}个节点「{node_text}」的{props_str}。用1句话确认并说会更新样式。"
                                else:
                                    ack_prompt = f"User wants to update {props_str} of node #{node_index+1} \"{node_text}\". Confirm in 1 sentence and say you'll update styles."
                                
                                async for chunk in self._stream_llm_response(ack_prompt, session):
                                    yield chunk
                                
                                logger.info(f"[ThinkGuide-{stage}] Updating properties: {properties}")
                                
                                yield {
                                    'event': 'diagram_update',
                                    'action': 'update_properties',
                                    'updates': [{
                                        'node_id': target_node['id'],
                                        'properties': properties
                                    }]
                                }
                                
                                # Completion confirmation using LLM
                                if language == 'zh':
                                    done_prompt = "成功更新节点样式。用1句话简洁确认。"
                                else:
                                    done_prompt = "Successfully updated node styles. Confirm briefly in 1 sentence."
                                
                                async for chunk in self._stream_llm_response(done_prompt, session):
                                    yield chunk
                                
                                logger.info(f"[ThinkGuide-{stage}] Properties updated with confirmation")
                                return
                        
                        elif action == 'update_position':
                            position = intent.get('position', {})
                            if position:
                                language = session.get('language', 'en')
                                node_text = target_node.get('text', '')
                                
                                # Handle swap operation
                                if 'swap_with' in position:
                                    swap_index = int(position['swap_with']) - 1  # Convert to 0-based
                                    if 0 <= swap_index < len(diagram_data['children']) and swap_index != node_index:
                                        swap_node = diagram_data['children'][swap_index]
                                        swap_text = swap_node.get('text', '')
                                        
                                        # Verbal acknowledgment using LLM
                                        if language == 'zh':
                                            ack_prompt = f"用户要交换第{node_index+1}个节点「{node_text}」和第{swap_index+1}个节点「{swap_text}」的位置。用1句话确认。"
                                        else:
                                            ack_prompt = f"User wants to swap positions of node #{node_index+1} \"{node_text}\" and node #{swap_index+1} \"{swap_text}\". Confirm in 1 sentence."
                                        
                                        async for chunk in self._stream_llm_response(ack_prompt, session):
                                            yield chunk
                                        
                                        yield {
                                            'event': 'diagram_update',
                                            'action': 'swap_positions',
                                            'updates': {
                                                'node1_id': target_node['id'],
                                                'node2_id': swap_node['id']
                                            }
                                        }
                                        
                                        # Completion confirmation using LLM
                                        if language == 'zh':
                                            done_prompt = "成功交换两个节点的位置。用1句话确认。"
                                        else:
                                            done_prompt = "Successfully swapped node positions. Confirm in 1 sentence."
                                        
                                        async for chunk in self._stream_llm_response(done_prompt, session):
                                            yield chunk
                                        
                                        logger.info(f"[ThinkGuide-{stage}] Swapped positions with confirmation")
                                        return
                                
                                # Handle angle/rotation operations
                                logger.info(f"[ThinkGuide-{stage}] Updating position: {position}")
                                
                                # Verbal acknowledgment using LLM
                                if language == 'zh':
                                    ack_prompt = f"用户要调整第{node_index+1}个节点「{node_text}」的位置。用1句话确认。"
                                else:
                                    ack_prompt = f"User wants to adjust position of node #{node_index+1} \"{node_text}\". Confirm in 1 sentence."
                                
                                async for chunk in self._stream_llm_response(ack_prompt, session):
                                    yield chunk
                                
                                yield {
                                    'event': 'diagram_update',
                                    'action': 'update_position',
                                    'updates': [{
                                        'node_id': target_node['id'],
                                        'node_index': node_index,
                                        'position': position
                                    }]
                                }
                                
                                # Completion confirmation using LLM
                                if language == 'zh':
                                    done_prompt = "成功调整节点位置。用1句话确认。"
                                else:
                                    done_prompt = "Successfully adjusted node position. Confirm in 1 sentence."
                                
                                async for chunk in self._stream_llm_response(done_prompt, session):
                                    yield chunk
                                
                                logger.info(f"[ThinkGuide-{stage}] Position updated with confirmation")
                                return
            
            elif action == 'discuss':
                # User just wants to discuss, don't modify diagram
                logger.info(f"[ThinkGuide-{stage}] LLM detected discussion-only intent, no diagram changes")
                return
        
        # Check if we should suggest nodes (bulk operation)
        if self._should_suggest_nodes(session, message):
            logger.info(f"[ThinkGuide-{stage}] Triggering node generation (sparse diagram or user request)")
            
            language = session.get('language', 'en')
            center = diagram_data.get('center', {}).get('text', '')
            
            # Verbal acknowledgment using LLM
            if language == 'zh':
                ack_prompt = f"用户希望为主题「{center}」添加节点。用1-2句话说你会思考相关概念并添加。"
            else:
                ack_prompt = f"User wants to add nodes for topic \"{center}\". Say in 1-2 sentences you'll think about relevant concepts and add them."
            
            async for chunk in self._stream_llm_response(ack_prompt, session):
                yield chunk
            
            suggested_nodes = await self._generate_suggested_nodes(session)
            
            if suggested_nodes:
                logger.info(f"[ThinkGuide-{stage}] Sending {len(suggested_nodes)} node suggestions to frontend")
                
                # List the nodes being added
                node_list = ', '.join([f"「{n['text']}」" for n in suggested_nodes]) if language == 'zh' else ', '.join([f"\"{n['text']}\"" for n in suggested_nodes])
                
                if language == 'zh':
                    adding_prompt = f"我建议添加这{len(suggested_nodes)}个节点：{node_list}。用1句话说明并说会添加到图中。"
                else:
                    adding_prompt = f"I suggest these {len(suggested_nodes)} nodes: {node_list}. Say in 1 sentence you'll add them to the diagram."
                
                async for chunk in self._stream_llm_response(adding_prompt, session):
                    yield chunk
                
                # Update session diagram data optimistically
                # (Frontend will send back actual state on next message)
                diagram_data.setdefault('children', []).extend(suggested_nodes)
                session['node_count'] = len(diagram_data['children'])
                
                yield {
                    'event': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': suggested_nodes
                }
                
                # Completion confirmation using LLM
                if language == 'zh':
                    done_prompt = f"成功添加{len(suggested_nodes)}个节点，现在共{session['node_count']}个。用1-2句话确认并鼓励继续完善圆圈图。"
                else:
                    done_prompt = f"Successfully added {len(suggested_nodes)} nodes. Now {session['node_count']} total. Confirm in 1-2 sentences and encourage refining the Circle Map."
                
                async for chunk in self._stream_llm_response(done_prompt, session):
                    yield chunk
                
                logger.info(f"[ThinkGuide-{stage}] Diagram updated with confirmation: {current_nodes} → {session['node_count']} nodes")
    
    async def process_step(
        self,
        message: str,
        session_id: str,
        diagram_data: Dict,
        current_state: str,
        user_id: str = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Main entry point - processes one step of the workflow.
        Yields SSE events.
        """
        
        # Get or create session
        if session_id not in self.sessions:
            # Detect language from diagram data
            center_text = diagram_data.get('center', {}).get('text', '')
            children_count = len(diagram_data.get('children', []))
            detected_language = self._detect_language(center_text)
            
            logger.info(f"[ThinkGuide] Creating session with diagram - Center: '{center_text}' | Children: {children_count}")
            
            self.sessions[session_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'state': CircleMapState.CONTEXT_GATHERING,
                'diagram_data': diagram_data,
                'language': detected_language,
                'history': [],
                'context': {},
                'node_count': children_count,
                'node_learning_material': {}  # For hover tooltips!
            }
            logger.info(f"[ThinkGuide] New session: {session_id} | Language: {detected_language}")
        
        session = self.sessions[session_id]
        
        # Update diagram data if provided
        if diagram_data:
            session['diagram_data'] = diagram_data
        
        # Route to appropriate handler based on state
        try:
            state = CircleMapState(current_state)
        except ValueError:
            logger.error(f"[ThinkGuide] Invalid state: {current_state}")
            yield {
                'event': 'error',
                'message': f'Invalid state: {current_state}'
            }
            return
        
        logger.info(f"[ThinkGuide] Processing state: {state.value} | Session: {session_id}")
        
        # Route to state handler
        if state == CircleMapState.CONTEXT_GATHERING:
            async for chunk in self._handle_context_gathering(session, message):
                yield chunk
        
        elif state == CircleMapState.EDUCATIONAL_ANALYSIS:
            async for chunk in self._handle_educational_analysis(session, message):
                yield chunk
        
        elif state == CircleMapState.ANALYSIS:
            async for chunk in self._handle_analysis(session, message):
                yield chunk
        
        elif state == CircleMapState.REFINEMENT_1:
            async for chunk in self._handle_refinement_1(session, message):
                yield chunk
        
        elif state == CircleMapState.REFINEMENT_2:
            async for chunk in self._handle_refinement_2(session, message):
                yield chunk
        
        elif state == CircleMapState.FINAL_REFINEMENT:
            async for chunk in self._handle_final_refinement(session, message):
                yield chunk
        
        else:
            yield {
                'event': 'error',
                'message': f'Unknown state: {state}'
            }
    
    async def _handle_context_gathering(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 1: Gather educational context"""
        
        if not message:
            # First time - ask for context
            # ❌ NEVER auto-generate nodes on initialization!
            # Only ask questions and wait for user input
            prompt = self._get_prompt(
                'CONTEXT_GATHERING',
                session,
                center_node=session['diagram_data']['center']['text']
            )
            
            async for chunk in self._stream_llm_response(prompt, session):
                yield chunk
            
            # No diagram modifications on init - wait for user's first message!
        
        else:
            # User provided context - store it directly
            session['history'].append({
                'role': 'user',
                'content': message,
                'state': 'CONTEXT_GATHERING'
            })
            
            # Store the raw context message
            # The LLM prompts will use this context naturally in their templates
            session['context'] = {
                'raw_message': message,
                # For template compatibility, include message as primary field
                'grade_level': message,
                'objective': message,
                'lesson_context': message,
                'subject': message
            }
            
            logger.info(f"[ThinkGuide] Stored context: {message[:100]}...")
            
            # 🆕 Check if user wants to modify diagram BEFORE transitioning
            # This is critical - the message gets lost after state transition!
            async for chunk in self._check_and_suggest_nodes(session, message, 'CONTEXT_GATHERING'):
                yield chunk
            
            # Transition to EDUCATIONAL_ANALYSIS
            session['state'] = CircleMapState.EDUCATIONAL_ANALYSIS
            
            yield {
                'event': 'state_transition',
                'new_state': 'EDUCATIONAL_ANALYSIS',
                'progress': 25
            }
            
            # Automatically start educational analysis
            async for chunk in self._handle_educational_analysis(session, ''):
                yield chunk
    
    async def _handle_educational_analysis(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 2: Provide educational content about each node"""
        
        # 🆕 TWO-WAY: Check if user wants to modify diagram at this stage
        async for chunk in self._check_and_suggest_nodes(session, message, 'EDUCATIONAL_ANALYSIS'):
            yield chunk
        
        nodes = session['diagram_data']['children']
        context = session['context']
        
        # Build educational analysis prompt
        prompt = self._get_prompt(
            'EDUCATIONAL_ANALYSIS',
            session,
            center_node=session['diagram_data']['center']['text'],
            nodes='\n'.join([f"- {node['text']}" for node in nodes]),
            node_count=len(nodes),
            grade_level=context.get('grade_level', 'not specified'),
            objective=context.get('objective', 'not specified')
        )
        
        # Stream educational content
        full_response = ""
        async for chunk in self._stream_llm_response(prompt, session):
            if chunk.get('event') == 'message_chunk':
                full_response += chunk.get('content', '')
            yield chunk
        
        # Store learning material per node (simplified for MVP)
        # In production, parse response to extract per-node content
        for node in nodes:
            session['node_learning_material'][node.get('id', node.get('text'))] = {
                'node_name': node['text'],
                'full_analysis': full_response
            }
        
        # Transition to ANALYSIS (Socratic questions)
        session['state'] = CircleMapState.ANALYSIS
        
        yield {
            'event': 'state_transition',
            'new_state': 'ANALYSIS',
            'progress': 40
        }
        
        # Automatically start Socratic analysis
        async for chunk in self._handle_analysis(session, ''):
            yield chunk
    
    async def _handle_analysis(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 3: Socratic questioning about nodes"""
        
        # 🆕 TWO-WAY: Check if user wants to modify diagram at this stage
        async for chunk in self._check_and_suggest_nodes(session, message, 'ANALYSIS'):
            yield chunk
        
        nodes = session['diagram_data']['children']
        context = session['context']
        
        prompt = self._get_prompt(
            'ANALYSIS',
            session,
            center_node=session['diagram_data']['center']['text'],
            nodes=', '.join([node['text'] for node in nodes]),
            node_count=len(nodes),
            grade_level=context.get('grade_level', 'not specified'),
            objective=context.get('objective', 'not specified')
        )
        
        async for chunk in self._stream_llm_response(prompt, session):
            yield chunk
        
        # Transition to REFINEMENT_1
        session['state'] = CircleMapState.REFINEMENT_1
        
        yield {
            'event': 'state_transition',
            'new_state': 'REFINEMENT_1',
            'progress': 60
        }
        
        # Ask refinement question
        refinement_prompt = self._get_prompt(
            'REFINEMENT_1',
            session,
            node_count=len(nodes),
            grade_level=context.get('grade_level', ''),
            objective=context.get('objective', ''),
            removals=len(nodes) - 8
        )
        
        async for chunk in self._stream_llm_response(refinement_prompt, session):
            yield chunk
    
    async def _handle_refinement_1(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 4: First refinement (N → 8)"""
        
        # 🆕 TWO-WAY: Check if user wants to modify diagram at this stage
        async for chunk in self._check_and_suggest_nodes(session, message, 'REFINEMENT_1'):
            yield chunk
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'REFINEMENT_1'
        })
        
        # Evaluate reasoning
        evaluation_prompt = self._get_prompt(
            'EVALUATE_REASONING',
            session,
            removed_nodes='extracted from message',
            user_reasoning=message,
            center_node=session['diagram_data']['center']['text'],
            objective=session['context'].get('objective', '')
        )
        
        async for chunk in self._stream_llm_response(evaluation_prompt, session):
            yield chunk
        
        # Update node count
        session['node_count'] = 8
        
        # Transition to REFINEMENT_2
        session['state'] = CircleMapState.REFINEMENT_2
        
        yield {
            'event': 'state_transition',
            'new_state': 'REFINEMENT_2',
            'progress': 75
        }
        
        # Ask next refinement
        refinement_prompt = self._get_prompt(
            'REFINEMENT_2',
            session,
            grade_level=session['context'].get('grade_level', '')
        )
        
        async for chunk in self._stream_llm_response(refinement_prompt, session):
            yield chunk
    
    async def _handle_refinement_2(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 5: Second refinement (8 → 6)"""
        
        # 🆕 TWO-WAY: Check if user wants to modify diagram at this stage
        async for chunk in self._check_and_suggest_nodes(session, message, 'REFINEMENT_2'):
            yield chunk
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'REFINEMENT_2'
        })
        
        # Evaluate reasoning
        evaluation_prompt = self._get_prompt(
            'EVALUATE_REASONING',
            session,
            removed_nodes='extracted from message',
            user_reasoning=message,
            center_node=session['diagram_data']['center']['text'],
            objective=session['context'].get('objective', '')
        )
        
        async for chunk in self._stream_llm_response(evaluation_prompt, session):
            yield chunk
        
        session['node_count'] = 6
        
        # Transition to FINAL_REFINEMENT
        session['state'] = CircleMapState.FINAL_REFINEMENT
        
        yield {
            'event': 'state_transition',
            'new_state': 'FINAL_REFINEMENT',
            'progress': 90
        }
        
        # Ask final refinement
        final_prompt = self._get_prompt(
            'FINAL_REFINEMENT',
            session,
            center_node=session['diagram_data']['center']['text']
        )
        
        async for chunk in self._stream_llm_response(final_prompt, session):
            yield chunk
    
    async def _handle_final_refinement(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Step 6: Final refinement (6 → 5)"""
        
        # 🆕 TWO-WAY: Check if user wants to modify diagram at this stage
        async for chunk in self._check_and_suggest_nodes(session, message, 'FINAL_REFINEMENT'):
            yield chunk
        
        session['history'].append({
            'role': 'user',
            'content': message,
            'state': 'FINAL_REFINEMENT'
        })
        
        # Final evaluation and completion
        completion_prompt = f"""
The teacher's final decision: {message}

Acknowledge their deep thinking and provide a brief summary:
1. The 5 core nodes they've identified
2. The thinking process they demonstrated
3. How this refined map serves their educational objective

End with encouragement about their critical thinking journey.
"""
        
        async for chunk in self._stream_llm_response(completion_prompt, session):
            yield chunk
        
        # Mark complete
        session['state'] = CircleMapState.COMPLETE
        
        yield {
            'event': 'state_transition',
            'new_state': 'COMPLETE',
            'progress': 100
        }
        
        yield {
            'event': 'complete',
            'summary': {
                'final_node_count': 5,
                'history': session['history']
            }
        }
    
    async def _stream_static_message(
        self,
        message: str,
        session: Dict
    ) -> AsyncGenerator[Dict, None]:
        """
        Stream a static message as chunks (no LLM call).
        Used for confirmations and system messages.
        """
        # Simulate streaming by splitting into words
        words = message.split(' ')
        full_content = ""
        
        for i, word in enumerate(words):
            chunk_text = word if i == 0 else f" {word}"
            full_content += chunk_text
            
            yield {
                'event': 'message_chunk',
                'content': chunk_text
            }
            
            # Small delay for natural typing effect
            import asyncio
            await asyncio.sleep(0.02)
        
        # Store in history
        session['history'].append({
            'role': 'assistant',
            'content': full_content,
            'state': session['state'].value if hasattr(session.get('state'), 'value') else 'UNKNOWN'
        })
        
        yield {
            'event': 'message_complete',
            'full_content': full_content
        }
    
    async def _stream_llm_response(
        self,
        prompt: str,
        session: Dict
    ) -> AsyncGenerator[Dict, None]:
        """Helper: Stream LLM response as SSE chunks (for actual prompts)"""
        
        try:
            full_content = ""
            
            # Prepare messages with system instruction for concise, professional responses
            language = session.get('language', 'en')
            if language == 'zh':
                system_msg = """你是一位专业的思维教学专家（Teaching Thinking Professional）。

你的角色：
- 帮助教师通过苏格拉底式提问深化思考
- 引导教师发现概念的本质和优先级
- 培养批判性思维和教学设计能力

你的风格：
- 简洁、清晰、专业
- 不使用表情符号
- 直接、有针对性
- 提问而非说教"""
            else:
                system_msg = """You are a Teaching Thinking Professional.

Your role:
- Help teachers deepen thinking through Socratic questioning
- Guide teachers to discover essence and priorities of concepts
- Develop critical thinking and instructional design skills

Your style:
- Concise, clear, professional
- No emojis
- Direct and targeted
- Ask, don't lecture"""
            
            # Stream from LLM Service
            async for chunk in self.llm.chat_stream(
                prompt=prompt,
                model=self.model,
                system_message=system_msg,
                temperature=0.7
            ):
                full_content += chunk
                
                yield {
                    'event': 'message_chunk',
                    'content': chunk
                }
            
            # Store in history
            session['history'].append({
                'role': 'assistant',
                'content': full_content,
                'state': session['state'].value
            })
            
            yield {
                'event': 'message_complete',
                'full_content': full_content
            }
        
        except Exception as e:
            logger.error(f"[ThinkGuide] LLM streaming error: {e}", exc_info=True)
            yield {
                'event': 'error',
                'message': str(e)
            }
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID (for tooltip endpoint)"""
        return self.sessions.get(session_id)


