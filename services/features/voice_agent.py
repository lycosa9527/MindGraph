from datetime import datetime
from typing import Dict, Any, Optional, List, Annotated, TypedDict
import json
import logging

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from services.llm import llm_service

"""
Voice Agent - Persistent LangGraph Agent for Voice Commands
Uses LangChain 1.x with LangGraph for stateful diagram control

Features:
- Persistent diagram state (always knows current nodes)
- Conversation memory (context-aware responses)
- Tool-based actions (select, add, delete, update nodes)
- Real-time sync with frontend diagram

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司
(Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""





logger = logging.getLogger('VOICE_AGENT')


# ============================================================================
# Agent State Definition
# ============================================================================

class DiagramNode(TypedDict):
    """Represents a node in the diagram"""
    id: str
    index: int
    text: str


class DiagramState(TypedDict):
    """Current diagram state"""
    diagram_type: str
    center_text: str
    nodes: List[DiagramNode]
    selected_nodes: List[str]


class AgentState(TypedDict):
    """Complete agent state with memory"""
    # Conversation messages (with memory)
    messages: Annotated[List, add_messages]

    # Current diagram state (synced from frontend)
    diagram: DiagramState

    # Panel states
    active_panel: str
    mindmate_open: bool
    node_palette_open: bool

    # Last parsed action (output)
    action: Optional[Dict[str, Any]]

    # Session info
    session_id: str
    last_updated: str


# ============================================================================
# Tools for Diagram Operations
# ============================================================================

@tool
def select_node(node_identifier: str) -> Dict[str, Any]:
    """
    Select a node in the diagram by its text content or index.

    Args:
        node_identifier: Node text (e.g., "ABC") or index (e.g., "1", "first")

    Returns:
        Action to select the node
    """
    return {
        "action": "select_node",
        "target": node_identifier,
        "confidence": 0.95
    }


@tool
def update_center(new_text: str) -> Dict[str, Any]:
    """
    Update the center/topic of the diagram.

    Args:
        new_text: New text for the center

    Returns:
        Action to update center
    """
    return {
        "action": "update_center",
        "target": new_text,
        "confidence": 0.95
    }


@tool
def add_node(text: str, position: Optional[int] = None) -> Dict[str, Any]:
    """
    Add a new node to the diagram.

    Args:
        text: Text content for the new node
        position: Optional position/index where to add the node (0-based).
                  If None, adds to the end. If specified, inserts at that position.
                  For mindmaps: "branch 1" = position 0, "branch 2" = position 1, etc.

    Returns:
        Action to add node
    """
    result = {
        "action": "add_node",
        "target": text,
        "confidence": 0.95
    }
    if position is not None:
        result["node_index"] = position
    return result


@tool
def delete_node(node_identifier: str) -> Dict[str, Any]:
    """
    Delete a node from the diagram.

    Args:
        node_identifier: Node text or index to delete

    Returns:
        Action to delete node
    """
    return {
        "action": "delete_node",
        "target": node_identifier,
        "confidence": 0.95
    }


@tool
def update_node(node_identifier: str, new_text: str) -> Dict[str, Any]:
    """
    Update a node's text content.

    Args:
        node_identifier: Node text or index to update
        new_text: New text for the node

    Returns:
        Action to update node
    """
    return {
        "action": "update_node",
        "target": new_text,
        "node_identifier": node_identifier,
        "confidence": 0.95
    }


@tool
def auto_complete() -> Dict[str, Any]:
    """
    Trigger AI auto-complete to fill in the diagram.

    Returns:
        Action to trigger auto-complete
    """
    return {
        "action": "auto_complete",
        "confidence": 0.95
    }


@tool
def open_panel(panel_name: str) -> Dict[str, Any]:
    """
    Open a panel (mindmate, node_palette).

    Args:
        panel_name: Name of panel to open

    Returns:
        Action to open panel
    """
    panel_map = {
        "thinkguide": "open_mindmate",  # Redirect to MindMate
        "mindmate": "open_mindmate",
        "node_palette": "open_node_palette",
        "palette": "open_node_palette"
    }
    action = panel_map.get(panel_name.lower(), f"open_{panel_name}")
    return {
        "action": action,
        "confidence": 0.95
    }


@tool
def close_panel(panel_name: str) -> Dict[str, Any]:
    """
    Close a panel or close all panels.

    Args:
        panel_name: Name of panel to close, or "all" for all panels

    Returns:
        Action to close panel
    """
    if panel_name.lower() == "all":
        return {"action": "close_all_panels", "confidence": 0.95}

    panel_map = {
        "thinkguide": "close_mindmate",  # Redirect to MindMate
        "mindmate": "close_mindmate",
        "node_palette": "close_node_palette"
    }
    action = panel_map.get(panel_name.lower(), f"close_{panel_name}")
    return {
        "action": action,
        "confidence": 0.95
    }


# ============================================================================
# Voice Agent Class
# ============================================================================

class VoiceAgent:
    """
    Persistent voice agent with LangGraph state management.
    Maintains diagram state and conversation memory.
    """

    # Available tools
    TOOLS = [
        select_node,
        update_center,
        add_node,
        delete_node,
        update_node,
        auto_complete,
        open_panel,
        close_panel
    ]

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.config = {"configurable": {"thread_id": session_id}}

        # Initialize state
        self._state = self._create_initial_state()

        logger.info("VoiceAgent initialized for session %s", session_id)

    def _create_initial_state(self) -> AgentState:
        """Create initial agent state"""
        return {
            "messages": [],
            "diagram": {
                "diagram_type": "unknown",
                "center_text": "",
                "nodes": [],
                "selected_nodes": []
            },
            "active_panel": "none",
            "mindmate_open": False,
            "node_palette_open": False,
            "action": None,
            "session_id": self.session_id,
            "last_updated": datetime.now().isoformat()
        }

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create graph with state schema
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("parse_command", self._parse_command_node)
        graph.add_node("resolve_references", self._resolve_references_node)

        # Define edges
        graph.set_entry_point("parse_command")
        graph.add_edge("parse_command", "resolve_references")
        graph.add_edge("resolve_references", END)

        # Compile with memory
        return graph.compile(checkpointer=self.memory)

    async def _parse_command_node(self, state: AgentState) -> Dict[str, Any]:
        """Parse user command using LLM"""

        # Get the last user message
        messages = state.get("messages", [])
        if not messages:
            return {"action": None}

        last_message = messages[-1]
        user_text = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # Build context-aware prompt
        diagram = state.get("diagram", {})
        nodes = diagram.get("nodes", [])

        # Format nodes for prompt
        nodes_text = ""
        for node in nodes[:15]:
            nodes_text += f'\n  {node["index"]+1}. "{node["text"]}" (id: {node["id"]})'

        diagram_type = diagram.get('diagram_type', 'unknown')

        # Build diagram-specific instructions for all diagram types
        diagram_specific_notes = ""
        if diagram_type == 'double_bubble_map':
            diagram_specific_notes = """
