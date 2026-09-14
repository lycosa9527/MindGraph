"""Fresh-canvas generate: extract topic and auto_complete without an extra LLM."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.core.prompt_understanding import PreparedGenerationPrompt, prepare_generation_prompt
from services.kitty.routing.one_sentence_edit_heuristics import heuristic_one_sentence_edit_command
from services.utils.ai_content_level import DEFAULT_AI_CONTENT_LEVEL

_BLOCKING_ACTIONS = frozenset(
    {
        "explain_node",
        "add_node",
        "delete_node",
        "update_node",
        "update_center",
        "auto_complete_branch",
        "set_branch_numbering",
        "ask_followup",
        "select_node",
        "clarify_options",
    }
)
_TOPIC_NODE_TYPES = frozenset({"topic", "center"})
_PLACEHOLDER_TOPICS = frozenset(
    {
        "",
        "中心主题",
        "主题",
        "topic",
        "central topic",
        "untitled",
        "未命名",
        "新思维导图",
        "new mind map",
    }
)


def _node_label(node: Dict[str, Any]) -> str:
    raw = node.get("text") or node.get("label")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return ""


def _child_has_label(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    text = item.get("text") or item.get("label")
    return isinstance(text, str) and bool(text.strip())


def is_fresh_diagram(session_context: Dict[str, Any]) -> bool:
    """True when the canvas is create-phase or has no labeled branches."""
    if str(session_context.get("one_sentence_phase") or "").strip() == "create":
        return True
    data = session_context.get("diagram_data")
    if not isinstance(data, dict):
        return True
    children = data.get("children")
    if isinstance(children, list) and any(_child_has_label(item) for item in children):
        return False
    nodes = data.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "").strip().lower()
            node_type = str(node.get("type") or "").strip().lower()
            if node_id in _TOPIC_NODE_TYPES or node_type in _TOPIC_NODE_TYPES:
                continue
            if _node_label(node):
                return False
    return True


def _blocks_fresh_generate(command_text: str) -> bool:
    heuristic = heuristic_one_sentence_edit_command(command_text)
    if heuristic is None:
        return False
    action = str(heuristic.get("action") or "")
    if action in _BLOCKING_ACTIONS:
        return True
    if action in {"set_content_level", "auto_complete"}:
        return True
    return False


def resolve_fresh_diagram_commands(
    command_text: str,
    session_context: Dict[str, Any],
    language: str,
    *,
    prepared: Optional[PreparedGenerationPrompt] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Return set_content_level + auto_complete, or None when this is not a fresh generate."""
    if not is_fresh_diagram(session_context):
        return None
    if _blocks_fresh_generate(command_text):
        return None
    understood = prepared or prepare_generation_prompt(command_text, language)
    topic = (understood.topic_seed or understood.topic_prompt or "").strip()
    if not topic or topic.lower() in _PLACEHOLDER_TOPICS:
        return None
    commands: List[Dict[str, Any]] = []
    session_level = str(session_context.get("ai_content_level") or "").strip()
    if understood.ai_content_level not in {DEFAULT_AI_CONTENT_LEVEL, session_level}:
        commands.append(
            {
                "action": "set_content_level",
                "level": understood.ai_content_level,
                "confidence": 0.95,
            }
        )
    complete: Dict[str, Any] = {"action": "auto_complete", "topic": topic, "confidence": 0.95}
    if understood.is_learning_sheet:
        complete["is_learning_sheet"] = True
    commands.append(complete)
    return commands
