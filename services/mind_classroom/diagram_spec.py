"""Load a library mind-map spec for classroom jobs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select

from models.domain.diagrams import Diagram
from services.diagram.mindmap_identity import migrate_mindmap_diagram_payload
from services.diagram.thinking_map_identity import migrate_thinking_map_diagram_payload
from services.diagram.thinking_map_patterns import is_thinking_map_diagram_type
from utils.db.session_open import system_rls_session


async def load_owned_diagram_spec(diagram_id: str, user_id: int) -> dict[str, Any]:
    """Return spec JSON for a mind map owned by the user."""
    cleaned = (diagram_id or "").strip()
    if not cleaned:
        raise ValueError("diagram_id required")
    async with system_rls_session() as db:
        result = await db.execute(select(Diagram).where(Diagram.id == cleaned, ~Diagram.is_deleted))
        diagram = result.scalar_one_or_none()
    if diagram is None:
        raise ValueError("Diagram not found")
    if diagram.user_id != int(user_id):
        raise PermissionError("Diagram does not belong to user")
    spec = deepcopy(diagram.spec) if isinstance(diagram.spec, dict) else {}
    if not spec.get("type") and diagram.diagram_type:
        spec = {**spec, "type": diagram.diagram_type}
    if not spec.get("nodes"):
        raise ValueError("Diagram spec has no nodes")
    diagram_type = str(spec.get("type") or diagram.diagram_type or "")
    if diagram_type in {"mindmap", "mind_map"}:
        migrate_mindmap_diagram_payload(spec)
    elif is_thinking_map_diagram_type(diagram_type):
        migrate_thinking_map_diagram_payload(spec, diagram_type)
    return spec
