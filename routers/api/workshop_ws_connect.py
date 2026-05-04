"""Post-accept join handshake (participants, editors, user_joined)."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.workshop_ws_connection_state import (
    ACTIVE_EDITORS as active_editors,
    AnyHandle,
    ViewerHandle,
    enqueue,
)
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.online_collab.core.online_collab_status import (
    diagram_title_for_active_workshop,
    online_collab_visibility_for_diagram_id,
)
from services.online_collab.participant.collab_display_name import (
    workshop_collab_member_display_name,
)
from services.online_collab.participant.workshop_join_resume_tokens import (
    mint_join_resume_token_async,
)
from services.online_collab.participant.online_collab_snapshots import (
    websocket_send_live_spec_snapshot,
)
from services.online_collab.participant.online_collab_ws_editor_redis import (
    load_editors,
)

from routers.api.workshop_ws_broadcast import broadcast_to_others
from routers.api.workshop_ws_handlers import build_participants_with_names


def _log_join_parallel_read_failures(exc_group: BaseExceptionGroup) -> None:
    for sub in exc_group.exceptions:
        logger.warning(
            "[CanvasCollabWS] parallel join read failed: %s", sub,
        )


async def _replay_remote_node_editing_states(
    handle: AnyHandle,
    user: Any,
    editor_map: Dict[str, Dict[int, str]],
    user_colors: List[str],
    user_emojis: List[str],
) -> None:
    """
    Send the current node-editing presence state to a joining user.

    All events are batched into a single ``node_editing_batch_ws`` frame so
    a room with many locked nodes does not fire N separate enqueue calls.
    """
    events = []
    for node_id, editors in editor_map.items():
        for editor_user_id, editor_username in editors.items():
            if editor_user_id != user.id:
                color = user_colors[editor_user_id % len(user_colors)]
                emoji = user_emojis[editor_user_id % len(user_emojis)]
                events.append(
                    {
                        "type": "node_editing",
                        "node_id": node_id,
                        "user_id": editor_user_id,
                        "username": editor_username,
                        "editing": True,
                        "color": color,
                        "emoji": emoji,
                    }
                )
    if events:
        await enqueue(
            handle,
            {"type": "node_editing_batch_ws", "events": events},
            "node_editing_batch",
        )


async def send_canvas_collab_join_handshake(
    handle: AnyHandle,
    code: str,
    user: Any,
    diagram_id: str,
    owner_id: Any,
    user_colors: List[str],
    user_emojis: List[str],
) -> None:
    """
    Send joined payload, replay remote editors, broadcast user_joined.

    Runs four independent reads (participants, visibility, editors,
    diagram title) in parallel via ``asyncio.TaskGroup`` so handshake time is
    O(slowest) rather than O(sum). With typical Redis+DB latencies this shaves
    2x-3x off join p95 on cold rooms.
    """
    username = workshop_collab_member_display_name(user)

    participant_ids: List[int] = []
    visibility: Any = None
    editor_map: Dict[str, Dict[int, str]] = {}
    diagram_title: Optional[str] = None

    async def _load_participants() -> None:
        nonlocal participant_ids
        participant_ids = await get_online_collab_manager().get_participants(code)

    async def _load_visibility() -> None:
        nonlocal visibility
        visibility = await online_collab_visibility_for_diagram_id(
            diagram_id, code=code,
        )

    async def _load_editors() -> None:
        nonlocal editor_map
        if is_ws_fanout_enabled():
            editor_map = await load_editors(code)
        else:
            editor_map = active_editors.get(code, {})

    async def _load_diagram_title() -> None:
        nonlocal diagram_title
        diagram_title = await diagram_title_for_active_workshop(str(diagram_id))

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_load_participants())
            tg.create_task(_load_visibility())
            tg.create_task(_load_editors())
            tg.create_task(_load_diagram_title())
    except* Exception as eg:
        if isinstance(eg, BaseExceptionGroup):
            _log_join_parallel_read_failures(eg)

    participants_with_names = await build_participants_with_names(participant_ids)

    joined_payload: Dict[str, Any] = {
        "type": "joined",
        "user_id": user.id,
        "username": username,
        "diagram_id": diagram_id,
        "participants": participant_ids,
        "participants_with_names": participants_with_names,
        "workshop_visibility": visibility,
        "role": handle.role,
    }
    if owner_id is not None:
        joined_payload["owner_id"] = owner_id
    if diagram_title:
        joined_payload["diagram_title"] = diagram_title

    resume_tok = await mint_join_resume_token_async(
        user_id=int(user.id),
        workshop_code_upper=code.strip().upper(),
        diagram_id=str(diagram_id),
    )
    if resume_tok:
        joined_payload["resume_token"] = resume_tok

    await enqueue(handle, joined_payload, "joined")

    try:
        await websocket_send_live_spec_snapshot(handle, code, diagram_id)
    except Exception as snap_exc:
        logger.error(
            "[WorkshopWS] snapshot failed code=%s user=%s: %s",
            code, handle.user_id, snap_exc,
        )
        try:
            await enqueue(
                handle,
                {"type": "error", "message": "snapshot_failed", "code": "snapshot_failed"},
                "error",
            )
        except Exception:
            pass
        raise

    if not isinstance(handle, ViewerHandle):
        await _replay_remote_node_editing_states(
            handle,
            user,
            editor_map,
            user_colors,
            user_emojis,
        )

    await broadcast_to_others(
        code,
        user.id,
        {
            "type": "user_joined",
            "user_id": user.id,
            "username": username,
        },
    )

    logger.info(
        "[WorkshopWS] handshake_ok code=%s user=%s role=%s",
        code, user.id, handle.role,
    )

    await get_online_collab_manager().touch_activity(code)
