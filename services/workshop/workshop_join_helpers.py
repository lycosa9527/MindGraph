"""Helpers for joining a workshop (Redis restore from DB)."""

from datetime import datetime
from typing import Any

from models.domain.diagrams import Diagram
from services.workshop.workshop_redis_keys import code_to_diagram_key, session_key


def restore_workshop_redis_from_db_row(
    redis: Any,
    code: str,
    diagram_id: str,
    diagram: Diagram,
    ttl: int,
) -> None:
    """Re-seed Redis session + code_to_diagram after a DB fallback lookup."""
    redis.setex(
        code_to_diagram_key(code),
        ttl,
        diagram_id,
    )
    session_data = {
        "diagram_id": diagram_id,
        "owner_id": str(diagram.user_id),
        "created_at": (
            diagram.workshop_started_at.isoformat()
            if diagram.workshop_started_at
            else datetime.utcnow().isoformat()
        ),
    }
    redis.setex(
        session_key(code),
        ttl,
        str(session_data),
    )
