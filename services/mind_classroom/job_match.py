"""Match a classroom job to the visible LLM diagram variant."""

from __future__ import annotations

from typing import Any, Optional


def job_matches_llm_model(settings: Any, llm_model: Optional[str]) -> bool:
    """True when the lookup is unfiltered, or the job was stored for this LLM."""
    wanted = (llm_model or "").strip()
    if not wanted:
        return True
    if not isinstance(settings, dict):
        return False
    return str(settings.get("llm_model") or "").strip() == wanted


def spec_snapshot_node_ids(spec: Any) -> list[str]:
    """Node ids from the spec the job was generated against."""
    if not isinstance(spec, dict):
        return []
    nodes = spec.get("nodes")
    if not isinstance(nodes, list):
        return []
    ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        if node_id:
            ids.append(node_id)
    return ids


def job_matches_live_nodes(job_node_ids: Any, live_ids: set[str]) -> bool:
    """True when a majority of the job's snapshot ids are still on the canvas."""
    if not isinstance(job_node_ids, list) or not job_node_ids:
        return False
    cleaned = [str(node_id).strip() for node_id in job_node_ids if str(node_id).strip()]
    if not cleaned:
        return False
    hits = sum(1 for node_id in cleaned if node_id in live_ids)
    return hits * 2 >= len(cleaned)


def playable_result_json(result_json: Any) -> bool:
    """True when Postgres still has lecture steps and COS has not superseded them."""
    if not isinstance(result_json, dict):
        return False
    if result_json.get("transcript_replaced") is True:
        return False
    steps = result_json.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("caption") or "").strip():
            return True
    return False


def classroom_ready_job_reusable(
    *,
    spec_hash: str,
    wanted_hash: str,
    spec_node_ids: Any,
    live_ids: set[str],
    result_json: Any,
) -> bool:
    """Ready/partial reuse: stored script exists and still binds to the live map."""
    if not playable_result_json(result_json):
        return False
    if wanted_hash and spec_hash == wanted_hash:
        return True
    return job_matches_live_nodes(spec_node_ids, live_ids)
