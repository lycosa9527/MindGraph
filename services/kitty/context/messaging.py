"""WebSocket messaging and Omni instruction strings for voice."""

import json
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.kitty.session.runtime_state import logger
from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import (
    KITTY_DIAGRAM_CATALOG_PROMPT,
    KITTY_VOICE_COMMAND_PROMPT,
)

_DIAGRAM_HINT_ZH: tuple[str, ...] = (
    "图",
    "导图",
    "圆圈",
    "气泡",
    "流程",
    "括号",
    "桥形",
    "树形",
    "双气泡",
    "类比",
)
_REVIEW_TERM_ZH: tuple[str, ...] = (
    "评价",
    "评估",
    "评析",
    "点评",
    "批改",
)
_IMPROVE_TERM_ZH: tuple[str, ...] = (
    "改进",
    "优化",
    "完善",
    "查漏补缺",
    "修整",
)
_EDU_FACT_ZH: tuple[str, ...] = (
    "教学",
    "教案",
    "课堂",
    "学生",
    "事实",
    "科学",
    "对不对",
    "正确吗",
    "严谨",
    "错误",
)

_ENGLISH_REVIEW_SUBSTRINGS: tuple[str, ...] = (
    "evaluate this diagram",
    "evaluate my diagram",
    "evaluate the diagram",
    "assess this diagram",
    "assess my diagram",
    "diagram evaluation",
    "diagram review",
    "review this diagram",
    "review my diagram",
    "review my mind map",
    "review this mind map",
    "review my map",
    "critique this diagram",
    "critique my diagram",
    "pedagogical",
    "curriculum fit",
    "educationally appropriate",
    "factually correct",
    "fact check",
    "improve this diagram",
    "improve my diagram",
    "improve my map",
)


def user_requests_diagram_pedagogical_review(text: str) -> bool:
    """
    Detect questions asking Kitty to critique, evaluate, improve, or fact-check the diagram.

    When True the realtime Omni session receives the full serialized diagram specification
    inside system instructions before the conversational reply.
    """
    if not isinstance(text, str):
        return False
    trimmed = text.strip()
    if len(trimmed) < 4:
        return False

    lower = trimmed.lower()

    if any(pat in lower for pat in _ENGLISH_REVIEW_SUBSTRINGS):
        return True

    zh_diagram_focus = (
        ("这张" in trimmed or "这幅" in trimmed or "这个" in trimmed)
        and "图" in trimmed
    ) or any(h in trimmed for h in _DIAGRAM_HINT_ZH)

    if not zh_diagram_focus:
        return False

    if any(t in trimmed for t in _REVIEW_TERM_ZH):
        return True
    if any(t in trimmed for t in _IMPROVE_TERM_ZH):
        return True
    if any(t in trimmed for t in _EDU_FACT_ZH):
        return True

    return False


def _diagram_spec_bundle_for_voice_llm(diagram_type: str, diagram_data: Any) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {"diagram_type": diagram_type}
    if isinstance(diagram_data, dict):
        for key, val in diagram_data.items():
            bundle[key] = val
    return bundle


def _serialize_diagram_spec_for_prompt(bundle: Dict[str, Any], max_chars: int) -> str:
    raw = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(raw) <= max_chars:
        return raw
    return f"{raw[: max_chars - 24]}\n…[truncated for length]…"


def _diagram_review_instruction_addon(lang: str, spec_text: str) -> str:
    if lang == "en":
        return f"""

【Complete diagram specification (JSON) — authoritative】
This block is the full diagram payload from the editor (types, topics, nodes, relationships, etc.).
Use it as ground truth when evaluating structure, labels, and links.

```json
{spec_text}
```

【Pedagogical / factual review mode】
When the user asks to evaluate, improve, fact-check, or judge whether the diagram is suitable for
teaching (K12), respond with **clear, structured feedback** (brief summary first, then bullet points).
Check: alignment with the graphic organizer type; clarity for learners; coherence of links;
obvious misconceptions or factual risks. If unsure, explicitly say **you are not certain**.
You may exceed the usual ultra-short reply style for these requests only."""

    return f"""

【完整图示规范（JSON，权威数据源）】
以下为画布导出的图示结构数据（包含类型、主题、节点、连线/关系字段等）。
评价结构、用词、关系时请以此为准。

```json
{spec_text}
```

【教学评析 / 事实核查模式】
当用户希望你**评析、打分、给出改进意见、判断是否适合课堂教学、核对事实是否合理**等时，
可作**结构化、适度展开**的口语回复（先总评再分条），不必强行一两句带过。
关注点：是否符合该图示类型的教学用法；低年级可读性；概念联系是否贴切；是否存在明显史实/科学硬伤。
如对事实不确定请**明说拿不准**。这类请求下可放宽「极简回复」限制。"""


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