【Double Bubble Map Special Handling】
- Center structure: Uses TWO topics (left and right) instead of single center
- Node arrays: similarities, left_differences, right_differences
- Node terminology: "similarity", "left difference", "right difference", "共同点", "左边不同点", "右边不同点"
- For update_center: Extract TWO topics from comparison commands
- For add_node: Can specify "category" field: "similarities",
  "left_differences", "right_differences"
- Return structured data:
  {"action": "update_center", "left": "Topic1", "right": "Topic2",
   "target": "Topic1和Topic2", "confidence": 0.95}
- Examples:
  * "比较苹果和梨子" →
    {"action": "update_center", "left": "苹果", "right": "梨子",
     "target": "苹果和梨子", "confidence": 0.95}
  * "change center to apples vs pears" →
    {"action": "update_center", "left": "apples", "right": "pears",
     "target": "apples vs pears", "confidence": 0.95}
  * "similarity 1 is color" →
    {"action": "add_node", "target": "color", "category": "similarities",
     "node_index": 0, "confidence": 0.95}
  * "left difference 1 is shape" →
    {"action": "add_node", "target": "shape",
     "category": "left_differences", "node_index": 0, "confidence": 0.95}
"""
        elif diagram_type == 'flow_map':
            diagram_specific_notes = """
【Flow Map Special Handling】
- Center structure: Uses "title" field instead of "topic"
- Node arrays: steps (main steps) and substeps (sub-steps under each step)
- Node terminology:
  * Steps: "step 1", "step 2", "步骤1", "步骤2", "first step", "second step"
  * Sub-steps: "substep 1.1", "substep 1.2", "子步骤1.1", "子步骤1.2", "step 1 substep 1", "步骤1的子步骤1"
- For update_center: Use "title" field
- For add_node:
  * Steps: "step 1" = node_index 0, "step 2" = node_index 1, etc.
  * Sub-steps: "substep 1.1" = step_index 0, substep_index 0; "substep 1.2" = step_index 0, substep_index 1
- For update_node/delete_node: Include step_index and substep_index for substeps
- Return: {"action": "update_center", "title": "Process Name",
  "target": "Process Name", "confidence": 0.95}
- Examples:
  * "step 1 is prepare" →
    {"action": "add_node", "target": "prepare", "node_index": 0,
     "confidence": 0.95}
  * "步骤1是准备" →
    {"action": "add_node", "target": "准备", "node_index": 0,
     "confidence": 0.95}
  * "substep 1.1 is gather materials" →
    {"action": "add_node", "target": "gather materials", "step_index": 0,
     "substep_index": 0, "confidence": 0.95}
  * "步骤1的子步骤1是收集材料" →
    {"action": "add_node", "target": "收集材料", "step_index": 0,
     "substep_index": 0, "confidence": 0.95}
  * "update substep 1.2 to check inventory" →
    {"action": "update_node", "target": "check inventory", "step_index": 0,
     "substep_index": 1, "confidence": 0.95}
  * "delete substep 2.1" →
    {"action": "delete_node", "step_index": 1, "substep_index": 0,
     "confidence": 0.95}
"""
        elif diagram_type == 'multi_flow_map':
            diagram_specific_notes = """
【Multi-Flow Map Special Handling】
- Center structure: Uses "event" field instead of "topic"
- Node arrays: causes, effects (causal relationships)
- Node terminology: "cause 1", "effect 1", "原因1", "结果1", "first cause", "first effect"
- For update_center: Use "event" field
- For add_node: Can specify "category" field: "causes" or "effects"
- Return: {"action": "update_center", "event": "Event Name",
  "target": "Event Name", "confidence": 0.95}
- Examples:
  * "cause 1 is rain" →
    {"action": "add_node", "target": "rain", "category": "causes",
     "node_index": 0, "confidence": 0.95}
  * "effect 1 is flood" →
    {"action": "add_node", "target": "flood", "category": "effects",
     "node_index": 0, "confidence": 0.95}
