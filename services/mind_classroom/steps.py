"""Shared lecture step schema and spec-id validation."""

from __future__ import annotations

from typing import Any, Optional

from services.diagram.mindmap_identity import identity_aliases, remap_id_list, remap_optional_id

MAX_STEPS_DEFAULT = 40
_KINDS = frozenset({"overview", "branch", "closing"})


def collect_spec_node_ids(spec: dict[str, Any]) -> set[str]:
    """Collect live node ids plus uid / legacy aliases from a mind-map spec."""
    nodes = spec.get("nodes")
    if not isinstance(nodes, list):
        return set()
    typed = [node for node in nodes if isinstance(node, dict)]
    return set(identity_aliases(typed).keys())


def normalize_step(raw: Any, *, known_ids: set[str], index: int) -> Optional[dict[str, Any]]:
    """Coerce one LLM/frame step; drop unknown focus ids."""
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "branch").strip().lower()
    if kind not in _KINDS:
        kind = "branch"
    title = str(raw.get("title") or "").strip()
    caption = str(raw.get("caption") or raw.get("teacher_script") or "").strip()
    if not caption and not title:
        return None
    bullets_raw = raw.get("bullets")
    bullets: list[str] = []
    if isinstance(bullets_raw, list):
        for item in bullets_raw:
            text = str(item or "").strip()
            if text:
                bullets.append(text)
            if len(bullets) >= 8:
                break
    focus_raw = raw.get("focus_node_ids") or raw.get("focusNodeIds")
    focus_ids: list[str] = []
    if isinstance(focus_raw, list):
        for item in focus_raw:
            node_id = str(item or "").strip()
            if node_id and (not known_ids or node_id in known_ids):
                focus_ids.append(node_id)
    branch_raw = raw.get("branch_node_id") or raw.get("branchNodeId")
    branch_id = str(branch_raw).strip() if branch_raw else ""
    if branch_id and known_ids and branch_id not in known_ids:
        branch_id = ""
    image_url = str(raw.get("image_url") or raw.get("imageUrl") or "").strip()
    step_id = str(raw.get("id") or f"{kind}-{index}").strip() or f"{kind}-{index}"
    return {
        "id": step_id[:80],
        "kind": kind,
        "title": title[:256] or caption[:80],
        "caption": caption[:4000],
        "bullets": bullets,
        "focus_node_ids": focus_ids,
        "branch_node_id": branch_id or None,
        "image_url": image_url or None,
    }


def normalize_steps(
    raw_steps: Any,
    *,
    spec: dict[str, Any],
    max_steps: int = MAX_STEPS_DEFAULT,
) -> list[dict[str, Any]]:
    """Validate and cap a step list against the spec snapshot."""
    if not isinstance(raw_steps, list):
        return []
    nodes_raw = spec.get("nodes")
    typed = [node for node in nodes_raw if isinstance(node, dict)] if isinstance(nodes_raw, list) else []
    aliases = identity_aliases(typed)
    known = set(aliases.keys())
    cap = max(1, int(max_steps))
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        if len(out) >= cap:
            break
        step = normalize_step(raw, known_ids=known, index=index)
        if step is not None:
            step["focus_node_ids"] = remap_id_list(step.get("focus_node_ids"), aliases)
            remapped_branch = remap_optional_id(step.get("branch_node_id"), aliases)
            if remapped_branch is not None:
                step["branch_node_id"] = remapped_branch
            out.append(step)
    return out


def filter_live_focus(steps: list[dict[str, Any]], live_ids: set[str]) -> list[dict[str, Any]]:
    """Drop focus ids that are no longer on the live canvas."""
    filtered: list[dict[str, Any]] = []
    for step in steps:
        focus = [node_id for node_id in (step.get("focus_node_ids") or []) if node_id in live_ids]
        branch = step.get("branch_node_id")
        if isinstance(branch, str) and branch and branch not in live_ids:
            branch = None
        next_step = dict(step)
        next_step["focus_node_ids"] = focus
        next_step["branch_node_id"] = branch
        filtered.append(next_step)
    return filtered
