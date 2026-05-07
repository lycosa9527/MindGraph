"""WebSocket messaging and Omni instruction strings for voice."""

from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from routers.features.voice.state import logger


def _diagram_extras_for_instructions(diagram_type: str, diagram_data: Dict[str, Any]) -> str:
    """Serialize type-specific fields from diagram_data for Omni (critique / Q&A)."""
    lines: List[str] = []

    ctx = diagram_data.get("context")
    if isinstance(ctx, list) and ctx:
        chunk = [str(x) for x in ctx[:12]]
        extra = ""
        if len(ctx) > 12:
            extra = f", … (+{len(ctx) - 12} more)"
        lines.append(f"- Context ring: {', '.join(chunk)}{extra}")

    attrs = diagram_data.get("attributes")
    if isinstance(attrs, list) and attrs:
        texts: List[str] = []
        for item in attrs[:18]:
            if isinstance(item, dict):
                raw = item.get("text") or item.get("label")
                if raw is not None:
                    texts.append(str(raw))
            elif item is not None:
                texts.append(str(item))
        if texts:
            show = texts[:12]
            tail = ""
            if len(texts) > 12:
                tail = f", … (+{len(texts) - 12} more)"
            lines.append(f"- Attribute bubbles: {', '.join(show)}{tail}")

    if diagram_type == "double_bubble_map":
        left = diagram_data.get("left") or ""
        right = diagram_data.get("right") or ""
        if left or right:
            lines.append(f"- Compared topics: left={left!r}, right={right!r}")

    if diagram_type in ("flow_map", "multi_flow_map"):
        title_key = "title" if diagram_type == "flow_map" else "event"
        val = diagram_data.get(title_key)
        if val:
            readable = title_key.replace("_", " ").title()
            lines.append(f"- {readable}: {val}")

    analogies = diagram_data.get("analogies")
    if isinstance(analogies, list) and analogies:
        for i, entry in enumerate(analogies[:10]):
            if isinstance(entry, dict):
                left = entry.get("left", "")
                right = entry.get("right", "")
                lines.append(f"- Analogy {i + 1}: {left!r} : {right!r}")
        if len(analogies) > 10:
            lines.append(f"- … (+{len(analogies) - 10} more analogy pairs)")

    if diagram_type == "brace_map":
        dim = diagram_data.get("dimension")
        if dim:
            lines.append(f"- Brace dimension label: {dim}")

    if diagram_type == "tree_map":
        dim = diagram_data.get("dimension")
        if dim:
            lines.append(f"- Sorting dimension: {dim}")

    fq = diagram_data.get("focus_question")
    if isinstance(fq, str) and fq.strip():
        lines.append(f"- Focus question: {fq.strip()}")

    rc = diagram_data.get("root_concept")
    if isinstance(rc, str) and rc.strip():
        lines.append(f"- Root concept: {rc.strip()}")

    rels = diagram_data.get("relationships")
    if isinstance(rels, list) and rels:
        lines.append("- Concept relationships:")
        for i, rel in enumerate(rels[:18]):
            if isinstance(rel, dict):
                src = rel.get("from", "")
                dst = rel.get("to", "")
                label = rel.get("label", "")
                lines.append(f'  * {i}: "{src}" —{label}→ "{dst}"')
        if len(rels) > 18:
            lines.append(f"  * … (+{len(rels) - 18} more)")

    return "\n".join(lines)


async def safe_websocket_send(websocket: WebSocket, message: Dict[str, Any]) -> bool:
    """
    Safely send a message via WebSocket, checking if connection is still open.

    Returns:
        True if message was sent successfully, False if WebSocket is closed
    """
    try:
        # Check WebSocket state - FastAPI WebSocket has client_state attribute
        if hasattr(websocket, "client_state"):
            # WebSocketState enum: CONNECTING, CONNECTED, DISCONNECTED
            if websocket.client_state.name == "DISCONNECTED":
                logger.debug("WebSocket is disconnected, skipping send")
                return False
        await websocket.send_json(message)
        return True
    except (RuntimeError, ConnectionError, AttributeError) as e:
        # Handle various WebSocket closed errors
        if "close" in str(e).lower() or "closed" in str(e).lower():
            logger.debug("WebSocket closed, cannot send message: %s", e)
            return False
        # Re-raise other exceptions
        logger.error("Error sending WebSocket message: %s", e)
        raise