async def send_kitty_diagram_update(
    websocket: WebSocket,
    voice_session_id: str,
    message: Dict[str, Any],
) -> bool:
    """
    Send ``diagram_update`` to the mobile Kitty WebSocket and fan out to desktop SSE.

    Desktop canvas applies incremental mutations; it must not reload voice-shaped live_spec.
    """
    sent = await safe_websocket_send(websocket, message)
    if message.get("type") != "diagram_update":
        return sent
    from services.kitty.infra.control.kitty_workflow_trace import (
        kitty_wf_log,
        summarize_diagram_update,
    )
    from services.kitty.infra.desktop.kitty_desktop_wake_fanout import publish_kitty_diagram_update
    from services.kitty.session.runtime_state import voice_sessions

    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return sent
    user_id = sess.get("user_id")
    scope = sess.get("diagram_session_id")
    if user_id is None or not isinstance(scope, str) or not scope.strip():
        return sent
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return sent
    await publish_kitty_diagram_update(uid, scope.strip(), message)
    from services.kitty.infra.desktop.kitty_voice_command_fanout import (
        fanout_voice_command_from_session,
    )

    action_raw = message.get("action")
    if isinstance(action_raw, str) and action_raw.strip():
        act = action_raw.strip()
        kitty_wf_log(
            "ws_out",
            summarize_diagram_update(act, message.get("updates")),
            voice_session_id=voice_session_id,
            scope=scope.strip() if isinstance(scope, str) else None,
            action=act,
        )
        await fanout_voice_command_from_session(
            voice_session_id,
            action_raw.strip(),
            updates=message.get("updates"),
        )
    return sent


def resolve_voice_interaction_language(context: Dict[str, Any]) -> str:
    """Omni instruction language: default Chinese unless client sets English UI."""
    raw = context.get("interaction_language")
    if raw is None:
        return "zh"
    lang = str(raw).strip().lower()
    if lang.startswith("en"):
        return "en"
    return "zh"


def build_voice_instructions(
    context: Dict[str, Any],
    *,
    diagram_review_deep: bool = False,
) -> str:
    """Build voice instructions from context with full diagram data."""
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
    selected_nodes_block = ""
    if isinstance(selected_nodes, list) and selected_nodes:
        selected_lines: List[str] = []
        child_list = children if isinstance(children, list) else []
        for sid in selected_nodes[:3]:
            if not isinstance(sid, str) or not sid.strip():
                continue
            label = sid.strip()
            for node in child_list[:30]:
                if isinstance(node, dict) and node.get("id") == sid.strip():
                    node_text = str(node.get("text") or node.get("label") or "").strip()
                    if node_text:
                        label = f"{node_text!r} (id: {sid.strip()})"
                    else:
                        label = f"id: {sid.strip()}"
                    break
            selected_lines.append(f"  - {label}")
        if selected_lines:
            selected_nodes_block = "\n- Selected nodes:\n" + "\n".join(selected_lines)
    if diagram_review_deep:
        extras = ""
        detail_block = ""
        if children:
            nodes_list = (
                f"\n  ({len(children)} nodes; exact content is in the Complete JSON specification below.)"
            )
        else:
            nodes_list = "\n  (No children array; see JSON for other fields.)"
    else:
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
- Selected nodes: {len(selected_nodes)}{selected_nodes_block}

【Your Capabilities】
You can help with:
1. Answering questions about the diagram content
2. Explaining concepts (e.g., "explain node 1" or "explain ABC")
3. Suggesting new nodes to add
4. Understanding relationships between nodes
5. **EXECUTING CHANGES**: Short spoken confirmation only; the system applies edits from the conversation.

【Important: Executing Changes】
When the user asks to change the diagram, give a **one short sentence** acknowledgment
(e.g. "Done, updating node 1."). The system applies the change; **do not lecture or repeat long examples**.

【Guidelines】
- Simple vocabulary for K12; reference nodes by the text shown in the diagram.

【Voice reply style — like a calm professional voice assistant (Doubao-like)】
- **Default: very short.** Most turns: **one or two sentences**, under ~25 words unless the user asks
  for a longer explanation.