"""
        elif diagram_type == 'brace_map':
            diagram_specific_notes = """
【Brace Map Special Handling】
- Center structure: Uses "whole" field instead of "topic"
- Node array: parts (hierarchical whole-to-parts)
- Node terminology: "part 1", "part 2", "部分1", "部分2", "first part", "second part"
- For update_center: Use "whole" field
- For add_node: "part 1" = node_index 0, "part 2" = node_index 1, etc.
- Return: {"action": "update_center", "whole": "Whole Name",
  "target": "Whole Name", "confidence": 0.95}
- Examples:
  * "part 1 is engine" →
    {"action": "add_node", "target": "engine", "node_index": 0,
     "confidence": 0.95}
  * "部分1是引擎" →
    {"action": "add_node", "target": "引擎", "node_index": 0,
     "confidence": 0.95}
"""
        elif diagram_type == 'bridge_map':
            diagram_specific_notes = """
【Bridge Map Special Handling】
- Center structure: Uses "dimension" field instead of "topic" (can be empty for diverse relationships)
- Node array: analogies (relating factor pairs)
- Node terminology: "analogy 1", "pair 1", "类比1", "第一对", "first analogy", "first pair"
- For update_center: Use "dimension" field
- For add_node: Analogies are pairs, so specify both "left" and "right" fields
- Return: {"action": "update_center", "dimension": "Dimension Name",
  "target": "Dimension Name", "confidence": 0.95}
- Examples:
  * "analogy 1: wheel is to car as key is to keyboard" →
    {"action": "add_node", "target": "wheel : car", "left": "wheel",
     "right": "car", "node_index": 0, "confidence": 0.95}
"""
        elif diagram_type in ['mindmap', 'mind_map']:
            diagram_specific_notes = """
【Mind Map Special Handling】
- Center structure: Uses "topic" field
- Node array: children (hierarchical: branches with children)
- Node terminology:
  * Branches: "branch 1", "branch 2", "分支1", "分支2"
  * Children: "child 1.1", "child 1.2", "子项1.1", "子项1.2", "branch 1 child 1", "分支1的子项1"
- For update_center: Use standard "target" field (maps to "topic")
- For add_node:
  * Branches: "branch 1" = node_index 0, "branch 2" = node_index 1, etc.
  * Children: "child 1.1" = branch_index 0, child_index 0; "child 1.2" = branch_index 0, child_index 1
- For update_node/delete_node: Include branch_index and child_index for children
- Return: {"action": "update_center", "target": "Topic Name",
  "confidence": 0.95}
- Examples:
  * "branch 1 is fruits" →
    {"action": "add_node", "target": "fruits", "node_index": 0,
     "confidence": 0.95}
  * "分支1是水果" →
    {"action": "add_node", "target": "水果", "node_index": 0,
     "confidence": 0.95}
  * "topic is cars, branch 1 is sedans, branch 2 is SUVs" →
    Parse as: update_center first, then add_node with node_index 0,
    then add_node with node_index 1
  * "child 1.1 is apples" →
    {"action": "add_node", "target": "apples", "branch_index": 0,
     "child_index": 0, "confidence": 0.95}
  * "分支1的子项1是苹果" →
    {"action": "add_node", "target": "苹果", "branch_index": 0,
     "child_index": 0, "confidence": 0.95}
  * "update child 1.2 to oranges" →
    {"action": "update_node", "target": "oranges", "branch_index": 0,
     "child_index": 1, "confidence": 0.95}
  * "delete child 2.1" →
    {"action": "delete_node", "branch_index": 1, "child_index": 0,
     "confidence": 0.95}
"""
        elif diagram_type == 'tree_map':
            diagram_specific_notes = """
【Tree Map Special Handling】
- Center structure: Uses "topic" field
- Node array: children (hierarchical: categories with items)
- Node terminology:
  * Categories: "category 1", "category 2", "类别1", "类别2"
  * Items: "item 1.1", "item 1.2", "项目1.1", "项目1.2", "category 1 item 1", "类别1的项目1"
- For update_center: Use standard "target" field (maps to "topic")
- For add_node:
  * Categories: "category 1" = node_index 0, "category 2" = node_index 1, etc.
  * Items: "item 1.1" = category_index 0, item_index 0; "item 1.2" = category_index 0, item_index 1
- For update_node/delete_node: Include category_index and item_index for items
- Return: {"action": "update_center", "target": "Topic Name",
  "confidence": 0.95}
- Examples:
  * "category 1 is mammals" →
    {"action": "add_node", "target": "mammals", "node_index": 0,
     "confidence": 0.95}
  * "类别1是哺乳动物" →
    {"action": "add_node", "target": "哺乳动物", "node_index": 0,
     "confidence": 0.95}
  * "item 1.1 is dogs" →
    {"action": "add_node", "target": "dogs", "category_index": 0,
     "item_index": 0, "confidence": 0.95}
  * "类别1的项目1是狗" →
    {"action": "add_node", "target": "狗", "category_index": 0,
     "item_index": 0, "confidence": 0.95}
  * "update item 1.2 to cats" →
    {"action": "update_node", "target": "cats", "category_index": 0,
     "item_index": 1, "confidence": 0.95}
  * "delete item 2.1" →
    {"action": "delete_node", "category_index": 1, "item_index": 0,
     "confidence": 0.95}
"""
        elif diagram_type == 'circle_map':
            diagram_specific_notes = """