def resolve_voice_interaction_language(context: Dict[str, Any]) -> str:
    """Omni instruction language: default Chinese unless client sets English UI."""
    raw = context.get("interaction_language")
    if raw is None:
        return "zh"
    lang = str(raw).strip().lower()
    if lang.startswith("en"):
        return "en"
    return "zh"


def build_voice_instructions(context: Dict[str, Any]) -> str:
    """Build voice instructions from context with full diagram data"""
    diagram_type = context.get("diagram_type", "unknown")
    active_panel = context.get("active_panel", "mindmate")
    selected_nodes = context.get("selected_nodes", [])
    diagram_data = context.get("diagram_data", {})

    # Extract center topic based on diagram type
    center_text = ""
    if diagram_type == "double_bubble_map":
        left = diagram_data.get("left", "")
        right = diagram_data.get("right", "")
        if left and right:
            center_text = f"{left} 和 {right}"
        elif left:
            center_text = left
        elif right:
            center_text = right
    elif diagram_type == "flow_map":
        center_text = diagram_data.get("title", "")
    elif diagram_type == "multi_flow_map":
        center_text = diagram_data.get("event", "")
    elif diagram_type == "brace_map":
        center_text = diagram_data.get("whole", "")
    elif diagram_type == "tree_map":
        topic_raw = diagram_data.get("topic", "")
        center_text = str(topic_raw) if topic_raw else ""
        if not center_text:
            ctr = diagram_data.get("center")
            if isinstance(ctr, dict):
                center_text = str(ctr.get("text", "") or "")
    elif diagram_type == "bridge_map":
        center_text = diagram_data.get("dimension", "")
    else:
        # Default: most diagrams use center.text
        ctr = diagram_data.get("center")
        if isinstance(ctr, dict):
            center_text = str(ctr.get("text", "") or "")
        elif ctr:
            center_text = str(ctr)

    children = diagram_data.get("children", [])
    extras = _diagram_extras_for_instructions(diagram_type, diagram_data)

    # Format nodes list for Omni to understand (with IDs for precise selection)
    nodes_list = ""
    if children:
        for i, node in enumerate(children[:15]):  # Limit to 15 nodes
            if isinstance(node, str):
                nodes_list += f'\n  {i + 1}. "{node}"'
            elif isinstance(node, dict):
                node_id = node.get("id", f"node_{i}")
                text = node.get("text") or node.get("label") or str(node)
                nodes_list += f'\n  {i + 1}. "{text}" (id: {node_id})'
        if len(children) > 15:
            nodes_list += f"\n  ... and {len(children) - 15} more nodes"

    detail_block = ""
    if extras:
        detail_block = f"\n【Type-specific detail】\n{extras}"

    library_id = context.get("diagram_library_id")
    display_title = (context.get("diagram_display_title") or "").strip()
    doc_suffix = ""
    if library_id:
        doc_suffix += f"\n- Saved diagram id: {library_id}"
    if display_title:
        doc_suffix += f'\n- Display title: "{display_title}"'

    lang = resolve_voice_interaction_language(context)
    if lang == "en":
        instructions = f"""You are a helpful K12 classroom AI assistant for MindGraph.

【Current Diagram】
- Type: {diagram_type}
- Center topic: {center_text or "Not set"}
- Nodes ({len(children)} total):{nodes_list if nodes_list else " None"}{detail_block}{doc_suffix}

【Current State】
- Active panel: {active_panel}
- Selected nodes: {len(selected_nodes)}

【Your Capabilities】
You can help with:
1. Answering questions about the diagram content
2. Explaining concepts (e.g., "explain node 1" or "explain ABC")
3. Suggesting new nodes to add
4. Understanding relationships between nodes
5. **EXECUTING CHANGES**: When users ask you to make changes (e.g., "change the first node to X",
   "update the center to Y", "add a node called Z", "delete node ABC"), you should acknowledge
   and confirm the change. The system will automatically execute these changes based on your
   conversation.

【Important: Executing Changes】
When users request changes conversationally (e.g., "can you change...", "please update...",
"I want to change..."), acknowledge the request clearly. Examples:
- "Change the first node to apples" → Acknowledge: "好的，我会把第一个节点改成'苹果'。" (The system will execute this automatically)
- "Update center to cars" → Acknowledge: "好的，我会把中心主题改成'汽车'。" (The system will execute this automatically)
- "Add a node called fruits" → Acknowledge: "好的，我会添加一个叫'水果'的节点。" (The system will execute this automatically)

When user mentions a node by name or number, you know exactly which one they mean.
For example, if user says "select ABC" and ABC is node 3, you understand they want node 3.

【Guidelines】
- Be concise and helpful
- Use simple vocabulary for K12 students
- Reference specific nodes by their content
- Encourage critical thinking
- **When users ask for changes, acknowledge clearly** - the system will execute them automatically

**Default to English** for spoken and written replies; if the user clearly uses another language
(e.g. Chinese), respond in that language naturally."""

    else:
        instructions = f"""你是 MindGraph 面向 K12 课堂的智能助手。

【当前图示】
- 类型: {diagram_type}
- 中心主题: {center_text or "未设置"}
- 节点（共 {len(children)} 个）:{nodes_list if nodes_list else " 无"}{detail_block}{doc_suffix}

【当前状态】
- 活动面板: {active_panel}
- 已选节点数: {len(selected_nodes)}

【你能做的事】
1. 回答与图示内容相关的问题
2. 讲解概念（例如「解释第1个节点」或「解释某某」）
3. 建议可以新增哪些节点
4. 帮助理解节点之间的关系
5. **执行修改**：当用户口头要求改图（例如「把第一个节点改成苹果」「把中心改成汽车」
   「加一个名字叫水果的节点」「删掉某某节点」）时，你要清楚确认；系统会根据对话自动执行。

【关于执行修改】
当用户用自然口语提出修改时，要用简短话语明确确认，例如：
- 「把第一个节点改成苹果」→ 可回复：「好的，我会把第一个节点改成「苹果」。」（随后由系统自动执行）
- 「把中心改成汽车」→ 「好的，我会把中心主题改成「汽车」。」
- 「加一个水果节点」→ 「好的，我会添加一个叫「水果」的节点。」

用户按名称或序号提到节点时，你要对应到具体节点；例如用户说「选 ABC」而 ABC 是第 3 个节点，你就知道指的是节点 3。

【表达要求】
- 简明、友好，用词适合中小学生
- 引用节点时用图示里的实际文字
- 适当引导思考
- 用户要求改图时务必先口头确认，系统会自动落地修改

**默认请使用简体中文**进行口语和文字回复；仅当用户**明确**使用其他语言（如英语）时，再用该语言自然回复。"""

    return instructions


