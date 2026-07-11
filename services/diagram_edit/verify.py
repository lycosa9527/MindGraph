"""Pure postcondition checks on diagram snapshots (mindmap v1).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional, Set

from services.diagram_edit.types import ExpectedEffect, VerificationReport


def normalize_diagram_text(value: Any) -> str:
    """Trim + Unicode NFKC; case-sensitive compare as stored."""
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFKC", value.strip())


def _node_text(node: Dict[str, Any]) -> str:
    raw = node.get("text")
    if isinstance(raw, str) and raw.strip():
        return normalize_diagram_text(raw)
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str):
            return normalize_diagram_text(label)
    return ""


def _snapshot_nodes_connections(
    evidence: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes_raw = evidence.get("nodes")
    connections_raw = evidence.get("connections")
    nodes = [n for n in nodes_raw if isinstance(n, dict)] if isinstance(nodes_raw, list) else []
    conns = [c for c in connections_raw if isinstance(c, dict)] if isinstance(connections_raw, list) else []
    return nodes, conns


def _topic_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [n for n in nodes if n.get("id") == "topic" or n.get("type") == "topic"]


def verify_mindmap_effect(
    effect: ExpectedEffect,
    evidence: Dict[str, Any],
    *,
    before_node_count: Optional[int] = None,
) -> VerificationReport:
    """Run mindmap postconditions on an after-apply snapshot."""
    nodes, connections = _snapshot_nodes_connections(evidence)
    passed: List[str] = []
    failed: List[str] = []

    def record(check: str, ok: bool) -> None:
        if ok:
            passed.append(check)
        else:
            failed.append(check)

    if effect.op == "update_center":
        topics = _topic_nodes(nodes)
        record("single_topic", len(topics) == 1)
        if effect.text and topics:
            record("topic_text_matches", _node_text(topics[0]) == normalize_diagram_text(effect.text))
        return _report(passed, failed)

    if effect.op == "add_branch":
        record("single_topic", len(_topic_nodes(nodes)) == 1)
        if before_node_count is not None:
            record("delta_nodes", len(nodes) == before_node_count + 1)
        if effect.text:
            matches = [n for n in nodes if _node_text(n) == normalize_diagram_text(effect.text)]
            record("node_exists", len(matches) > 0)
            record("text_matches", len(matches) > 0)
            if matches and effect.parent_ref == "topic":
                new_id = str(matches[-1].get("id") or "")
                has_edge = any(c.get("source") == "topic" and c.get("target") == new_id for c in connections)
                record("parent_edge_exists", has_edge)
        return _report(passed, failed)

    if effect.op == "add_child":
        if before_node_count is not None:
            record("delta_nodes", len(nodes) == before_node_count + 1)
        if effect.text:
            matches = [n for n in nodes if _node_text(n) == normalize_diagram_text(effect.text)]
            record("node_exists", len(matches) > 0)
            record("text_matches", len(matches) > 0)
            if matches:
                new_id = str(matches[-1].get("id") or "")
                has_parent_edge = any(c.get("target") == new_id for c in connections)
                record("parent_edge_exists", has_parent_edge)
        return _report(passed, failed)

    if effect.op == "update_node":
        record("node_count_unchanged", before_node_count is None or len(nodes) == before_node_count)
        if effect.text:
            matches = [n for n in nodes if _node_text(n) == normalize_diagram_text(effect.text)]
            record("text_matches", len(matches) > 0)
            record("node_exists", len(matches) > 0)
        return _report(passed, failed)

    if effect.op == "delete_node":
        if effect.node_identifier:
            ident = normalize_diagram_text(effect.node_identifier)
            absent = not any(n.get("id") == ident or _node_text(n) == ident for n in nodes)
            record("node_absent", absent)
        target_ids: Set[str] = {str(n.get("id") or "") for n in nodes}
        dangling = any(
            c.get("source") not in target_ids or c.get("target") not in target_ids
            for c in connections
            if c.get("source") and c.get("target")
        )
        record("no_dangling_edges", not dangling)
        record("tree_rooted_at_topic", len(_topic_nodes(nodes)) == 1)
        return _report(passed, failed)

    return VerificationReport(ok=False, checks=[], error="unsupported_effect")


def _report(passed: List[str], failed: List[str]) -> VerificationReport:
    if failed:
        return VerificationReport(
            ok=False,
            checks=passed,
            error=f"failed: {', '.join(failed)}",
        )
    return VerificationReport(ok=True, checks=passed)


def extract_created_node_id(
    effect: ExpectedEffect,
    evidence: Dict[str, Any],
    *,
    created_node_ids: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Resolve the canvas id created by an add mutation.

    Prefers explicit ``created_node_ids`` from the owning canvas ack; falls back to
    matching ``effect.text`` in the after-snapshot (last match wins).
    """
    if created_node_ids:
        for item in created_node_ids:
            if isinstance(item, str) and item.strip():
                return item.strip()
    if effect.op not in ("add_branch", "add_child") or not effect.text:
        return None
    nodes, _connections = _snapshot_nodes_connections(evidence)
    want = normalize_diagram_text(effect.text)
    matches = [n for n in nodes if _node_text(n) == want]
    if not matches:
        return None
    new_id = matches[-1].get("id")
    if isinstance(new_id, str) and new_id.strip():
        return new_id.strip()
    return None


def verify_effect_on_snapshot(
    effect: ExpectedEffect,
    evidence: Dict[str, Any],
    *,
    before_node_count: Optional[int] = None,
    diagram_type: str = "mindmap",
) -> VerificationReport:
    """Dispatch verification by diagram type (v1: mindmap only)."""
    if diagram_type not in ("mindmap", "mind_map"):
        return VerificationReport(ok=False, checks=[], error="unsupported_diagram_type")
    return verify_mindmap_effect(effect, evidence, before_node_count=before_node_count)