【Circle Map Special Handling】
- Center structure: Uses "topic" or "center.text" field
- Node array: contexts (observations, examples, characteristics)
- Node terminology: "context 1", "context 2", "上下文1", "上下文2", "first context", "second context"
- For update_center: Use standard "target" field (maps to "topic" or "center.text")
- For add_node: "context 1" = node_index 0, "context 2" = node_index 1, etc.
- Return: {"action": "update_center", "target": "Topic Name", "confidence": 0.95}
- Examples:
  * "context 1 is classroom" → {"action": "add_node", "target": "classroom", "node_index": 0, "confidence": 0.95}
  * "上下文1是教室" → {"action": "add_node", "target": "教室", "node_index": 0, "confidence": 0.95}
"""
        elif diagram_type == 'bubble_map':
            diagram_specific_notes = """
【Bubble Map Special Handling】
- Center structure: Uses "topic" field
- Node array: attributes (descriptive characteristics)
- Node terminology: "attribute 1", "attribute 2", "属性1", "属性2", "first attribute", "second attribute"
- For update_center: Use standard "target" field (maps to "topic")
- For add_node: "attribute 1" = node_index 0, "attribute 2" = node_index 1, etc.
- Return: {"action": "update_center", "target": "Topic Name", "confidence": 0.95}
- Examples:
  * "attribute 1 is red" → {"action": "add_node", "target": "red", "node_index": 0, "confidence": 0.95}
  * "属性1是红色" → {"action": "add_node", "target": "红色", "node_index": 0, "confidence": 0.95}
"""
        elif diagram_type == 'concept_map':
            diagram_specific_notes = """
【Concept Map Special Handling】
- Center structure: Uses "topic" field
- Node arrays: concepts (flat array) + relationships (edges between concepts)
- Node terminology:
  * Concepts: "concept 1", "concept 2", "概念1", "概念2"
  * Relationships: "relationship", "关系", "link", "连接"
- For update_center: Use standard "target" field (maps to "topic")
- For add_node:
  * Concepts: "concept 1" = node_index 0, "concept 2" = node_index 1, etc.
  * Relationships: Use "from", "to", "label" fields (e.g., "Concept1 causes Concept2")
- For update_node: Include relationship_index for relationships, or node_index for concepts
- For delete_node: Include relationship_index for relationships, or node_index for concepts
- Return: {"action": "update_center", "target": "Topic Name",
  "confidence": 0.95}
- Examples:
  * "concept 1 is photosynthesis" →
    {"action": "add_node", "target": "photosynthesis", "node_index": 0,
     "confidence": 0.95}
  * "概念1是光合作用" →
    {"action": "add_node", "target": "光合作用", "node_index": 0,
     "confidence": 0.95}
  * "add relationship: Concept1 causes Concept2" →
    {"action": "add_node", "from": "Concept1", "to": "Concept2",
     "label": "causes", "confidence": 0.95}
  * "添加关系：概念1导致概念2" →
    {"action": "add_node", "from": "概念1", "to": "概念2", "label": "导致",
     "confidence": 0.95}
  * "update relationship 0 label to leads to" →
    {"action": "update_node", "target": "leads to", "relationship_index": 0,
     "confidence": 0.95}
  * "delete relationship 1" → {"action": "delete_node", "relationship_index": 1, "confidence": 0.95}
"""

        prompt = f"""You are a diagram control assistant. Parse the user's command and return a JSON action.

【Current Diagram】
- Type: {diagram_type}
- Center: {diagram.get('center_text', 'Not set')}
- Nodes:{nodes_text if nodes_text else ' None'}
{diagram_specific_notes}
【User Command】
"{user_text}"

【Available Actions】
- select_node: Select a node (by name or number)
- update_center: Change the center topic (structure varies by diagram type - see diagram-specific notes above)
- add_node: Add a new node (node type varies by diagram: context/attribute/step/part/branch/etc.)
  * Can include "node_index" to specify position (0-based): "branch 1" = node_index 0, "branch 2" = node_index 1, etc.
  * If node_index not specified, adds to the end
- delete_node: Remove a node
- update_node: Change a node's text (can update existing node at specific position)
- auto_complete: AI fill/complete the diagram (trigger AI auto-complete feature)
- open_mindmate/open_node_palette: Open panels
- close_mindmate/close_all_panels: Close panels
- none: Just conversation, no action needed

【Structured Input Pattern】
When users specify topic and multiple nodes with positions, use diagram-specific terminology:
- Mindmap: "branch 1", "branch 2" → node_index 0, 1, etc.
- Flow map: "step 1", "step 2" → node_index 0, 1, etc.
- Tree map: "category 1", "category 2" → node_index 0, 1, etc.
- Circle map: "context 1", "context 2" → node_index 0, 1, etc.
- Bubble map: "attribute 1", "attribute 2" → node_index 0, 1, etc.
- Brace map: "part 1", "part 2" → node_index 0, 1, etc.
- Double bubble map: "similarity 1", "left difference 1", "right difference 1" → specify category field
- Multi-flow map: "cause 1", "effect 1" → specify category field
- Bridge map: "analogy 1", "pair 1" → specify left and right fields

CRITICAL: Always use the correct terminology for the current diagram type!
- Parse as multiple actions: first update_center, then multiple add_node actions with node_index
- Convert 1-based user terminology (branch 1, step 1) to 0-based node_index (0, 1)
- If user says "branch 1 should be X" and branch 1 already exists, use update_node instead of add_node

