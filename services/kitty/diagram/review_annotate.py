"""
Structured diagram review for Kitty voice: annotate nodes needing edits (ids + reasons).

Uses a compact LLM JSON pass paired with heuristic resolution to vue-flow ``node_id`` values.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Tuple

from services.llm import llm_service

logger = logging.getLogger(__name__)

_MAX_NODES_LLM = 12
_PROMPT_SOFT_CAP = 42_000


def _diagram_payload_for_inventory(diagram_type: str, diagram_data: Dict[str, Any]) -> Dict[str, Any]:
    """Diagram payload for inventory."""
    base = dict(diagram_data)
    base["diagram_type"] = diagram_type
    raw = json.dumps(base, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(raw) <= _PROMPT_SOFT_CAP:
        return base
    children = base.get("children")
    trimmed = dict(base)
    if isinstance(children, list) and len(children) > 80:
        trimmed["children"] = children[:80]
        trimmed["_truncated_children"] = len(children) - 80
    rel = trimmed.get("relationships")
    if isinstance(rel, list) and len(rel) > 60:
        trimmed["relationships"] = rel[:60]
        trimmed["_truncated_relationships"] = len(rel) - 60
    return trimmed


def _flatten_id_text_pairs(diagram_data: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Flatten id text pairs."""
    pairs: List[Tuple[str, str]] = []

    children = diagram_data.get("children")
    if isinstance(children, list):
        for ch in children:
            if isinstance(ch, dict):
                nid = ch.get("id")
                txt = ch.get("text") or ch.get("label") or ""
                if isinstance(nid, str) and nid:
                    pairs.append((nid, str(txt).strip()))

    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for item in nodes:
            if isinstance(item, dict):
                nid = item.get("id")
                txt = item.get("text") or ""
                if isinstance(nid, str) and nid and not any(p[0] == nid for p in pairs):
                    pairs.append((nid, str(txt).strip()))

    return pairs


def _norm(s: str) -> str:
    """Norm."""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _resolve_node_id(
    _diagram_data: Dict[str, Any],
    raw_id: Any,
    text_hint: Any,
    pairs: List[Tuple[str, str]],
) -> str | None:
    """Resolve node id."""
    if isinstance(raw_id, str) and raw_id.strip():
        nid = raw_id.strip()
        if any(p[0] == nid for p in pairs):
            return nid

    hint = ""
    if isinstance(text_hint, str):
        hint = text_hint.strip()
    nh = _norm(hint)
    if nh:
        for nid, lbl in pairs:
            if nh == _norm(lbl):
                return nid
            if nh and nh in _norm(lbl):
                return nid
            if _norm(lbl) and _norm(lbl) in nh and len(_norm(lbl)) >= 2:
                return nid
    return None


def _parse_llm_json(text: str) -> Dict[str, Any]:
    """Parse llm json."""
    cleaned = text.strip()
    if "```" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if 0 <= start < end:
            cleaned = cleaned[start:end]
    return json.loads(cleaned)


async def compute_kitty_diagram_review_annotations(
    user_text: str,
    *,
    diagram_type: str,
    diagram_data: Dict[str, Any],
    user_id: int | None = None,
    organization_id: int | None = None,
    voice_session_id: str | None = None,
) -> Dict[str, Any]:
    """
    Produce ``summary`` + ``items`` (node_id, reason, suggestion?) for websocket ``diagram_review_annotation``.

    Args:
        user_text: Transcribed or typed Kitty user message (review request).
        diagram_type: Canonical slug (e.g. circle_map).
        diagram_data: Voice session ``diagram_data`` (merged from Redis/live).

    Returns:
        Dict with keys ``summary`` (str), ``items`` (list of dicts), optional ``warn`` (str).
    """
    payload_preview = _diagram_payload_for_inventory(diagram_type, diagram_data or {})
    inv_pairs = _flatten_id_text_pairs(diagram_data if isinstance(diagram_data, dict) else {})
    inv_lines = [f"- id={nid!r} text={txt!r}" for nid, txt in inv_pairs[:200]]

    lang_note = (
        "If the user's message is primarily English, write summary/reason/suggestion fields in "
        "English; if primarily Chinese, use Simplified Chinese."
    )

    prompt = (
        "You review K12 instructional diagrams for teaching quality and factual plausibility.\n"
        f"{lang_note}\n"
        "Return ONLY a JSON object of this shape (no markdown):\n"
        '{"summary":"2-4 sentences overall","nodes":['
        '{"node_id":"<exact id from inventory or empty string>","node_text":"'
        '<optional label substring to match>","reason":"why this node/content is problematic or '
        'should change for teaching/clarity/facts","suggestion":"specific optional fix"}'
        f"]}}\n"
        "Rules:\n"
        f"- Prefer at most {_MAX_NODES_LLM} nodes.\n"
        '- node_id MUST be copied exactly from the inventory when known; otherwise use "" '
        "and rely on node_text.\n"
        '- Be precise; if unsure about facts say so briefly in "reason" (do not invent '
        "citations).\n"
        "- Omit trivial cosmetic issues unless they confuse learners.\n\n"
        f"User question:\n{user_text}\n\n"
        "Diagram payload (truncated if huge):\n"
        f"{json.dumps(payload_preview, ensure_ascii=False, default=str)}\n\n"
        "Node id/text inventory:\n" + ("\n".join(inv_lines) if inv_lines else "(no enumerated nodes)")
    )

    empty: Dict[str, Any] = {"summary": "", "items": []}

    try:
        response = await llm_service.chat(
            prompt=prompt,
            model="qwen-plus",
            temperature=0.2,
            max_tokens=2000,
            timeout=35.0,
            user_id=user_id,
            organization_id=organization_id,
            request_type="kitty_diagram_review_annotation",
            diagram_type=diagram_type or None,
            session_id=voice_session_id,
            endpoint_path="/ws/kitty",
            use_knowledge_base=False,
        )
        parsed = _parse_llm_json(response or "{}")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("[KittyDiagramReview] JSON parse failed: %s", exc)
        return {**empty, "warn": "parse_error"}
    except (RuntimeError, ConnectionError, TimeoutError, OSError) as exc:
        logger.error("[KittyDiagramReview] LLM transport error: %s", exc, exc_info=True)
        return {**empty, "warn": "llm_error"}

    summary = parsed.get("summary")
    summary_str = summary.strip() if isinstance(summary, str) else ""

    raw_nodes = parsed.get("nodes")
    if not isinstance(raw_nodes, list):
        raw_nodes = []

    items: List[Dict[str, Any]] = []
    for raw in raw_nodes[:_MAX_NODES_LLM]:
        if not isinstance(raw, dict):
            continue
        nid = _resolve_node_id(diagram_data, raw.get("node_id"), raw.get("node_text"), inv_pairs)
        if not nid:
            continue
        reason = raw.get("reason")
        sug = raw.get("suggestion")
        reason_str = reason.strip() if isinstance(reason, str) else ""
        if not reason_str:
            continue
        entry: Dict[str, Any] = {"node_id": nid, "reason": reason_str}
        if isinstance(sug, str) and sug.strip():
            entry["suggestion"] = sug.strip()
        items.append(entry)

    return {"summary": summary_str, "items": items}
