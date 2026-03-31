"""Redis TTL for workshop keys derived from diagram session expiry."""

from config.database import SessionLocal
from models.domain.diagrams import Diagram
from services.workshop.workshop_expiry import redis_ttl_seconds_for_expires_at

_FALLBACK_TTL = 86400


def get_workshop_redis_ttl_seconds(diagram_id: str) -> int:
    """TTL to use for ``live_spec`` and related keys (capped, min 1s)."""
    db = SessionLocal()
    try:
        diagram = (
            db.query(Diagram)
            .filter(
                Diagram.id == diagram_id,
                ~Diagram.is_deleted,
            )
            .first()
        )
        if not diagram:
            return _FALLBACK_TTL
        if diagram.workshop_expires_at:
            return redis_ttl_seconds_for_expires_at(diagram.workshop_expires_at)
        return _FALLBACK_TTL
    finally:
        db.close()