【Important Notes】
- "这张图", "这幅图", "这个图", "图表", "图" all refer to "the diagram"
- "完成" means "complete" or "finish"
- "自动" means "automatically" or "auto"
- Commands asking to complete/fill the diagram should trigger auto_complete
- For double bubble maps, ALWAYS extract and return both "left" and "right" topics separately
- Node types vary by diagram: context (circle_map), attribute (bubble_map),
  step (flow_map), part (brace_map), branch (mindmap), etc.

【Return JSON】
{{"action": "action_name", "target": "value", "node_index": 0, "confidence": 0.9}}
For double bubble map update_center, also include "left" and "right" fields.

Examples:
【Select Node】
- "选中ABC" → {{"action": "select_node", "target": "ABC", "confidence": 0.95}}
- "选第一个" → {{"action": "select_node", "node_index": 0, "confidence": 0.95}}
- "select the first one" → {{"action": "select_node", "node_index": 0, "confidence": 0.95}}
- "选择第三个节点" → {{"action": "select_node", "node_index": 2, "confidence": 0.95}}

【Update Center/Topic】
- "把主题改成汽车" → {{"action": "update_center", "target": "汽车", "confidence": 0.95}}
- "主题改成摩托车" → {{"action": "update_center", "target": "摩托车", "confidence": 0.95}}
- "change topic to cars" → {{"action": "update_center", "target": "cars", "confidence": 0.95}}
- "can you change the center to cars" → {{"action": "update_center", "target": "cars", "confidence": 0.9}}
- "please update the topic to motorcycles" → {{"action": "update_center", "target": "motorcycles", "confidence": 0.9}}
- "I want to change the center to apples" → {{"action": "update_center", "target": "apples", "confidence": 0.9}}

【Update Node】
- "把第一个节点改成苹果" →
  {{"action": "update_node", "target": "苹果", "node_index": 0,
   "confidence": 0.95}}
- "change the first node to apples" →
  {{"action": "update_node", "target": "apples", "node_index": 0,
   "confidence": 0.95}}
- "can you change node 1 to fruits" →
  {{"action": "update_node", "target": "fruits", "node_index": 0,
   "confidence": 0.9}}
- "please update ABC to XYZ" →
  {{"action": "update_node", "target": "XYZ", "node_identifier": "ABC",
   "confidence": 0.9}}
- "I want to change the second node to cars" →
  {{"action": "update_node", "target": "cars", "node_index": 1,
   "confidence": 0.9}}

For Double Bubble Map:
- "把第一个相似点改成颜色" →
  {{"action": "update_node", "target": "颜色", "node_index": 0,
   "category": "similarities", "confidence": 0.95}}
- "change the first left difference to shape" →
  {{"action": "update_node", "target": "shape", "node_index": 0,
   "category": "left_differences", "confidence": 0.95}}

For Multi-Flow Map:
- "把第一个原因改成下雨" →
  {{"action": "update_node", "target": "下雨", "node_index": 0,
   "category": "causes", "confidence": 0.95}}
- "change the first effect to flood" →
  {{"action": "update_node", "target": "flood", "node_index": 0,
   "category": "effects", "confidence": 0.95}}

For Bridge Map:
- "把第一个类比改成轮子对应汽车" →
  {{"action": "update_node", "target": "轮子 : 汽车", "left": "轮子",
   "right": "汽车", "node_index": 0, "confidence": 0.95}}

For Flow Map Sub-steps:
- "update substep 1.2 to check inventory" →
  {{"action": "update_node", "target": "check inventory", "step_index": 0,
   "substep_index": 1, "confidence": 0.95}}
- "把步骤1的子步骤2改成检查库存" →
  {{"action": "update_node", "target": "检查库存", "step_index": 0,
   "substep_index": 1, "confidence": 0.95}}

For Tree Map Items:
- "update item 1.2 to cats" →
  {{"action": "update_node", "target": "cats", "category_index": 0,
   "item_index": 1, "confidence": 0.95}}
- "把类别1的项目2改成猫" →
  {{"action": "update_node", "target": "猫", "category_index": 0,
   "item_index": 1, "confidence": 0.95}}

For Brace Map Subparts:
- "update subpart 1.2 to pistons" →
  {{"action": "update_node", "target": "pistons", "part_index": 0,
   "subpart_index": 1, "confidence": 0.95}}
- "把部分1的子部分2改成活塞" →
  {{"action": "update_node", "target": "活塞", "part_index": 0,
   "subpart_index": 1, "confidence": 0.95}}

For Mindmap Children:
- "update child 1.2 to oranges" →
  {{"action": "update_node", "target": "oranges", "branch_index": 0,
   "child_index": 1, "confidence": 0.95}}
- "把分支1的子项2改成橙子" →
  {{"action": "update_node", "target": "橙子", "branch_index": 0,
   "child_index": 1, "confidence": 0.95}}

For Concept Map Relationships:
- "update relationship 0 label to leads to" →
  {{"action": "update_node", "target": "leads to", "relationship_index": 0,
   "confidence": 0.95}}
- "把关系0的标签改成导致" →
  {{"action": "update_node", "target": "导致", "relationship_index": 0,
   "confidence": 0.95}}

【Add Node】
- "添加一个节点叫做水果" → {{"action": "add_node", "target": "水果", "confidence": 0.95}}
- "加一个苹果" → {{"action": "add_node", "target": "苹果", "confidence": 0.95}}
- "add a node called apple" → {{"action": "add_node", "target": "apple", "confidence": 0.95}}
- "添加节点" → {{"action": "add_node", "confidence": 0.9}}
- "can you add a node called fruits" → {{"action": "add_node", "target": "fruits", "confidence": 0.9}}
- "please add fruits" → {{"action": "add_node", "target": "fruits", "confidence": 0.9}}
- "I want to add apples" → {{"action": "add_node", "target": "apples", "confidence": 0.9}}

