"""
Best-effort cleanup of in-process workshop editor maps when a user is deleted.

Redis-backed participant/editor state is removed when sessions expire or when
rooms are purged; this hook prevents ghost \"still editing\" entries in the
local ACTIVE_EDITORS map on the worker that served the user.
"""

from __future__ import annotations


def purge_user_from_active_collab(user_id: int) -> None:
    """Remove *user_id* from all ``ACTIVE_EDITORS`` node maps on this worker."""
    from services.features.workshop_ws_connection_state import ACTIVE_EDITORS

    uid = int(user_id)
    for code in list(ACTIVE_EDITORS.keys()):
        room = ACTIVE_EDITORS.get(code)
        if not room:
            continue
        for node_id in list(room.keys()):
            editors = room.get(node_id)
            if not editors:
                continue
            if uid in editors:
                editors.pop(uid, None)
            if not editors:
                del room[node_id]
        if not room:
            del ACTIVE_EDITORS[code]
