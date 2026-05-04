"""
Ensure at most one hosted online-collab workshop per owning user.

When starting a session on diagram D, any other diagram owned by the same
user that still carries a workshop code is torn down via the normal owner
stop path (flush + fan-out kick + Redis purge).

Parallel starts on two diagrams for the same owner can race briefly; a
diagram-scoped NX start lock partially serialises contention. Further
cross-diagram guarding can be layered later if QA finds duplicate codes.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram

logger = logging.getLogger(__name__)


async def stop_other_owner_online_collabs(
    *,
    owner_user_id: int,
    except_diagram_id: str,
) -> int:
    """
    Stop every hosted workshop owned by ``owner_user_id`` except ``except_diagram_id``.

    Delegates each stop to ``stop_online_collab_impl`` so semantics match manual
    host stop (including zombie-ish rows that still retain ``workshop_code``).

    Returns
    -------
    int
        Count of diagrams for which ``stop_online_collab_impl`` returned ``True``.
    """
    from services.online_collab.core.online_collab_lifecycle import (
        stop_online_collab_impl,
    )

    ids_to_stop: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Diagram.id, Diagram.workshop_code).where(
                    Diagram.user_id == owner_user_id,
                    ~Diagram.is_deleted,
                    Diagram.id != except_diagram_id,
                    Diagram.workshop_code.isnot(None),
                )
            )
            for rid, wc in result.all():
                if wc is not None and str(wc).strip():
                    ids_to_stop.append(str(rid))
    except SQLAlchemyError as exc:
        logger.warning(
            "[OnlineCollabMgr] stop_other_owner_collabs: listing failed "
            "user=%s except=%s: %s",
            owner_user_id,
            except_diagram_id,
            exc,
        )
        return 0

    stopped_ok = 0
    for other_id in ids_to_stop:
        try:
            finished = await stop_online_collab_impl(other_id, owner_user_id)
        except (SQLAlchemyError, OSError, RuntimeError) as exc:
            logger.warning(
                "[OnlineCollabMgr] stop_other_collabs: stop failed "
                "diagram_id=%s user=%s: %s",
                other_id,
                owner_user_id,
                exc,
            )
            continue
        if finished:
            stopped_ok += 1
    if ids_to_stop:
        logger.info(
            "[OnlineCollabMgr] single-owner cleanup user=%s target=%s "
            "candidates=%d stopped_ok=%d",
            owner_user_id,
            except_diagram_id,
            len(ids_to_stop),
            stopped_ok,
        )
    return stopped_ok
