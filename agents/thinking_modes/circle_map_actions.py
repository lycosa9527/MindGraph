"""
Circle Map Action Handlers
============================

Diagram-specific action handlers for Circle Map ThinkGuide.
Handles node updates, deletions, center changes, etc.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Dict, AsyncGenerator

logger = logging.getLogger(__name__)


class CircleMapActionHandler:
    """
    Handles all Circle Map-specific diagram modifications.
    Separated from main agent to keep files under 500 lines.
    """
    
    def __init__(self, agent):
        """
        Initialize handler with reference to parent agent.
        
        Args:
            agent: Parent CircleMapThinkingAgent instance
        """
        self.agent = agent
    
    async def handle_change_center(
        self,
        session: Dict,
        new_topic: str,
        old_topic: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle center topic change"""
        language = session.get('language', 'en')
        
        # Verbal acknowledgment
        if language == 'zh':
            ack_prompt = f"用户想要修改圆圈图中心主题从「{old_topic}」改为「{new_topic}」。用1句话确认。"
        else:
            ack_prompt = f"User wants to change center topic from \"{old_topic}\" to \"{new_topic}\". Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Update diagram
        session['diagram_data']['center']['text'] = new_topic
        
        yield {
            'event': 'diagram_update',
            'action': 'update_center',
            'updates': {'new_text': new_topic}
        }
        
        # Completion message
        if language == 'zh':
            done_prompt = f"成功更新中心主题为「{new_topic}」。用1句话确认并鼓励继续。"
        else:
            done_prompt = f"Successfully updated center to \"{new_topic}\". Confirm in 1 sentence and encourage."
        
        async for chunk in self.agent._stream_llm_response(done_prompt, session):
            yield chunk
    
    async def handle_update_node(
        self,
        session: Dict,
        node_index: int,
        new_text: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle node text update"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        
        if not (0 <= node_index < len(diagram_data['children'])):
            return
        
        target_node = diagram_data['children'][node_index]
        old_text = target_node.get('text', '')
        
        # Acknowledge
        if language == 'zh':
            ack_prompt = f"用户要将第{node_index+1}个节点从「{old_text}」改为「{new_text}」。用1句话确认。"
        else:
            ack_prompt = f"User wants to change node #{node_index+1} from \"{old_text}\" to \"{new_text}\". Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Update
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
        
        # Confirm
        if language == 'zh':
            done_prompt = f"成功更新节点为「{new_text}」。用1句话确认。"
        else:
            done_prompt = f"Successfully updated node to \"{new_text}\". Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(done_prompt, session):
            yield chunk
    
    async def handle_delete_node(
        self,
        session: Dict,
        node_index: int
    ) -> AsyncGenerator[Dict, None]:
        """Handle node deletion"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        
        if not (0 <= node_index < len(diagram_data['children'])):
            return
        
        target_node = diagram_data['children'][node_index]
        old_text = target_node.get('text', '')
        
        # Acknowledge
        if language == 'zh':
            ack_prompt = f"用户要删除第{node_index+1}个节点「{old_text}」。用1句话确认。"
        else:
            ack_prompt = f"User wants to delete node #{node_index+1}: \"{old_text}\". Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Delete
        diagram_data['children'] = [n for n in diagram_data['children'] if n['id'] != target_node['id']]
        
        yield {
            'event': 'diagram_update',
            'action': 'remove_nodes',
            'updates': {'node_ids': [target_node['id']]}
        }
        
        # Confirm
        if language == 'zh':
            done_prompt = f"成功删除节点「{old_text}」，现在有{len(diagram_data['children'])}个节点。用1句话确认。"
        else:
            done_prompt = f"Successfully deleted \"{old_text}\". Now {len(diagram_data['children'])} nodes remain. Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(done_prompt, session):
            yield chunk
    
    async def handle_update_properties(
        self,
        session: Dict,
        node_index: int,
        properties: Dict
    ) -> AsyncGenerator[Dict, None]:
        """Handle node property updates (color, style, etc.)"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        
        if not (0 <= node_index < len(diagram_data['children'])):
            return
        
        target_node = diagram_data['children'][node_index]
        node_text = target_node.get('text', '')
        
        # Build description
        prop_desc = []
        if 'fillColor' in properties:
            prop_desc.append('颜色' if language == 'zh' else 'color')
        if 'bold' in properties:
            prop_desc.append('粗体' if language == 'zh' else 'bold')
        if 'italic' in properties:
            prop_desc.append('斜体' if language == 'zh' else 'italic')
        
        props_str = '、'.join(prop_desc) if language == 'zh' else ', '.join(prop_desc)
        
        # Acknowledge
        if language == 'zh':
            ack_prompt = f"用户要修改第{node_index+1}个节点「{node_text}」的{props_str}。用1句话确认。"
        else:
            ack_prompt = f"User wants to update {props_str} of node #{node_index+1} \"{node_text}\". Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Update
        yield {
            'event': 'diagram_update',
            'action': 'update_properties',
            'updates': [{
                'node_id': target_node['id'],
                'properties': properties
            }]
        }
        
        # Confirm
        if language == 'zh':
            done_prompt = "成功更新节点样式。用1句话确认。"
        else:
            done_prompt = "Successfully updated node styles. Confirm in 1 sentence."
        
        async for chunk in self.agent._stream_llm_response(done_prompt, session):
            yield chunk
    
    async def handle_add_nodes(
        self,
        session: Dict,
        message: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle adding suggested nodes"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        center = diagram_data.get('center', {}).get('text', '')
        
        # Acknowledge
        if language == 'zh':
            ack_prompt = f"用户希望为「{center}」添加节点。用1句话说你会思考相关概念。"
        else:
            ack_prompt = f"User wants to add nodes for \"{center}\". Say in 1 sentence you'll think about relevant concepts."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Generate suggestions
        suggested_nodes = await self.agent._generate_suggested_nodes(session)
        
        if suggested_nodes:
            # List the nodes
            node_list = ', '.join([f"「{n['text']}」" for n in suggested_nodes]) if language == 'zh' else ', '.join([f"\"{n['text']}\"" for n in suggested_nodes])
            
            if language == 'zh':
                adding_prompt = f"我建议添加{len(suggested_nodes)}个节点：{node_list}。用1句话说明。"
            else:
                adding_prompt = f"I suggest {len(suggested_nodes)} nodes: {node_list}. Say in 1 sentence."
            
            async for chunk in self.agent._stream_llm_response(adding_prompt, session):
                yield chunk
            
            # Update diagram
            diagram_data.setdefault('children', []).extend(suggested_nodes)
            session['node_count'] = len(diagram_data['children'])
            
            yield {
                'event': 'diagram_update',
                'action': 'add_nodes',
                'updates': suggested_nodes
            }
            
            # Confirm
            if language == 'zh':
                done_prompt = f"成功添加{len(suggested_nodes)}个节点，现在共{session['node_count']}个。用1句话确认并鼓励。"
            else:
                done_prompt = f"Successfully added {len(suggested_nodes)} nodes. Now {session['node_count']} total. Confirm in 1 sentence."
            
            async for chunk in self.agent._stream_llm_response(done_prompt, session):
                yield chunk
    
    async def handle_open_node_palette(
        self,
        session: Dict
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle opening Node Palette for brainstorming more nodes.
        
        This is triggered when user asks:
        - "Show me node palette"
        - "给我节点选择板"
        - "Generate more ideas"
        - "Brainstorm more observations"
        """
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        center_topic = diagram_data.get('center', {}).get('text', 'Unknown Topic')
        current_node_count = len(diagram_data.get('children', []))
        
        # Acknowledge request
        if language == 'zh':
            ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」头脑风暴更多观察点。目前有{current_node_count}个节点。用1-2句话说你将使用多个AI模型生成创意想法。"
        else:
            ack_prompt = f"User wants to open Node Palette to brainstorm more observations for \"{center_topic}\". Currently {current_node_count} nodes. Say in 1-2 sentences you'll generate creative ideas using multiple AI models."
        
        async for chunk in self.agent._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Extract educational context from ThinkGuide session
        context = session.get('context', {})
        educational_context = {
            'grade_level': context.get('grade_level', '5th grade'),
            'subject': context.get('subject', 'General'),
            'objective': context.get('objective', ''),
            'raw_message': context.get('raw_message', ''),  # Original user context for more focused prompts
            'language': language  # Pass UI language to Node Palette
        }
        
        # Yield action event to trigger Node Palette on frontend
        yield {
            'event': 'action',
            'action': 'open_node_palette',
            'data': {
                'center_topic': center_topic,
                'current_node_count': current_node_count,
                'diagram_data': diagram_data,
                'session_id': session['session_id'],
                'educational_context': educational_context  # Pass ThinkGuide context for focused generation
            }
        }
        
        # Final message
        if language == 'zh':
            done_prompt = "节点选择板已准备就绪！从多个AI生成的节点中选择您喜欢的，然后点击「完成」按钮添加到圆圈图中。用1-2句话说明。"
        else:
            done_prompt = "Node Palette is ready! Select your favorite nodes from multiple AI-generated suggestions, then click \"Finish\" to add them to your Circle Map. Say in 1-2 sentences."
        
        async for chunk in self.agent._stream_llm_response(done_prompt, session):
            yield chunk