【Add Node at Specific Position (Diagram-Specific Terminology)】
For Mindmap:
- "branch 1 should be sedans" →
  {{"action": "add_node", "target": "sedans", "node_index": 0,
   "confidence": 0.95}}
- "第一个分支是苹果" →
  {{"action": "add_node", "target": "苹果", "node_index": 0,
   "confidence": 0.95}}
- "child 1.1 is apples" →
  {{"action": "add_node", "target": "apples", "branch_index": 0,
   "child_index": 0, "confidence": 0.95}}
- "分支1的子项1是苹果" →
  {{"action": "add_node", "target": "苹果", "branch_index": 0,
   "child_index": 0, "confidence": 0.95}}

For Flow Map:
- "step 1 is prepare" →
  {{"action": "add_node", "target": "prepare", "node_index": 0,
   "confidence": 0.95}}
- "步骤1是准备" →
  {{"action": "add_node", "target": "准备", "node_index": 0,
   "confidence": 0.95}}
- "substep 1.1 is gather materials" →
  {{"action": "add_node", "target": "gather materials", "step_index": 0,
   "substep_index": 0, "confidence": 0.95}}
- "步骤1的子步骤1是收集材料" →
  {{"action": "add_node", "target": "收集材料", "step_index": 0,
   "substep_index": 0, "confidence": 0.95}}
- "step 1 substep 2 is check inventory" →
  {{"action": "add_node", "target": "check inventory", "step_index": 0,
   "substep_index": 1, "confidence": 0.95}}

For Tree Map:
- "category 1 is mammals" →
  {{"action": "add_node", "target": "mammals", "node_index": 0,
   "confidence": 0.95}}
- "类别1是哺乳动物" →
  {{"action": "add_node", "target": "哺乳动物", "node_index": 0,
   "confidence": 0.95}}
- "item 1.1 is dogs" →
  {{"action": "add_node", "target": "dogs", "category_index": 0,
   "item_index": 0, "confidence": 0.95}}
- "类别1的项目1是狗" →
  {{"action": "add_node", "target": "狗", "category_index": 0,
   "item_index": 0, "confidence": 0.95}}

For Circle Map:
- "context 1 is classroom" → {{"action": "add_node", "target": "classroom", "node_index": 0, "confidence": 0.95}}
- "上下文1是教室" → {{"action": "add_node", "target": "教室", "node_index": 0, "confidence": 0.95}}

For Bubble Map:
- "attribute 1 is red" → {{"action": "add_node", "target": "red", "node_index": 0, "confidence": 0.95}}
- "属性1是红色" → {{"action": "add_node", "target": "红色", "node_index": 0, "confidence": 0.95}}

For Brace Map:
- "part 1 is engine" →
  {{"action": "add_node", "target": "engine", "node_index": 0,
   "confidence": 0.95}}
- "部分1是引擎" →
  {{"action": "add_node", "target": "引擎", "node_index": 0,
   "confidence": 0.95}}
- "subpart 1.1 is cylinders" →
  {{"action": "add_node", "target": "cylinders", "part_index": 0,
   "subpart_index": 0, "confidence": 0.95}}
- "部分1的子部分1是气缸" →
  {{"action": "add_node", "target": "气缸", "part_index": 0,
   "subpart_index": 0, "confidence": 0.95}}

For Double Bubble Map:
- "similarity 1 is color" →
  {{"action": "add_node", "target": "color", "category": "similarities",
   "node_index": 0, "confidence": 0.95}}
- "left difference 1 is shape" →
  {{"action": "add_node", "target": "shape",
   "category": "left_differences", "node_index": 0, "confidence": 0.95}}

For Multi-Flow Map:
- "cause 1 is rain" →
  {{"action": "add_node", "target": "rain", "category": "causes",
   "node_index": 0, "confidence": 0.95}}
- "effect 1 is flood" →
  {{"action": "add_node", "target": "flood", "category": "effects",
   "node_index": 0, "confidence": 0.95}}

For Bridge Map:
- "analogy 1: wheel is to car" →
  {{"action": "add_node", "target": "wheel : car", "left": "wheel",
   "right": "car", "node_index": 0, "confidence": 0.95}}

For Concept Map:
- "concept 1 is photosynthesis" →
  {{"action": "add_node", "target": "photosynthesis", "node_index": 0,
   "confidence": 0.95}}
- "概念1是光合作用" →
  {{"action": "add_node", "target": "光合作用", "node_index": 0,
   "confidence": 0.95}}
- "add relationship: Concept1 causes Concept2" →
  {{"action": "add_node", "from": "Concept1", "to": "Concept2",
   "label": "causes", "confidence": 0.95}}
- "添加关系：概念1导致概念2" →
  {{"action": "add_node", "from": "概念1", "to": "概念2", "label": "导致",
   "confidence": 0.95}}

【Multi-Node Structured Input】
- "topic is cars, branch 1 is sedans, branch 2 is SUVs" →
  Parse as: update_center first, then add_node with node_index 0,
  then add_node with node_index 1
- "主题是汽车，分支1是轿车，分支2是SUV" →
  Parse as: update_center first, then add_node with node_index 0,
  then add_node with node_index 1