- **Spoken, not essay:** no long intros, fillers ("Let me think"), or repeating the whole question.
- **Direct:** answer first, then optionally one follow-up if helpful.
- Prefer a **neutral, professional** tone; skip enthusiasm padding and emojis.

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
- 已选节点数: {len(selected_nodes)}{selected_nodes_block}

【你能做的事】
1. 回答与图示内容相关的问题
2. 讲解概念（例如「解释第1个节点」或「解释某某」）
3. 建议可以新增哪些节点
4. 帮助理解节点之间的关系
5. **执行修改**：用户口头改图时用**一句话**确认即可，系统会根据对话自动执行。

【关于执行修改】
用户口头改图时：**用一句话确认即可**（例如「好，改第一个节点。」），系统会自动落地；**勿长篇举例、勿反复铺陈**。
按名称或序号对应到具体节点。

【语音回复风格——类似豆包：短、干净、专业】
- **默认极简**：绝大多数回复 **一至两句**，口语控制在约 **40 字以内**；用户明确要求展开时再加长。
- **勿冗长寒暄**：少说「我是你的助手」「让我想想看」；**不重复复述**用户整句话。
- **先答要点**：开门见山；需要时可再补一句点拨。
- 语气稳重、克制，少用堆砌形容词和表情包式语气。

**默认请使用简体中文**进行口语和文字回复；仅当用户**明确**使用其他语言（如英语）时，再用该语言自然回复。"""

    review_addon = ""
    if diagram_review_deep:
        bundle = _diagram_spec_bundle_for_voice_llm(diagram_type, diagram_data)
        spec_text = _serialize_diagram_spec_for_prompt(bundle, 48000)
        review_addon = _diagram_review_instruction_addon(lang, spec_text)

    return (
        instructions
        + review_addon
        + KITTY_DIAGRAM_CATALOG_PROMPT
        + KITTY_VOICE_COMMAND_PROMPT
        + (
            "\n\n【跨设备·桌面画布】若用户要在**电脑/桌面浏览器**新建或打开某种**空白画布**，口头简短确认即可；"
            "类型使用语义 slug（circle_map、bubble_map、double_bubble_map、tree_map、brace_map、"
            "flow_map、multi_flow_map、bridge_map、mindmap、mind_map、concept_map）。"
            "已登录的配对桌面标签页会自行打开对应画布；**手机界面仍停在 Kitty**。"
        )
        if lang != "en"
        else (
            "\n\n【Cross-device desktop canvas】If the user asks to open a **blank** diagram on the **desktop browser**, "
            "confirm briefly; diagram kinds use semantic slugs (circle_map, bubble_map, double_bubble_map, tree_map, "
            "brace_map, flow_map, multi_flow_map, bridge_map, mindmap, mind_map, concept_map). "
            "A signed-in paired desktop tab opens that canvas; **the phone stays on Kitty**."
        )
    )


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
        "circle_map": "你好，我可以帮你补全圆圈图。需要改哪里？",
        "bubble_map": "你好，想加哪些描述？",
        "tree_map": "你好，要怎样分类？",
        "flow_map": "你好，流程上需要我帮什么？",
        "brace_map": "你好，整体与部分需要怎么拆？",
        "bridge_map": "你好，要做哪组类比？",
        "double_bubble_map": "你好，要比较哪两点？",
        "multi_flow_map": "你好，因果上需要理哪一段？",
        "mind_map": "你好，主题是什么？",
        "concept_map": "你好，概念关系哪里不清楚？",
        "default": "你好，我是 Kitty。直接说问题或要改的内容即可。",
    }

    # English greetings
    greetings_en = {
        "circle_map": "Hi. What should we add to your circle map?",
        "bubble_map": "Hi. Which traits should we describe?",
        "tree_map": "Hi. How do you want to sort this?",
        "flow_map": "Hi. What step needs help?",
        "brace_map": "Hi. Which part-whole split should we work on?",
        "bridge_map": "Hi. Which analogy should we map?",
        "double_bubble_map": "Hi. What two things are we comparing?",
        "multi_flow_map": "Hi. Which cause or effect should we clarify?",
        "mind_map": "Hi. What is the topic?",
        "concept_map": "Hi. Which link should we explain?",
        "default": "Hi, I'm Kitty. Say what you need or what to change.",
    }

    greetings = greetings_zh if language == "zh" else greetings_en
    return greetings.get(diagram_type, greetings["default"])