def parse_double_bubble_target(target: str) -> Optional[Dict[str, str]]:
    """
    Parse target text for double bubble map into left/right fields.

    Handles common patterns:
    - "A和B" (Chinese: A and B)
    - "A与B" (Chinese: A and B, alternative)
    - "A vs B" (English: A versus B)
    - "A and B" (English: A and B)
    - "A/B" (Slash separator)
    - "A 和 B" (with spaces)

    Args:
        target: Target text to parse

    Returns:
        Dict with 'left' and 'right' keys if parsing successful, None otherwise
    """
    if not target or not isinstance(target, str):
        return None

    target = target.strip()

    # Try different separators in order of likelihood
    separators = [
        "和",  # Chinese: and
        "与",  # Chinese: and (alternative)
        " vs ",  # English: versus (with spaces)
        " vs",  # English: versus (space before)
        "vs ",  # English: versus (space after)
        "vs",  # English: versus (no spaces)
        " and ",  # English: and (with spaces)
        " and",  # English: and (space before)
        "and ",  # English: and (space after)
        " and",  # English: and (space before, lowercase)
        "and",  # English: and (no spaces)
        "/",  # Slash separator
        "|",  # Pipe separator
    ]

    for sep in separators:
        if sep in target:
            parts = target.split(sep, 1)  # Split only on first occurrence
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()
                if left and right:
                    return {"left": left, "right": right}

    # If no separator found, return None (parsing failed)
    return None


