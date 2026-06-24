"""
Agent routing for diagram generation — unified kwargs and fixed-structure priority.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from agents.core.fixed_structure import fixed_labels_from_nodes

AgentRouteMode = Literal[
    "bridge_pairs",
    "bridge_dimension_only",
    "tree_brace_fixed_dimension",
    "dimension_preference",
    "standard",
]

_FIXED_LIST_KEYS: Dict[str, str] = {
    "tree_map": "children",
    "brace_map": "parts",
    "flow_map": "steps",
    "mind_map": "children",
    "mindmap": "children",
}


def has_enforced_fixed_lists(
    diagram_type: str,
    structure_mode: str,
    fixed_nodes: Optional[Dict[str, Any]],
) -> bool:
    """True when Case 2 fixed labels must be enforced for this diagram type."""
    if structure_mode != "fixed":
        return False
    list_key = _FIXED_LIST_KEYS.get(diagram_type)
    if not list_key:
        return False
    labels = fixed_labels_from_nodes(fixed_nodes, list_key)
    return bool(labels)


def _base_tracking_kwargs(
    *,
    user_id: Any,
    organization_id: Any,
    request_type: str,
    endpoint_path: Any,
    phase_emit: Any,
    structure_mode: str,
    fixed_nodes: Optional[Dict[str, Any]],
    constraints: str,
) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "organization_id": organization_id,
        "request_type": request_type,
        "endpoint_path": endpoint_path,
        "phase_emit": phase_emit,
        "structure_mode": structure_mode,
        "fixed_nodes": fixed_nodes or {},
        "constraints": constraints,
    }


@dataclass
class AgentGenerateRoute:
    """Resolved agent invocation mode and keyword arguments."""

    mode: AgentRouteMode
    kwargs: Dict[str, Any]


def resolve_agent_generate_route(
    *,
    diagram_type: str,
    structure_mode: str = "free",
    fixed_nodes: Optional[Dict[str, Any]] = None,
    constraints: str = "",
    fixed_dimension: Optional[str] = None,
    dimension_only_mode: Optional[bool] = None,
    dimension_preference: Optional[str] = None,
    existing_analogies: Optional[list] = None,
    user_id: Any = None,
    organization_id: Any = None,
    request_type: str = "diagram_generation",
    endpoint_path: Any = None,
    phase_emit: Any = None,
) -> AgentGenerateRoute:
    """Choose agent branch; fixed label lists take priority over dimension routing."""
    base = _base_tracking_kwargs(
        user_id=user_id,
        organization_id=organization_id,
        request_type=request_type,
        endpoint_path=endpoint_path,
        phase_emit=phase_emit,
        structure_mode=structure_mode,
        fixed_nodes=fixed_nodes,
        constraints=constraints,
    )

    if has_enforced_fixed_lists(diagram_type, structure_mode, fixed_nodes):
        hint_dimension = fixed_dimension or dimension_preference
        kwargs = dict(base)
        if isinstance(hint_dimension, str) and hint_dimension.strip():
            kwargs["dimension_preference"] = hint_dimension.strip()
        if isinstance(fixed_dimension, str) and fixed_dimension.strip():
            kwargs["fixed_dimension"] = fixed_dimension.strip()
        return AgentGenerateRoute(mode="standard", kwargs=kwargs)

    if diagram_type == "bridge_map" and existing_analogies:
        return AgentGenerateRoute(
            mode="bridge_pairs",
            kwargs={
                **base,
                "existing_analogies": existing_analogies,
                "fixed_dimension": fixed_dimension,
                "dimension_preference": dimension_preference,
            },
        )

    if diagram_type == "bridge_map" and fixed_dimension and not existing_analogies:
        return AgentGenerateRoute(
            mode="bridge_dimension_only",
            kwargs={
                **base,
                "existing_analogies": None,
                "fixed_dimension": fixed_dimension,
                "dimension_preference": dimension_preference,
            },
        )

    if diagram_type in ("tree_map", "brace_map") and fixed_dimension:
        route_kwargs = {
            **base,
            "dimension_preference": fixed_dimension,
            "fixed_dimension": fixed_dimension,
            "dimension_only_mode": bool(dimension_only_mode),
        }
        return AgentGenerateRoute(mode="tree_brace_fixed_dimension", kwargs=route_kwargs)

    if diagram_type in ("brace_map", "tree_map", "bridge_map") and dimension_preference:
        return AgentGenerateRoute(
            mode="dimension_preference",
            kwargs={
                **base,
                "dimension_preference": dimension_preference,
            },
        )

    return AgentGenerateRoute(mode="standard", kwargs=base)
