"""
Voice Diagram Update Agent
Uses LangChain + Qwen Turbo to extract structured diagram update commands

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from services.llm_service import llm_service

logger = logging.getLogger('VOIC_AGENT')


class DiagramUpdateCommand(BaseModel):
    """Structured diagram update command"""
    action: str = Field(description="Action type: update_center, update_node, add_node, delete_node")
    target: Optional[str] = Field(None, description="Target text for update (e.g., new topic, new node text)")
    node_index: Optional[int] = Field(None, description="Node index (0-based) for update_node or delete_node")
    confidence: float = Field(description="Confidence score 0-1")


class VoiceDiagramAgent:
    """
    Simple LangChain agent that extracts structured diagram updates from voice commands.
    Uses Qwen Turbo for fast, reliable parsing.
    """
    
    def __init__(self):
        self.output_parser = PydanticOutputParser(pydantic_object=DiagramUpdateCommand)
        
    async def parse_voice_command(
        self,
        user_message: str,
        diagram_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse voice command and extract structured diagram update.
        
        Args:
            user_message: User's voice command (e.g., "把主题改成摩托车")
            diagram_context: Current diagram state (center, nodes, etc.)
        
        Returns:
            {
                'action': 'update_center' | 'update_node' | 'add_node' | 'delete_node' | 'none',
                'target': 'new text',
                'node_index': 0,  # if applicable
                'confidence': 0.95
            }
        """
        try:
            # Extract diagram info
            center_text = diagram_context.get('diagram_data', {}).get('center', {}).get('text', 'unknown')
            nodes = diagram_context.get('diagram_data', {}).get('children', [])
            diagram_type = diagram_context.get('diagram_type', 'unknown')
            
            # Build nodes description
            nodes_desc = self._format_nodes(nodes)
            
            # Build prompt
            prompt = f"""你是一个图表更新助手。用户正在使用语音更新{diagram_type}图表。

当前图表状态：
- 中心主题：{center_text}
- 节点数量：{len(nodes)}
{nodes_desc}

用户说："{user_message}"

请分析用户的意图，提取结构化的更新命令。

可能的操作：
- update_center: 用户想修改中心主题（例如："把主题改成X"、"改为X"）
- update_node: 用户想修改某个节点（例如："把第一个改成X"、"修改第二个节点为X"）
- add_node: 用户想添加新节点（例如："添加X"、"增加一个X"）
- delete_node: 用户想删除节点（例如："删除第一个"、"去掉第二个"）
- none: 不是更新操作（例如：问问题、闲聊）

请返回JSON格式：
{{
    "action": "操作类型",
    "target": "目标文本（如果有）",
    "node_index": 节点索引（如果有，从0开始）,
    "confidence": 置信度（0-1）
}}

例子：
用户："把主题改成摩托车"
返回：{{"action": "update_center", "target": "摩托车", "node_index": null, "confidence": 0.95}}

用户："把第一个改成汽车"
返回：{{"action": "update_node", "target": "汽车", "node_index": 0, "confidence": 0.9}}

用户："添加飞机"
返回：{{"action": "add_node", "target": "飞机", "node_index": null, "confidence": 0.85}}

用户："删除第三个"
返回：{{"action": "delete_node", "target": null, "node_index": 2, "confidence": 0.9}}

用户："这是什么图？"
返回：{{"action": "none", "target": null, "node_index": null, "confidence": 0.95}}

现在请分析上面用户的话，只返回JSON，不要其他内容。"""
            
            # Call Qwen Turbo via LLM service
            response = await llm_service.chat(
                prompt=prompt,
                model='qwen',  # Qwen Turbo
                temperature=0.1,  # Low for structured extraction
                max_tokens=200,
                timeout=5.0
            )
            
            logger.debug(f"Qwen response: {response}")
            
            # Parse JSON response
            result = self._parse_response(response)
            
            logger.info(f"Parsed command: action={result['action']}, target={result.get('target')}, confidence={result.get('confidence')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Voice command parsing error: {e}", exc_info=True)
            return {
                'action': 'none',
                'target': None,
                'node_index': None,
                'confidence': 0.0
            }
    
    def _format_nodes(self, nodes) -> str:
        """Format nodes for prompt"""
        if not nodes:
            return "- 当前没有节点"
        
        lines = []
        for i, node in enumerate(nodes[:10]):  # Limit to first 10
            if isinstance(node, str):
                text = node
            elif isinstance(node, dict):
                text = node.get('text', str(node))
            else:
                text = str(node)
            lines.append(f"  {i+1}. {text}")
        
        if len(nodes) > 10:
            lines.append(f"  ... 还有{len(nodes)-10}个节点")
        
        return "- 现有节点：\n" + "\n".join(lines)
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Qwen's JSON response"""
        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = response.strip()
            if cleaned.startswith('```'):
                # Remove ```json or ``` wrapper
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1]) if len(lines) > 2 else cleaned
            
            cleaned = cleaned.replace('```json', '').replace('```', '').strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Validate required fields
            action = data.get('action', 'none')
            target = data.get('target')
            node_index = data.get('node_index')
            confidence = data.get('confidence', 0.8)
            
            # Convert node_index to int if present
            if node_index is not None and not isinstance(node_index, int):
                try:
                    node_index = int(node_index)
                except:
                    node_index = None
            
            return {
                'action': action,
                'target': target,
                'node_index': node_index,
                'confidence': float(confidence)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Response was: {response}")
            return {
                'action': 'none',
                'target': None,
                'node_index': None,
                'confidence': 0.0
            }
        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            return {
                'action': 'none',
                'target': None,
                'node_index': None,
                'confidence': 0.0
            }


# Global instance
voice_diagram_agent = VoiceDiagramAgent()