def build_greeting_message(diagram_type: str = "unknown", language: str = "zh") -> str:
    """
    Build personalized greeting message based on diagram type and language.

    Args:
        diagram_type: Type of diagram (circle_map, bubble_map, etc.)
        language: Language code ('zh' or 'en')

    Returns:
        Greeting message string
    """
    # Chinese greetings
    greetings_zh = {
        "circle_map": "你好！我是你的思维助手。我可以帮你完善圆圈图，探索更多观察和想法。有什么我可以帮你的吗？",
        "bubble_map": "嗨！我来帮你描述事物的特征。告诉我你想添加什么形容词或特点吧！",
        "tree_map": "你好！我可以帮你整理分类。让我们一起把想法分门别类吧！",
        "flow_map": "嗨！我来帮你梳理流程。告诉我每一步的顺序，我会协助你理清思路！",
        "brace_map": "你好！我可以帮你分析整体与部分的关系。让我们一起探索吧！",
        "bridge_map": "嗨！我来帮你找出事物之间的类比关系。准备好了吗？",
        "double_bubble_map": "你好！我可以帮你比较两个事物。告诉我它们的相同点和不同点吧！",
        "multi_flow_map": "嗨！我来帮你分析因果关系。让我们一起找出原因和结果！",
        "mind_map": "你好！我是你的思维导图助手。告诉我你的主题，我会帮你展开更多想法！",
        "concept_map": "嗨！我来帮你理清概念之间的关系。让我们一起建立知识网络吧！",
        "default": "你好！我是你的AI助手，很高兴为你服务。你可以问我任何关于思维图的问题，或者让我帮你更新图表内容。",
    }

    # English greetings
    greetings_en = {
        "circle_map": (
            "Hi! I'm your thinking assistant. I can help you enhance your Circle Map "
            "with more observations and ideas. How can I help?"
        ),
        "bubble_map": (
            "Hello! I'm here to help you describe things. Tell me what adjectives or characteristics you want to add!"
        ),
        "tree_map": ("Hi! I can help you organize by categories. Let's classify your ideas together!"),
        "flow_map": ("Hello! I'm here to help you map processes. Tell me the sequence, and I'll help you clarify!"),
        "brace_map": ("Hi! I can help you analyze whole-part relationships. Let's explore together!"),
        "bridge_map": ("Hello! I'm here to help you find analogies. Ready to compare?"),
        "double_bubble_map": ("Hi! I can help you compare two things. Tell me their similarities and differences!"),
        "multi_flow_map": ("Hello! I'm here to help you analyze cause and effect. Let's find the reasons and results!"),
        "mind_map": ("Hi! I'm your mind map assistant. Tell me your topic, and I'll help you brainstorm ideas!"),
        "concept_map": ("Hello! I'm here to help you connect concepts. Let's build a knowledge network together!"),
        "default": (
            "Hello! I'm your AI assistant, happy to help. Ask me anything about your diagram, "
            "or let me help you update it."
        ),
    }

    greetings = greetings_zh if language == "zh" else greetings_en
    return greetings.get(diagram_type, greetings["default"])
