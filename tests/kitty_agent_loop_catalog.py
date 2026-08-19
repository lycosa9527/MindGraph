"""Catalog of five real mindmaps for Kitty agent-loop action coverage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec

_ROOT = Path(__file__).resolve().parent
_FIXTURES = _ROOT / "fixtures"

MAP_FILES: Tuple[Tuple[str, Path], ...] = (
    ("sams_club", _FIXTURES / "zhihui_sams_club_l1.json"),
    ("photosynthesis", _FIXTURES / "agent_loop_mindmaps" / "photosynthesis.json"),
    ("new_energy_vehicles", _FIXTURES / "agent_loop_mindmaps" / "new_energy_vehicles.json"),
    ("chinese_tea", _FIXTURES / "agent_loop_mindmaps" / "chinese_tea.json"),
    ("beijing_trip", _FIXTURES / "agent_loop_mindmaps" / "beijing_trip.json"),
)

NODE_ACTIONS: Tuple[str, ...] = (
    "add_node",
    "update_node",
    "update_center",
    "delete_node",
    "auto_complete_branch",
    "auto_complete",
    "clarify_options",
)

STRUCTURAL_ACTIONS = frozenset({"add_node", "update_node", "update_center", "delete_node"})


@dataclass(frozen=True, slots=True)
class RealMindmap:
    """Hydrated mindmap plus one L1 branch used as the action target."""

    slug: str
    topic: str
    branch_label: str
    branch_id: str
    context: Dict[str, Any]


def _first_l1_branch(diagram_data: Dict[str, Any]) -> Tuple[str, str]:
    connections = diagram_data.get("connections")
    nodes = diagram_data.get("nodes")
    child_ids: List[str] = []
    if isinstance(connections, list):
        for conn in connections:
            if not isinstance(conn, dict) or conn.get("source") != "topic":
                continue
            target = conn.get("target")
            if isinstance(target, str) and target.strip() and target != "topic":
                child_ids.append(target.strip())
    typed = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    by_id = {str(node.get("id")): node for node in typed if isinstance(node.get("id"), str)}
    for node_id in child_ids:
        node = by_id.get(node_id)
        if not node:
            continue
        label = str(node.get("text") or "").strip()
        if label:
            return node_id, label
    for node in typed:
        if node.get("id") in {None, "topic"}:
            continue
        label = str(node.get("text") or "").strip()
        if label:
            return str(node.get("id")), label
    raise AssertionError("mindmap has no named branch")


def load_real_mindmap(slug: str, path: Path) -> RealMindmap:
    """Hydrate a canvas/spec JSON into one-sentence edit session context."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    live = diagram_data_from_saved_spec(spec, "mindmap")
    topic = ""
    raw_topic = spec.get("topic")
    if isinstance(raw_topic, str) and raw_topic.strip():
        topic = raw_topic.strip()
    elif isinstance(raw_topic, dict):
        text = raw_topic.get("text")
        if isinstance(text, str) and text.strip():
            topic = text.strip()
    center = live.get("center")
    if isinstance(center, dict):
        center_text = center.get("text")
        if isinstance(center_text, str) and center_text.strip():
            topic = center_text.strip()
    if not topic:
        nodes = live.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict) and node.get("id") == "topic":
                    topic = str(node.get("text") or "").strip()
                    break
    if not topic:
        topic = slug
    branch_id, branch_label = _first_l1_branch(live)
    context = {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_data": live,
    }
    return RealMindmap(
        slug=slug,
        topic=topic,
        branch_label=branch_label,
        branch_id=branch_id,
        context=context,
    )


def load_all_real_mindmaps() -> List[RealMindmap]:
    """Load the five committed real mindmaps."""
    maps = [load_real_mindmap(slug, path) for slug, path in MAP_FILES]
    if len(maps) != 5:
        raise AssertionError(f"expected 5 mindmaps, got {len(maps)}")
    return maps


def utterance_for(mmap: RealMindmap, action: str) -> str:
    """Clear typed phrase for one library action against this map."""
    branch = mmap.branch_label
    topic = mmap.topic
    if action == "add_node":
        return "添加一个扩展阅读的分支"
    if action == "update_node":
        return f"把{branch}改成要点提纲"
    if action == "update_center":
        return f"主题改成{topic}导学"
    if action == "delete_node":
        return f"删除{branch}这个分支"
    if action == "auto_complete_branch":
        return f"补全{branch}这个分支"
    if action == "auto_complete":
        return "自动补全导图"
    if action == "clarify_options":
        return f"「{branch}」是要补全还是删掉？"
    raise AssertionError(f"unknown action {action}")


def mock_tool_for(mmap: RealMindmap, action: str) -> Tuple[str, str]:
    """Return (tool_name, arguments_json) the model would send for this action."""
    branch = mmap.branch_label
    uid = mmap.branch_id
    if action == "add_node":
        return "diagram.add_node", json.dumps({"text": "扩展阅读"}, ensure_ascii=False)
    if action == "update_node":
        return "diagram.update_node", json.dumps(
            {"node_identifier": branch, "new_text": "要点提纲"},
            ensure_ascii=False,
        )
    if action == "update_center":
        return "diagram.update_center", json.dumps({"new_text": f"{mmap.topic}导学"}, ensure_ascii=False)
    if action == "delete_node":
        return "diagram.delete_node", json.dumps({"node_identifier": branch}, ensure_ascii=False)
    if action == "auto_complete_branch":
        return "node_action.auto_complete_branch", json.dumps(
            {"node_id": uid, "target": branch},
            ensure_ascii=False,
        )
    if action == "auto_complete":
        return "node_action.auto_complete", "{}"
    if action == "clarify_options":
        payload = {
            "question": "你是想：",
            "options": [
                {"label": f"补全「{branch}」", "action": "auto_complete_branch", "target": branch, "node_id": uid},
                {"label": f"删除「{branch}」", "action": "delete_node", "target": branch, "node_id": uid},
            ],
        }
        return "node_action.clarify_options", json.dumps(payload, ensure_ascii=False)
    raise AssertionError(f"unknown action {action}")