【Delete Node】
- "删除第一个" → {{"action": "delete_node", "node_index": 0, "confidence": 0.9}}
- "删掉ABC" → {{"action": "delete_node", "target": "ABC", "confidence": 0.9}}
- "delete the second node" → {{"action": "delete_node", "node_index": 1, "confidence": 0.9}}
- "can you delete the first node" → {{"action": "delete_node", "node_index": 0, "confidence": 0.85}}
- "please remove ABC" → {{"action": "delete_node", "target": "ABC", "confidence": 0.85}}
- "I want to delete node 3" → {{"action": "delete_node", "node_index": 2, "confidence": 0.85}}

For Flow Map Sub-steps:
- "delete substep 1.2" → {{"action": "delete_node", "step_index": 0, "substep_index": 1, "confidence": 0.95}}
- "删除步骤1的子步骤2" → {{"action": "delete_node", "step_index": 0, "substep_index": 1, "confidence": 0.95}}
- "remove step 2 substep 1" → {{"action": "delete_node", "step_index": 1, "substep_index": 0, "confidence": 0.95}}

For Tree Map Items:
- "delete item 1.2" → {{"action": "delete_node", "category_index": 0, "item_index": 1, "confidence": 0.95}}
- "删除类别1的项目2" → {{"action": "delete_node", "category_index": 0, "item_index": 1, "confidence": 0.95}}

For Brace Map Subparts:
- "delete subpart 1.2" → {{"action": "delete_node", "part_index": 0, "subpart_index": 1, "confidence": 0.95}}
- "删除部分1的子部分2" → {{"action": "delete_node", "part_index": 0, "subpart_index": 1, "confidence": 0.95}}

For Mindmap Children:
- "delete child 1.2" → {{"action": "delete_node", "branch_index": 0, "child_index": 1, "confidence": 0.95}}
- "删除分支1的子项2" → {{"action": "delete_node", "branch_index": 0, "child_index": 1, "confidence": 0.95}}

For Concept Map Relationships:
- "delete relationship 1" → {{"action": "delete_node", "relationship_index": 1, "confidence": 0.95}}
- "删除关系1" → {{"action": "delete_node", "relationship_index": 1, "confidence": 0.95}}

For Double Bubble Map:
- "删除第一个相似点" → {{"action": "delete_node", "node_index": 0, "category": "similarities", "confidence": 0.95}}
- "delete the first left difference" →
  {{"action": "delete_node", "node_index": 0,
   "category": "left_differences", "confidence": 0.95}}

For Multi-Flow Map:
- "删除第一个原因" → {{"action": "delete_node", "node_index": 0, "category": "causes", "confidence": 0.95}}
- "delete the first effect" → {{"action": "delete_node", "node_index": 0, "category": "effects", "confidence": 0.95}}

【Auto Complete】
- "自动完成" → {{"action": "auto_complete", "confidence": 0.95}}
- "帮我完成这幅图" → {{"action": "auto_complete", "confidence": 0.95}}
- "自动帮我完成这张图" → {{"action": "auto_complete", "confidence": 0.95}}
- "帮我完成这张图" → {{"action": "auto_complete", "confidence": 0.95}}
- "自动帮我完成" → {{"action": "auto_complete", "confidence": 0.95}}
- "自动完成这张图" → {{"action": "auto_complete", "confidence": 0.95}}
- "AI帮我填" → {{"action": "auto_complete", "confidence": 0.95}}
- "AI帮我完成" → {{"action": "auto_complete", "confidence": 0.95}}
- "auto complete" → {{"action": "auto_complete", "confidence": 0.95}}
- "fill in the rest" → {{"action": "auto_complete", "confidence": 0.95}}
- "complete the diagram" → {{"action": "auto_complete", "confidence": 0.95}}

【Conversation Only】
- "你好" → {{"action": "none", "confidence": 0.95}}
- "谢谢" → {{"action": "none", "confidence": 0.95}}

