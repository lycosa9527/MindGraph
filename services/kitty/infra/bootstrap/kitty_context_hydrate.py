"""Merge client Kitty VoiceContext with server-side persisted diagram (library id)."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.infrastructure.monitoring.ws_metrics import record_kitty_hydrate_cache_miss
from services.kitty.infra.desktop.kitty_desktop_focus import get_kitty_desktop_focus_diagram
from services.kitty.infra.bootstrap.kitty_native_spec import native_spec_to_pseudo_nodes
from services.kitty.infra.redis.kitty_session_redis import (
    fetch_kitty_sessionmeta_for_user,
    load_kitty_live_context,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.redis.cache.redis_diagram_cache import get_diagram_cache

logger = logging.getLogger(__name__)


def _node_display_text(node: Dict[str, Any]) -> str:
    text_raw = str(node.get("text") or "").strip()
    if text_raw:
        return text_raw
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
        alt = data.get("text")
        if isinstance(alt, str):
            return alt.strip()
    return ""


def diagram_data_from_saved_spec(spec: Dict[str, Any], diagram_type: str) -> Dict[str, Any]:
    """
    Build VoiceContext-style diagram_data from stored spec (DB/cache shape).

    Prefer client-built payloads when present; this supplies a server-side baseline
    when hydrating from library rows.
    """
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list):
        nodes_raw = []
    children: List[Dict[str, Any]] = []
    vue_nodes: List[Dict[str, Any]] = []
    for index, n in enumerate(nodes_raw):
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or f"n{index}")
        text = _node_display_text(n)
        children.append({"id": nid, "index": len(children), "text": text})
        vue_nodes.append({"id": nid, "text": text, "type": n.get("type")})

    diagram_data: Dict[str, Any] = {
        "diagram_type": diagram_type,
        "children": children,
        "selected_nodes": [],
    }
    if vue_nodes:
        diagram_data["nodes"] = vue_nodes
    if isinstance(spec.get("connections"), list):
        diagram_data["connections"] = spec["connections"]
    if isinstance(spec.get("focus_question"), str) and spec["focus_question"].strip():
        diagram_data["focus_question"] = spec["focus_question"]
    topic = spec.get("topic")
    if isinstance(topic, dict):
        ttext = _node_display_text(topic)
        if ttext:
            diagram_data["center"] = {"text": ttext}
    elif isinstance(spec.get("center"), dict):
        diagram_data["center"] = spec["center"]
    return diagram_data


def diagram_data_from_library_row(cached: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrate ``diagram_data`` from a RedisDiagramCache/DB row (any spec shape)."""
    row_type = str(cached.get("diagram_type") or "circle_map")
    spec = cached.get("spec")
    if not isinstance(spec, dict):
        spec = {}
    pseudo = native_spec_to_pseudo_nodes(spec, row_type)
    if pseudo is None:
        return diagram_data_from_saved_spec(spec, row_type)
    merged_spec = {**spec, "nodes": pseudo}
    return diagram_data_from_saved_spec(merged_spec, row_type)


async def merge_voice_context_with_library(
    user_id: int,
    client_context: Dict[str, Any],
    *,
    diagram_type: str,
    active_panel: str,
    prefer_server_diagram_nodes: bool = False,
) -> Tuple[Dict[str, Any], str, str]:
    """
    Hydrate from RedisDiagramCache/DB when diagram_library_id is set.

    Policy:
    - Server row (when found) supplies title, diagram_type, and baseline diagram_data
      from saved spec.
    - Client wins for selected_nodes (ephemeral).
    - Client diagram_data with non-empty children wins over server baseline for
      node payloads; otherwise server baseline is used.
    - When ``prefer_server_diagram_nodes`` is True and a library row exists, server
      ``children``, ``nodes``, and ``connections`` stay authoritative so desktop-only edits
      remain visible to Kitty without relying on the phone resending canvas state.

    Returns (merged_context, resolved_diagram_type, resolved_active_panel).
    """
    merged = copy.deepcopy(client_context) if client_context else {}
    raw_lib = merged.get("diagram_library_id")
    if raw_lib is not None and not isinstance(raw_lib, str):
        merged["diagram_library_id"] = str(raw_lib).strip()
    library_id = merged.get("diagram_library_id")
    if not library_id or not isinstance(library_id, str) or not library_id.strip():
        merged.setdefault("diagram_data", merged.get("diagram_data") or {})
        return merged, diagram_type, active_panel

    cached: Optional[Dict[str, Any]] = None
    try:
        cached = await get_diagram_cache().get_diagram(user_id, library_id)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        logger.warning("[KittyHydrate] cache/diagram load failed id=%s: %s", library_id, exc)

    if not cached:
        record_kitty_hydrate_cache_miss()
        merged.setdefault("diagram_data", merged.get("diagram_data") or {})
        return merged, diagram_type, active_panel

    row_title = str(cached.get("title") or "").strip()
    row_type = str(cached.get("diagram_type") or diagram_type or "circle_map")

    server_dd = diagram_data_from_library_row(cached)
    client_dd = merged.get("diagram_data")
    if not isinstance(client_dd, dict):
        client_dd = {}

    merged_dd: Dict[str, Any] = {**server_dd}
    skip_keys = {"children"}
    if prefer_server_diagram_nodes:
        skip_keys = {"children", "nodes", "connections"}
    for key, val in client_dd.items():
        if key in skip_keys:
            continue
        merged_dd[key] = val
    if not prefer_server_diagram_nodes:
        client_children = client_dd.get("children")
        if isinstance(client_children, list) and len(client_children) > 0:
            merged_dd["children"] = client_children
    merged["diagram_data"] = merged_dd

    sel = merged.get("selected_nodes")
    if not isinstance(sel, list) and isinstance(client_dd.get("selected_nodes"), list):
        sel = client_dd["selected_nodes"]
    if isinstance(sel, list):
        merged["selected_nodes"] = sel
        merged["diagram_data"]["selected_nodes"] = sel

    if row_title and not str(merged.get("diagram_display_title") or "").strip():
        merged["diagram_display_title"] = row_title

    resolved_type = row_type or diagram_type
    merged["diagram_type"] = resolved_type

    return merged, resolved_type, active_panel


