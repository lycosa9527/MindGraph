"""
Voice Diagram Agent V2 - Complete Implementation
Uses LangChain + Qwen Turbo to extract structured commands

Supports:
- Diagram updates (all node types)
- UI actions (panels, selection, help)
- Content-based node search
- Multi-step actions
- Context-aware decisions

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher

from services.llm_service import llm_service

logger = logging.getLogger('VOIC_AGENT')


# Diagram metadata for context-aware processing
DIAGRAM_METADATA = {
    'circle_map': {
        'purpose': '定义概念，探索观察',
        'center_name': '主题/概念',
        'node_name': '观察/背景',
        'array_name': 'context',
        'node_id_prefix': 'context'
    },
    'bubble_map': {
        'purpose': '描述特征和属性',
        'center_name': '对象',
        'node_name': '形容词/特点',
        'array_name': 'attributes',
        'node_id_prefix': 'attribute'
    },
    'double_bubble_map': {
        'purpose': '比较两个事物',
        'center_name': '两个对象',
        'node_name': '相似点/不同点',
        'arrays': {
            'similarities': {'name': '相似点', 'prefix': 'similarity'},
            'left_differences': {'name': '左侧不同点', 'prefix': 'left_diff'},
            'right_differences': {'name': '右侧不同点', 'prefix': 'right_diff'}
        }
    },
    'tree_map': {
        'purpose': '分类整理',
        'center_name': '主题',
        'node_name': '类别和项目',
        'array_name': 'items',
        'node_id_prefix': 'item'
    },
    'mindmap': {
        'purpose': '展开思维',
        'center_name': '中心主题',
        'node_name': '分支',
        'array_name': 'branches',
        'node_id_prefix': 'branch'
    }
}


class VoiceDiagramAgentV2:
    """
    Complete voice diagram agent with all capabilities:
    - Diagram updates (all node types)
    - UI actions (open panels, select nodes, get help)
    - Content-based search
    - Multi-step actions
    """
    
    def __init__(self):
        pass
        
    async def parse_voice_command(
        self,
        user_message: str,
        diagram_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse voice command and extract structured actions.
        
        Returns:
            {
                'action': str,
                'target': str,
                'node_index': int,
                'node_id': str,
                'search_term': str,
                'array_type': str,  # For double_bubble_map
                'count': int,
                'actions': List[Dict],  # Multi-step
                'confidence': float
            }
        """
        try:
            # Extract context
            diagram_type = diagram_context.get('diagram_type', 'unknown')
            diagram_data = diagram_context.get('diagram_data', {})
            center_text = diagram_data.get('center', {}).get('text', 'unknown')
            nodes = diagram_data.get('children', [])
            
            # Panel states
            thinkguide_open = diagram_context.get('thinkguide_open', False)
            palette_open = diagram_context.get('node_palette_open', False)
            selected_nodes = diagram_context.get('selected_nodes', [])
            
            # Get diagram metadata
            metadata = DIAGRAM_METADATA.get(diagram_type, {
                'purpose': '思维整理',
                'center_name': '主题',
                'node_name': '节点'
            })
            
            # Build comprehensive prompt
            prompt = self._build_prompt(
                user_message=user_message,
                diagram_type=diagram_type,
                metadata=metadata,
                center_text=center_text,
                nodes=nodes,
                thinkguide_open=thinkguide_open,
                palette_open=palette_open,
                selected_nodes=selected_nodes
            )
            
            # Call Qwen Turbo
            response = await llm_service.chat(
                prompt=prompt,
                model='qwen',
                temperature=0.1,
                max_tokens=300,
                timeout=5.0
            )
            
            logger.debug(f"Qwen response: {response}")
            
            # Parse response
            result = self._parse_response(response)
            
            # Post-process: resolve node references
            result = self._resolve_node_references(result, nodes, diagram_type)
            
            logger.info(f"Parsed command: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            return {'action': 'none', 'confidence': 0.0}
    
    def _build_prompt(
        self,
        user_message: str,
        diagram_type: str,
        metadata: Dict,
        center_text: str,
        nodes: List,
        thinkguide_open: bool,
        palette_open: bool,
        selected_nodes: List
    ) -> str:
        """Build comprehensive prompt with all context"""
        
        # Format nodes
        nodes_text = self._format_nodes(nodes)
        selected_text = f"{len(selected_nodes)}个节点已选中" if selected_nodes else "无"
        
        prompt = f"""你是一个智能图表助手。用户正在使用语音命令操作{diagram_type}图表。

【图表类型】
{diagram_type}: {metadata.get('purpose', '思维整理')}
- 中心表示：{metadata.get('center_name', '主题')}
- 节点表示：{metadata.get('node_name', '节点')}

【当前状态】
- 中心主题：{center_text}
- 节点数量：{len(nodes)}
{nodes_text}
- ThinkGuide面板：{'✓ 已开启' if thinkguide_open else '✗ 未开启'}
- Node Palette：{'✓ 已开启' if palette_open else '✗ 未开启'}
- 已选节点：{selected_text}

【用户说】
"{user_message}"

【可用操作】

1. 更新图表数据
- update_center: 修改中心主题
- update_node: 修改节点（可用序号或内容描述）
- add_node: 添加新节点
- delete_node: 删除节点

2. UI操作 - 面板控制
- open_thinkguide: 打开ThinkGuide面板
- close_thinkguide: 关闭ThinkGuide面板
- open_node_palette: 打开Node Palette获取节点建议
- close_node_palette: 关闭Node Palette
- open_mindmate: 打开MindMate AI助手
- close_mindmate: 关闭MindMate
- close_all_panels: 关闭所有面板

3. UI操作 - 交互控制
- select_node: 选中/高亮某个节点
- explain_node: 让ThinkGuide解释某个节点
- ask_thinkguide: 向ThinkGuide发送问题/提示词
- ask_mindmate: 向MindMate发送问题
- auto_complete: 触发AI自动完成按钮
- help: 请求帮助或建议

4. 复合操作
- 可以返回多个操作的组合（actions数组）

【返回格式】JSON:
{{
    "action": "主要操作类型",
    "target": "目标文本（如果有）",
    "node_index": 节点序号（从0开始，如果有）,
    "search_term": "搜索词（如果按内容查找节点）",
    "array_type": "数组类型（仅double_bubble_map: similarities|left_differences|right_differences）",
    "count": 数量（如果添加多个节点）,
    "actions": [多个操作时的数组],
    "confidence": 置信度（0-1）
}}

【示例】

例1 - 修改中心：
用户："把主题改成摩托车"
返回：{{"action": "update_center", "target": "摩托车", "confidence": 0.95}}

例2 - 按序号修改节点：
用户："把第一个改成汽车"
返回：{{"action": "update_node", "target": "汽车", "node_index": 0, "confidence": 0.9}}

例3 - 按内容查找并修改：
用户："把关于背景的那个改成环境"
返回：{{"action": "update_node", "target": "环境", "search_term": "背景", "confidence": 0.85}}

例4 - 打开帮助：
用户："帮我添加更多节点"
返回：{{"action": "open_node_palette", "confidence": 0.9}}

例5 - 解释节点：
用户："解释第一个节点"
返回：{{"action": "explain_node", "node_index": 0, "confidence": 0.95}}

例6 - 选中节点：
用户："选中第二个"
返回：{{"action": "select_node", "node_index": 1, "confidence": 0.95}}

例7 - 复合操作：
用户："选中第一个并解释它"
返回：{{"actions": [{{"action": "select_node", "node_index": 0}}, {{"action": "explain_node", "node_index": 0}}], "confidence": 0.9}}

例8 - 添加多个：
用户："添加三个新观察"
返回：{{"action": "add_node", "count": 3, "confidence": 0.85}}

例9 - 打开思维向导：
用户："打开思维向导"
返回：{{"action": "open_thinkguide", "confidence": 0.95}}

例10 - 请求帮助：
用户："我不知道怎么做"
返回：{{"action": "open_thinkguide", "confidence": 0.9}}

例11 - 打开面板：
用户："打开思维向导面板"
返回：{{"action": "open_thinkguide", "confidence": 0.95}}

例12 - 关闭面板：
用户："关闭思维向导"
返回：{{"action": "close_thinkguide", "confidence": 0.95}}

例13 - 向ThinkGuide提问：
用户："问问思维向导什么是光合作用"
返回：{{"action": "ask_thinkguide", "target": "什么是光合作用", "confidence": 0.9}}

例14 - 直接发送问题到ThinkGuide：
用户："让思维向导解释一下摩擦力"
返回：{{"action": "ask_thinkguide", "target": "解释一下摩擦力", "confidence": 0.9}}

例15 - 打开MindMate：
用户："打开AI助手"
返回：{{"action": "open_mindmate", "confidence": 0.95}}

例16 - 向MindMate提问：
用户："问问AI助手这个图怎么画"
返回：{{"action": "ask_mindmate", "target": "这个图怎么画", "confidence": 0.85}}

例17 - 关闭所有面板：
用户："关闭所有面板"
返回：{{"action": "close_all_panels", "confidence": 0.95}}

例18 - 自动完成图表：
用户："自动完成"
返回：{{"action": "auto_complete", "confidence": 0.95}}

例19 - AI自动填充：
用户："让AI帮我完成这个图"
返回：{{"action": "auto_complete", "confidence": 0.9}}

例20 - 自动补全：
用户："自动补全剩下的节点"
返回：{{"action": "auto_complete", "confidence": 0.9}}

例21 - 复合操作（打开并提问）：
用户："打开思维向导并问问它什么是惯性"
返回：{{"actions": [{{"action": "open_thinkguide"}}, {{"action": "ask_thinkguide", "target": "什么是惯性"}}], "confidence": 0.85}}

例22 - 普通对话：
用户："这是什么图？"
返回：{{"action": "none", "confidence": 0.95}}

现在分析上面用户的话，只返回JSON，不要其他内容。"""
        
        return prompt
    
    def _format_nodes(self, nodes: List) -> str:
        """Format nodes for display"""
        if not nodes:
            return "- 当前节点：无"
        
        lines = ["- 当前节点："]
        for i, node in enumerate(nodes[:10]):
            text = self._get_node_text(node)
            lines.append(f"  {i+1}. {text}")
        
        if len(nodes) > 10:
            lines.append(f"  ... 还有{len(nodes)-10}个节点")
        
        return "\n".join(lines)
    
    def _get_node_text(self, node: Any) -> str:
        """Extract text from node (handles different formats)"""
        if isinstance(node, str):
            return node
        elif isinstance(node, dict):
            return node.get('text') or node.get('label') or node.get('content') or str(node)
        return str(node)
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse Qwen's JSON response"""
        try:
            # Clean markdown
            cleaned = response.strip()
            if '```' in cleaned:
                # Extract JSON from code block
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                if start >= 0 and end > start:
                    cleaned = cleaned[start:end]
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Extract fields
            result = {
                'action': data.get('action', 'none'),
                'target': data.get('target'),
                'node_index': self._safe_int(data.get('node_index')),
                'search_term': data.get('search_term'),
                'array_type': data.get('array_type'),
                'count': self._safe_int(data.get('count')),
                'actions': data.get('actions'),
                'confidence': float(data.get('confidence', 0.8))
            }
            
            return result
            
        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Response: {response}")
            return {'action': 'none', 'confidence': 0.0}
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert to int"""
        if value is None:
            return None
        try:
            return int(value)
        except:
            return None
    
    def _resolve_node_references(
        self,
        result: Dict[str, Any],
        nodes: List,
        diagram_type: str
    ) -> Dict[str, Any]:
        """
        Resolve node references:
        - If search_term provided, find matching node
        - Generate proper node_id based on diagram type
        """
        # If search_term provided, find best matching node
        if result.get('search_term') and nodes:
            match = self._find_node_by_content(result['search_term'], nodes)
            if match:
                result['node_index'] = match['index']
                result['node_text'] = match['text']
                result['match_score'] = match['score']
                logger.info(f"Found node by content: index={match['index']}, text={match['text']}, score={match['score']:.2f}")
        
        # Generate node_id if we have node_index
        if result.get('node_index') is not None:
            metadata = DIAGRAM_METADATA.get(diagram_type, {})
            prefix = metadata.get('node_id_prefix', 'node')
            result['node_id'] = f"{prefix}_{result['node_index']}"
        
        return result
    
    def _find_node_by_content(
        self,
        search_term: str,
        nodes: List
    ) -> Optional[Dict[str, Any]]:
        """Find node by fuzzy content matching"""
        best_match = None
        best_score = 0.0
        
        for i, node in enumerate(nodes):
            text = self._get_node_text(node)
            score = self._similarity_score(search_term, text)
            
            if score > best_score:
                best_score = score
                best_match = {
                    'index': i,
                    'text': text,
                    'score': score
                }
        
        # Only return if confidence > 0.6
        return best_match if best_score > 0.6 else None
    
    def _similarity_score(self, a: str, b: str) -> float:
        """Calculate similarity between two strings"""
        # Normalize
        a = a.lower().strip()
        b = b.lower().strip()
        
        # Exact match
        if a == b:
            return 1.0
        
        # Substring match
        if a in b or b in a:
            return 0.9
        
        # Sequence matcher
        return SequenceMatcher(None, a, b).ratio()


# Global instance
voice_diagram_agent_v2 = VoiceDiagramAgentV2()

