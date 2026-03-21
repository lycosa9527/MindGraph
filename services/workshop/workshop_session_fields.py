"""
Workshop DB field helpers (legacy backfill, clearing session columns).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime, timedelta

from models.domain.diagrams import Diagram


def backfill_workshop_expiry_if_needed(diagram: Diagram, db) -> None:
    """Legacy rows: set expiry to 24h from diagram updated_at if missing."""
    if not diagram.workshop_code or diagram.workshop_expires_at is not None:
        return
    started = diagram.updated_at or diagram.created_at or datetime.utcnow()
    diagram.workshop_started_at = started
    diagram.workshop_expires_at = started + timedelta(hours=24)
    diagram.workshop_duration_preset = "legacy"
    db.commit()


def clear_workshop_session_fields(diagram: Diagram) -> None:
    """Clear all workshop-related columns on a diagram row."""
    diagram.workshop_code = None
    diagram.workshop_visibility = None
    diagram.workshop_started_at = None
    diagram.workshop_expires_at = None
    diagram.workshop_duration_preset = None