def diagram_data_has_visible_content(diagram_data: Dict[str, Any]) -> bool:
    """True if diagram_data carries at least topic or nodes for Kitty instructions."""
    children = diagram_data.get("children")
    if isinstance(children, list) and len(children) > 0:
        return True
    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list) and len(nodes) > 0:
        return True
    center = diagram_data.get("center")
    if isinstance(center, dict) and str(center.get("text") or "").strip():
        return True
    return False


async def try_build_context_from_live_spec(
    scope: str,
    user_id: int,
) -> Optional[Tuple[Dict[str, Any], str, str]]:
    """
    Build VoiceContext from Redis live_spec when a non-mobile desktop Kitty session owns scope.

    Returns (merged_context, diagram_type, active_panel) or None.
    """
    meta = await fetch_kitty_sessionmeta_for_user(scope, user_id)
    if not meta:
        return None
    if meta.get("client_lane") == "mobile":
        return None
    live = await load_kitty_live_context(scope)
    if not live:
        return None
    raw_dd = live.get("diagram_data")
    if not isinstance(raw_dd, dict):
        return None
    diagram_data = copy.deepcopy(raw_dd)
    if not diagram_data_has_visible_content(diagram_data):
        return None

    diagram_type = str(live.get("diagram_type") or diagram_data.get("diagram_type") or "circle_map")
    active_panel = str(live.get("active_panel") or "none")
    lib_raw = live.get("diagram_library_id")
    library_id = lib_raw if isinstance(lib_raw, str) and lib_raw.strip() else scope

    title_raw = live.get("diagram_display_title")
    diagram_display_title = title_raw if isinstance(title_raw, str) else ""

    selected: List[Any] = []
    sn = live.get("selected_nodes")
    if isinstance(sn, list):
        selected = sn

    merged: Dict[str, Any] = {
        "diagram_data": diagram_data,
        "diagram_type": diagram_type,
        "selected_nodes": selected,
        "diagram_library_id": normalize_kitty_diagram_session_id(library_id) or library_id,
    }
    if diagram_display_title.strip():
        merged["diagram_display_title"] = diagram_display_title.strip()

    diagram_data.setdefault("diagram_type", diagram_type)
    diagram_data["selected_nodes"] = selected

    return merged, diagram_type, active_panel


async def resolve_mobile_open_bootstrap(
    user_id: int,
    *,
    client_suggested_scope: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mobile Kitty preflight: desktop Redis live_spec (non-mobile) then library merge.

    Returns keys: recommended_scope, desktop_focus, context, diagram_type, active_panel,
    source (live | library | empty).
    """
    focus_lib_id, focus_ts = await get_kitty_desktop_focus_diagram(user_id)
    focus_norm = normalize_kitty_diagram_session_id(focus_lib_id) if focus_lib_id else None
    client_norm = normalize_kitty_diagram_session_id(client_suggested_scope) if client_suggested_scope else None

    desktop_focus: Dict[str, Any] = {
        "diagram_library_id": focus_norm,
        "updated_at": focus_ts,
    }

    candidates: List[Tuple[str, int, int]] = []
    seen_scopes: set[str] = set()
    for scope in (client_norm, focus_norm):
        if not scope or scope in seen_scopes:
            continue
        seen_scopes.add(scope)
        meta = await fetch_kitty_sessionmeta_for_user(scope, user_id)
        meta_ts_raw = meta.get("updated_at") if isinstance(meta, dict) else None
        meta_ts = int(meta_ts_raw) if isinstance(meta_ts_raw, int) else -1
        focus_score = int(focus_ts) if (scope == focus_norm and isinstance(focus_ts, int)) else -1
        freshness = max(meta_ts, focus_score)
        focus_rank = 1 if scope == focus_norm else 0
        candidates.append((scope, freshness, focus_rank))

    candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
    for scope, _freshness, _focus_rank in candidates:
        live_out = await try_build_context_from_live_spec(scope, user_id)
        if live_out:
            merged_ctx, dt, panel = live_out
            return {
                "recommended_scope": scope,
                "desktop_focus": desktop_focus,
                "context": merged_ctx,
                "diagram_type": dt,
                "active_panel": panel,
                "source": "live",
            }

    library_id = client_norm or focus_norm
    if library_id:
        merged, dt, panel = await merge_voice_context_with_library(
            user_id,
            {"diagram_library_id": library_id, "diagram_data": {}},
            diagram_type="circle_map",
            active_panel="none",
            prefer_server_diagram_nodes=True,
        )
        try:
            cached = await get_diagram_cache().get_diagram(user_id, library_id)
        except (RuntimeError, ValueError, TypeError, OSError):
            cached = None
        has_row = cached is not None
        has_visible = diagram_data_has_visible_content(merged.get("diagram_data") or {})
        source: str = "library" if has_row or has_visible else "empty"
        return {
            "recommended_scope": library_id,
            "desktop_focus": desktop_focus,
            "context": merged,
            "diagram_type": dt,
            "active_panel": panel,
            "source": source,
        }

    return {
        "recommended_scope": None,
        "desktop_focus": desktop_focus,
        "context": {
            "diagram_data": {},
            "selected_nodes": [],
            "diagram_type": "circle_map",
        },
        "diagram_type": "circle_map",
        "active_panel": "none",
        "source": "empty",
    }