Return only JSON:"""

        try:
            # Get tracking info from state (set by process_command)
            tracking_info = state.get("_tracking_info", {})
            user_id = tracking_info.get("user_id")
            organization_id = tracking_info.get("organization_id")
            voice_session_id = tracking_info.get("voice_session_id")
            diagram_type = tracking_info.get("diagram_type", "unknown")

            # Use qwen-turbo for intention checking/classification (faster and optimized for this task)
            response = await llm_service.chat(
                prompt=prompt,
                model='qwen-turbo',  # Use Turbo for classification/intention checking
                temperature=0.1,
                max_tokens=200,
                timeout=5.0,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type='voice_command_parsing',
                diagram_type=diagram_type,
                session_id=voice_session_id,
                endpoint_path='/ws/voice'
            )

            # Parse JSON response
            action = self._parse_json_response(response)

            logger.info("Voice agent parsed command: user_text='%s', action=%s", user_text, action)

            return {"action": action}

        except Exception as e:
            logger.error("Parse error: %s", e)
            return {"action": {"action": "none", "confidence": 0.0}}

    async def _resolve_references_node(self, state: AgentState) -> Dict[str, Any]:
        """Resolve node references (by name/index to actual node ID)"""

        action = state.get("action")
        if not action or action.get("action") == "none":
            return {}

        diagram = state.get("diagram", {})
        nodes = diagram.get("nodes", [])

        # Resolve node_index if present
        if "node_index" in action and action["node_index"] is not None:
            idx = action["node_index"]
            if 0 <= idx < len(nodes):
                action["node_id"] = nodes[idx]["id"]
                action["resolved_text"] = nodes[idx]["text"]

        # Resolve target if it matches a node name
        if "target" in action and action.get("action") in ["select_node", "delete_node", "update_node"]:
            target = action["target"]

            # Try exact match first
            for node in nodes:
                if node["text"].lower() == target.lower():
                    action["node_id"] = node["id"]
                    action["node_index"] = node["index"]
                    action["resolved_text"] = node["text"]
                    break

            # Try partial match
            if "node_id" not in action:
                for node in nodes:
                    if target.lower() in node["text"].lower() or node["text"].lower() in target.lower():
                        action["node_id"] = node["id"]
                        action["node_index"] = node["index"]
                        action["resolved_text"] = node["text"]
                        break

        return {"action": action}

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        try:
            cleaned = response.strip()

            # Extract JSON from markdown code block
            if '```' in cleaned:
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                if start >= 0 and end > start:
                    cleaned = cleaned[start:end]

            parsed = json.loads(cleaned)
            logger.debug("Successfully parsed JSON response: %s", parsed)
            return parsed

        except Exception as e:
            logger.error("JSON parse error: %s, raw response: %s", e, response)
            return {"action": "none", "confidence": 0.0}

    def update_diagram_state(self, diagram_data: Dict[str, Any]):
        """
        Update the agent's diagram state (called when frontend syncs).
        This keeps the agent always in sync with the current diagram.
        """
        nodes = []
        children = diagram_data.get("children", [])

        for child in children:
            if isinstance(child, dict):
                nodes.append({
                    "id": child.get("id", f"node_{len(nodes)}"),
                    "index": child.get("index", len(nodes)),
                    "text": child.get("text", "")
                })
            elif isinstance(child, str):
                nodes.append({
                    "id": f"node_{len(nodes)}",
                    "index": len(nodes),
                    "text": child
                })

        self._state["diagram"] = {
            "diagram_type": diagram_data.get("diagram_type", self._state["diagram"]["diagram_type"]),
            "center_text": diagram_data.get("center", {}).get("text", ""),
            "nodes": nodes,
            "selected_nodes": diagram_data.get("selected_nodes", [])
        }
        self._state["last_updated"] = datetime.now().isoformat()

        logger.debug("Diagram state updated: %s nodes", len(nodes))

    def update_panel_state(self, active_panel: str, panels: Dict[str, bool] = None):
        """Update panel states"""
        self._state["active_panel"] = active_panel
        if panels:
            self._state["mindmate_open"] = panels.get("mindmate", False)
            self._state["node_palette_open"] = panels.get("node_palette", False)

    async def process_command(
        self,
        user_text: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        voice_session_id: Optional[str] = None,
        diagram_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a voice command and return the action.

        Args:
            user_text: Transcribed user speech
            user_id: User ID for token tracking (optional)
            organization_id: Organization ID for token tracking (optional)
            voice_session_id: Voice session ID for token tracking (optional)
            diagram_type: Diagram type for token tracking (optional)

        Returns:
            Action dict with action type, target, node_id, etc.
        """
        # Store tracking info in state for use in _parse_command_node
        self._state["_tracking_info"] = {
            "user_id": user_id,
            "organization_id": organization_id,
            "voice_session_id": voice_session_id,
            "diagram_type": diagram_type or self._state.get("diagram", {}).get("diagram_type", "unknown")
        }

        # Add user message to state
        self._state["messages"].append(HumanMessage(content=user_text))

        # Run the graph
        try:
            result = await self.graph.ainvoke(self._state, self.config)

            action = result.get("action", {"action": "none", "confidence": 0.0})

            # Store the action in conversation for context
            self._state["messages"].append(
                AIMessage(content=f"Action: {action.get('action', 'none')}")
            )

            # Clean up tracking info from state (temporary data, not part of agent state)
            if "_tracking_info" in self._state:
                del self._state["_tracking_info"]

            return action

        except Exception as e:
            logger.error("Process command error: %s", e, exc_info=True)
            # Clean up tracking info even on error
            if "_tracking_info" in self._state:
                del self._state["_tracking_info"]
            return {"action": "none", "confidence": 0.0, "error": str(e)}

    def get_state(self) -> AgentState:
        """Get current agent state"""
        return self._state

    def clear_history(self):
        """Clear conversation history but keep diagram state"""
        self._state["messages"] = []
        logger.debug("Conversation history cleared")


# ============================================================================
# Agent Manager (Session-based)
# ============================================================================

class VoiceAgentManager:
    """
    Manages VoiceAgent instances per session.
    Each voice session gets its own persistent agent.
    """

    def __init__(self):
        self._agents: Dict[str, VoiceAgent] = {}

    def get_or_create(self, session_id: str) -> VoiceAgent:
        """Get existing agent or create new one for session"""
        if session_id not in self._agents:
            self._agents[session_id] = VoiceAgent(session_id)
            logger.info("Created new VoiceAgent for session %s", session_id)
        return self._agents[session_id]

    def remove(self, session_id: str):
        """Remove agent when session ends"""
        if session_id in self._agents:
            del self._agents[session_id]
            logger.info("Removed VoiceAgent for session %s", session_id)

    def update_diagram(self, session_id: str, diagram_data: Dict[str, Any]):
        """Update diagram state for a session's agent"""
        if session_id in self._agents:
            self._agents[session_id].update_diagram_state(diagram_data)

    def get_agent_count(self) -> int:
        """Get number of active agents"""
        return len(self._agents)


# Global manager instance
voice_agent_manager = VoiceAgentManager()

