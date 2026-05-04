"""Message handlers for canvas collaboration WebSocket (reduces router complexity)."""

import asyncio
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket

from services.features.workshop_ws_connection_state import (
    ACTIVE_EDITORS as active_editors,
    AnyHandle,
    ViewerHandle,
    enqueue,
)
from services.features.workshop_ws_role_change import handle_role_change
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.redis.redis_async_client import get_async_redis
from services.online_collab.spec.online_collab_live_spec import read_live_spec
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_collab_resync,
    record_ws_rate_limit_hit,
    record_ws_resync_rate_limit_check_failure,
)
from services.online_collab.participant.canvas_collab_locks import (
    compute_subtree_node_ids_async,
    node_locked_by_other_user,
)
from services.online_collab.participant.online_collab_snapshots import (
    websocket_send_live_spec_snapshot,
)
from services.online_collab.participant.online_collab_ws_editor_redis import (
    apply_node_editor_batch_delta_redis,
    apply_node_editor_delta_redis,
    claim_node_exclusive_redis,
    load_editors,
)
from services.online_collab.redis.redis8_features import (
    tdigest_record_latency,
)
from services.online_collab.redis.online_collab_redis_keys import (
    resync_rate_limit_key,
)
from services.online_collab.participant.collab_display_name import (
    workshop_collab_member_display_name,
)
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.online_collab.core.online_collab_status import (
    diagram_title_for_active_workshop,
    online_collab_visibility_for_diagram_id,
)
from services.online_collab.participant.workshop_join_resume_tokens import (
    mint_join_resume_token_async,
)
from utils.auth_ws import authenticate_websocket_user
from routers.api.workshop_ws_handlers_update import handle_update as _handle_update

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

from routers.api.workshop_ws_broadcast import broadcast_to_all, broadcast_to_others
from utils.ws_limits import (
    MAX_COLLAB_INBOUND_JSON_DEPTH,
    WORKSHOP_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    collab_json_exceeds_depth,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)


def _collab_jwt_revalidate_interval_sec() -> float:
    raw = os.environ.get("COLLAB_WS_JWT_REVALIDATE_SEC", "180")
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return 180.0
    return parsed if parsed > 0 else 0.0


_NODE_EDIT_DEDUP_WINDOW_SEC = 0.050
_NODE_EDIT_DEDUP_MAX_ENTRIES = 5000
_node_editing_dedup_cache: OrderedDict = OrderedDict()
_NODE_EDIT_DEDUP_EVICT_COUNT = 100

_PARTICIPANTS_WITH_NAMES_CAP = 250

_USERNAME_CACHE_MAX = 10_000
_USERNAME_CACHE_TTL_SEC = 30.0
_username_cache: OrderedDict[int, Tuple[str, float]] = OrderedDict()


def _evict_username_cache() -> None:
    """Drop oldest 10 % of username cache entries when capacity is exceeded."""
    evict_count = max(1, _USERNAME_CACHE_MAX // 10)
    for _ in range(evict_count):
        if _username_cache:
            _username_cache.popitem(last=False)


async def _resolve_participant_name(pid: int) -> Dict[str, Any]:
    """
    Resolve one participant's username with a short-TTL process-local cache.

    Under high join rates (500 users entering a room) repeated individual Redis
    calls for the same user IDs collapse into a single cache read per TTL window
    instead of 250+ concurrent pool checkouts on every join handshake.
    """
    now = time.monotonic()
    cached = _username_cache.get(pid)
    if cached is not None and (now - cached[1]) < _USERNAME_CACHE_TTL_SEC:
        return {"user_id": pid, "username": cached[0]}

    username: str = f"User {pid}"
    if redis_user_cache:
        try:
            participant_user = await redis_user_cache.get_by_id(pid)
            if participant_user:
                username = workshop_collab_member_display_name(participant_user)
        except Exception:
            pass

    if len(_username_cache) >= _USERNAME_CACHE_MAX:
        _evict_username_cache()
    _username_cache[pid] = (username, now)
    return {"user_id": pid, "username": username}


async def build_participants_with_names(
    participant_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    Build ``{user_id, username}`` entries for ``participant_ids`` (parallel).

    Capped at ``_PARTICIPANTS_WITH_NAMES_CAP`` (250) entries to keep the join
    handshake payload bounded in very large rooms. Beyond the cap, the client
    gets the first N plus a sentinel ``_overflow`` entry signalling the total
    count; full name resolution for off-cap participants can be served via a
    paginated ``/api/workshop/participants`` endpoint.

    Usernames are cached process-locally for ``_USERNAME_CACHE_TTL_SEC`` seconds
    so that a burst of 500 participants joining the same room only pays Redis
    round-trips for the first join; subsequent join handshakes resolve from cache.
    """
    if not participant_ids:
        return []
    total = len(participant_ids)
    truncated = total > _PARTICIPANTS_WITH_NAMES_CAP
    effective_ids = (
        participant_ids[:_PARTICIPANTS_WITH_NAMES_CAP]
        if truncated
        else participant_ids
    )
    results = await asyncio.gather(
        *[_resolve_participant_name(pid) for pid in effective_ids],
        return_exceptions=True,
    )
    out: List[Dict[str, Any]] = []
    for pid, res in zip(effective_ids, results):
        if isinstance(res, BaseException):
            out.append({"user_id": pid, "username": f"User {pid}"})
        else:
            out.append(res)
    if truncated:
        logger.info(
            "[CanvasCollabWS] participants list truncated total=%s cap=%s",
            total, _PARTICIPANTS_WITH_NAMES_CAP,
        )
        out.append(
            {
                "user_id": -1,
                "username": f"+{total - _PARTICIPANTS_WITH_NAMES_CAP} more",
                "_overflow": True,
                "_total": total,
            }
        )
    return out


@dataclass
class CollabWsContext:
    """Fixed state for one canvas-collab WebSocket session."""

    code: str
    diagram_id: str
    owner_id: Optional[int]
    user: Any
    rate_limiter: WebsocketMessageRateLimiter
    websocket: WebSocket
    user_colors: List[str]
    user_emojis: List[str]
    handle: Optional[AnyHandle] = None
    jwt_last_revalidated_monotonic: float = 0.0
    authz_last_checked_monotonic: float = 0.0

    @property
    def role(self) -> str:
        """Return the role of this connection ("host", "editor", or "viewer")."""
        if self.handle is not None:
            return self.handle.role
        return "editor"


async def _ctx_send(
    ctx: "CollabWsContext", payload: dict, msg_type: str = "error"
) -> None:
    """Route an outbound frame through handle.enqueue or ws.send_json fallback."""
    if ctx.handle is not None:
        await enqueue(ctx.handle, payload, msg_type)
    else:
        await ctx.websocket.send_json(payload)


async def _handle_ping(ctx: CollabWsContext, _message: Dict[str, Any]) -> None:
    try:
        await get_online_collab_manager().refresh_participant_ttl(
            ctx.code, ctx.user.id,
        )
    except Exception as exc:
        logger.debug("[CanvasCollabWS] ping participant TTL refresh skipped: %s", exc)
    try:
        await get_online_collab_manager().touch_activity(ctx.code)
    except Exception as exc:
        logger.debug("[CanvasCollabWS] ping touch_activity skipped: %s", exc)
    await _ctx_send(ctx, {"type": "pong"}, "pong")


async def _handle_join_repeat(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    join_diagram_id = message.get("diagram_id")
    if (
        isinstance(join_diagram_id, str)
        and join_diagram_id
        and join_diagram_id != ctx.diagram_id
    ):
        logger.warning(
            "[CanvasCollabWS] join_repeat diagram mismatch user=%s code=%s"
            " got=%s expected=%s",
            ctx.user.id, ctx.code, join_diagram_id, ctx.diagram_id,
        )
        await _ctx_send(ctx, {"type": "error", "message": "Diagram ID mismatch"})
        return

    participant_ids = await get_online_collab_manager().get_participants(ctx.code)
    current_username = workshop_collab_member_display_name(ctx.user)
    names = await build_participants_with_names(participant_ids)

    join_repeat: Dict[str, Any] = {
        "type": "joined",
        "user_id": ctx.user.id,
        "username": current_username,
        "diagram_id": ctx.diagram_id,
        "participants": participant_ids,
        "participants_with_names": names,
        "workshop_visibility": await online_collab_visibility_for_diagram_id(
            ctx.diagram_id, code=ctx.code,
        ),
    }
    diag_title = await diagram_title_for_active_workshop(str(ctx.diagram_id))
    if diag_title:
        join_repeat["diagram_title"] = diag_title
    if ctx.owner_id is not None:
        join_repeat["owner_id"] = ctx.owner_id

    resume_tok = await mint_join_resume_token_async(
        user_id=int(ctx.user.id),
        workshop_code_upper=ctx.code.strip().upper(),
        diagram_id=str(ctx.diagram_id),
    )
    if resume_tok:
        join_repeat["resume_token"] = resume_tok

    await _ctx_send(ctx, join_repeat, "joined")
    logger.debug(
        "[CanvasCollabWS] join_repeat_ok user=%s code=%s participants=%d",
        ctx.user.id, ctx.code, len(participant_ids),
    )


_RESYNC_RATE_LIMIT_PER_MIN = 5
_RESYNC_RATE_LIMIT_TTL_SEC = 60


async def _handle_resync(ctx: CollabWsContext, message: Dict[str, Any]) -> None:
    """Send authoritative live spec snapshot (version-gap recovery path)."""
    diag = message.get("diagram_id")
    if diag != ctx.diagram_id:
        logger.warning(
            "[CanvasCollabWS] resync diagram mismatch user=%s code=%s got=%s expected=%s",
            ctx.user.id, ctx.code, diag, ctx.diagram_id,
        )
        await _ctx_send(ctx, {"type": "error", "message": "Diagram ID mismatch"})
        return
    logger.debug(
        "[CanvasCollabWS] resync_start user=%s code=%s diagram=%s role=%s",
        ctx.user.id, ctx.code, ctx.diagram_id, ctx.handle.role,
    )
    redis_rl = get_async_redis()
    if redis_rl:
        rl_key = resync_rate_limit_key(ctx.code.strip().upper(), int(ctx.user.id))
        try:
            count = await redis_rl.incr(rl_key)
            if count == 1:
                await redis_rl.expire(rl_key, _RESYNC_RATE_LIMIT_TTL_SEC)
            if count > _RESYNC_RATE_LIMIT_PER_MIN:
                logger.info(
                    "[CanvasCollabWS] resync rate limited user=%s code=%s count=%s",
                    ctx.user.id, ctx.code, count,
                )
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": "Too many resync requests — wait a moment.",
                    },
                )
                return
        except Exception as exc:
            logger.warning("[CanvasCollabWS] resync rate limit check failed (allowing): %s", exc)
            try:
                record_ws_resync_rate_limit_check_failure()
            except Exception:  # pylint: disable=broad-except
                pass
    try:
        record_ws_collab_resync()
    except Exception as exc:
        logger.debug("record_ws_collab_resync skipped: %s", exc)
    if isinstance(ctx.handle, ViewerHandle):
        try:
            from services.infrastructure.monitoring.ws_metrics import (
                record_ws_viewer_resync,
            )
            record_ws_viewer_resync()
        except Exception:
            pass
    await websocket_send_live_spec_snapshot(ctx.handle, ctx.code, ctx.diagram_id)


async def _handle_node_editing(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    node_id = message.get("node_id")
    raw_editing = message.get("editing", False)
    editing = raw_editing is True or raw_editing == 1
    username = workshop_collab_member_display_name(ctx.user)

    if not node_id or not isinstance(node_id, str) or len(node_id) > 200:
        await _ctx_send(ctx, {"type": "error", "message": "Invalid node_id"})
        return

    dedup_key = f"{ctx.code}:{node_id}:{ctx.user.id}"
    now_ts = asyncio.get_running_loop().time()
    cached = _node_editing_dedup_cache.get(dedup_key)
    if cached is not None:
        prev_editing, prev_ts = cached
        if (
            prev_editing == editing
            and (now_ts - prev_ts) < _NODE_EDIT_DEDUP_WINDOW_SEC
        ):
            logger.debug(
                "[CanvasCollabWS] node_editing duplicate suppressed user=%s node=%s",
                ctx.user.id, node_id,
            )
            return
    while len(_node_editing_dedup_cache) >= _NODE_EDIT_DEDUP_MAX_ENTRIES:
        for _ in range(min(_NODE_EDIT_DEDUP_EVICT_COUNT, len(_node_editing_dedup_cache))):
            _node_editing_dedup_cache.popitem(last=False)
    _node_editing_dedup_cache[dedup_key] = (editing, now_ts)

    room = active_editors.setdefault(ctx.code, {})
    node_editors = room.setdefault(node_id, {})
    if editing:
        node_editors[ctx.user.id] = username
        color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
        emoji = ctx.user_emojis[ctx.user.id % len(ctx.user_emojis)]
    else:
        node_editors.pop(ctx.user.id, None)
        if not node_editors:
            room.pop(node_id, None)
        if not room:
            active_editors.pop(ctx.code, None)
        color = None
        emoji = None

    if is_ws_fanout_enabled():
        ok_redis = await apply_node_editor_delta_redis(
            ctx.code,
            str(node_id),
            int(ctx.user.id),
            bool(editing),
            str(username),
        )
        if not ok_redis:
            logger.warning(
                "[CanvasCollabWS] Redis editor delta failed workshop=%s "
                "user=%s node=%s editing=%s — broadcast proceeds with in-process lock only",
                ctx.code, ctx.user.id, node_id, editing,
            )
            # Do not return: broadcast_to_all must still fire so other participants
            # see the editing animation (dashed outline). The Redis editors map is
            # best-effort soft-lock state; a transient Redis failure degrades lock
            # enforcement to in-process only but must not block the visual signal.

    await broadcast_to_all(
        ctx.code,
        {
            "type": "node_editing",
            "node_id": node_id,
            "user_id": ctx.user.id,
            "username": username,
            "editing": editing,
            "color": color,
            "emoji": emoji,
        },
    )
    logger.debug(
        "[CollabDebug] node_editing user=%s code=%s node_id=%s editing=%s",
        ctx.user.id, ctx.code, node_id, editing,
    )


async def _handle_node_editing_batch(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    """
    Acquire or release an exclusive lock on a whole subtree atomically.

    Client sends ``{"type": "node_editing_batch", "root_node_id": "X",
    "editing": true|false, "op": "subtree"|"explicit", "node_ids": [...]}``.

    For ``op="subtree"`` the server walks the live_spec and computes
    descendants bounded by ``compute_subtree_node_ids_async``. For
    ``op="explicit"`` the client-supplied ``node_ids`` list is used. The
    whole set is then merged into Redis in a single WATCH/MULTI so the
    acquire/release is all-or-nothing.
    """
    raw_root = message.get("root_node_id")
    raw_editing = message.get("editing", False)
    editing = raw_editing is True or raw_editing == 1
    op = message.get("op") or "subtree"
    username = workshop_collab_member_display_name(ctx.user)

    if op not in ("subtree", "explicit"):
        await _ctx_send(ctx, {"type": "error", "message": "Invalid node_editing_batch op"})
        return

    node_ids: List[str] = []
    if op == "subtree":
        if not isinstance(raw_root, str) or not raw_root or len(raw_root) > 200:
            await _ctx_send(ctx, {"type": "error", "message": "Invalid root_node_id"})
            return
        redis_client = get_async_redis()
        try:
            live_doc = (
                await read_live_spec(redis_client, ctx.code)
                if redis_client
                else None
            )
        except Exception as exc:
            logger.debug(
                "[CanvasCollabWS] node_editing_batch: live_spec read failed: %s",
                exc,
            )
            live_doc = None
        node_ids = await compute_subtree_node_ids_async(live_doc, raw_root)
    else:
        raw_ids = message.get("node_ids")
        if not isinstance(raw_ids, list):
            await _ctx_send(
                ctx,
                {"type": "error", "message": "Invalid node_ids for node_editing_batch"},
            )
            return
        node_ids = [
            nid for nid in raw_ids
            if isinstance(nid, str) and nid and len(nid) <= 200
        ][:500]

    if not node_ids:
        await _ctx_send(
            ctx,
            {
                "type": "node_editing_batch",
                "user_id": ctx.user.id,
                "username": username,
                "editing": editing,
                "root_node_id": raw_root if isinstance(raw_root, str) else None,
                "node_ids": [],
            },
            "node_editing_batch",
        )
        return

    color = (
        ctx.user_colors[ctx.user.id % len(ctx.user_colors)] if editing else None
    )
    emoji = (
        ctx.user_emojis[ctx.user.id % len(ctx.user_emojis)] if editing else None
    )

    if is_ws_fanout_enabled():
        effective_ids, ok_redis = await apply_node_editor_batch_delta_redis(
            ctx.code,
            node_ids,
            int(ctx.user.id),
            bool(editing),
            str(username),
        )
        if not ok_redis:
            logger.warning(
                "[CanvasCollabWS] batch editor delta failed workshop=%s "
                "user=%s editing=%s size=%d — broadcasting with full node_ids",
                ctx.code, ctx.user.id, editing, len(node_ids),
            )
            effective_ids = node_ids
    else:
        room = active_editors.setdefault(ctx.code, {})
        effective_ids = []
        for nid in node_ids:
            node_map = room.setdefault(nid, {})
            if editing:
                locked_by_other = any(
                    int(u) != int(ctx.user.id) for u in node_map
                )
                if locked_by_other:
                    continue
                node_map[ctx.user.id] = username
                effective_ids.append(nid)
            else:
                if ctx.user.id not in node_map:
                    continue
                node_map.pop(ctx.user.id, None)
                if not node_map:
                    room.pop(nid, None)
                effective_ids.append(nid)
        if not room:
            active_editors.pop(ctx.code, None)

    await broadcast_to_all(
        ctx.code,
        {
            "type": "node_editing_batch",
            "user_id": ctx.user.id,
            "username": username,
            "editing": editing,
            "color": color,
            "emoji": emoji,
            "root_node_id": raw_root if isinstance(raw_root, str) else None,
            "op": op,
            "node_ids": effective_ids,
        },
    )
    logger.debug(
        "[CollabDebug] node_editing_batch user=%s code=%s editing=%s op=%s node_ids=%s%s",
        ctx.user.id, ctx.code, editing, op,
        effective_ids[:10],
        " (truncated)" if len(effective_ids) > 10 else "",
    )


async def _handle_node_selected(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    node_sel = message.get("node_id")
    selected = bool(message.get("selected", True))
    sel_username = workshop_collab_member_display_name(ctx.user)
    if not node_sel or not isinstance(node_sel, str) or len(node_sel) > 200:
        await _ctx_send(ctx, {"type": "error", "message": "Invalid node_id"})
        return
    sel_color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
    await broadcast_to_others(
        ctx.code,
        ctx.user.id,
        {
            "type": "node_selected",
            "node_id": node_sel,
            "selected": selected,
            "user_id": ctx.user.id,
            "username": sel_username,
            "color": sel_color,
        },
    )
    logger.debug(
        "[CollabDebug] node_selected user=%s code=%s node_id=%s selected=%s",
        ctx.user.id, ctx.code, node_sel, selected,
    )


async def _handle_claim_node_edit(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    """Atomically check and grant/deny exclusive edit ownership of a node.

    The client sends ``claim_node_edit`` before entering edit mode (optimistic
    claim).  The server checks the soft-lock editors map and responds with
    ``node_edit_claimed{granted:true/false}``.  On grant it also broadcasts
    ``node_editing{editing:true}`` to all other participants so the dashed-border
    animation appears immediately without a second round-trip.
    """
    node_id = message.get("node_id")
    if not node_id or not isinstance(node_id, str) or len(node_id) > 200:
        await _ctx_send(ctx, {"type": "error", "message": "Invalid node_id"})
        return

    username = workshop_collab_member_display_name(ctx.user)

    if is_ws_fanout_enabled():
        # Atomic exclusive claim via Lua: no read-check-write race.
        atomic_result = await claim_node_exclusive_redis(
            ctx.code, str(node_id), int(ctx.user.id), username,
        )
        if atomic_result is True:
            room = active_editors.setdefault(ctx.code, {})
            node_editors = room.setdefault(node_id, {})
            node_editors[ctx.user.id] = username
            color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
            emoji = ctx.user_emojis[ctx.user.id % len(ctx.user_emojis)]
            await broadcast_to_all(
                ctx.code,
                {
                    "type": "node_editing",
                    "node_id": node_id,
                    "user_id": ctx.user.id,
                    "username": username,
                    "editing": True,
                    "color": color,
                    "emoji": emoji,
                },
            )
            logger.debug(
                "[CollabDebug] claim_node_edit granted(atomic) user=%s code=%s node=%s",
                ctx.user.id, ctx.code, node_id,
            )
            await _ctx_send(
                ctx,
                {"type": "node_edit_claimed", "node_id": node_id, "granted": True},
                "node_edit_claimed",
            )
            return
        if atomic_result is False:
            logger.debug(
                "[CollabDebug] claim_node_edit denied(atomic) user=%s code=%s node=%s",
                ctx.user.id, ctx.code, node_id,
            )
            await _ctx_send(
                ctx,
                {"type": "node_edit_claimed", "node_id": node_id, "granted": False},
                "node_edit_claimed",
            )
            return
        # atomic_result is None: FCALL unavailable, fall through to read-check-write.

    editors_from_redis: Optional[Dict[str, Dict[int, str]]] = None
    if is_ws_fanout_enabled():
        editors_from_redis = await load_editors(ctx.code)

    is_locked = node_locked_by_other_user(
        ctx.code, int(ctx.user.id), node_id, active_editors, editors_from_redis,
    )

    if is_locked:
        held_by_user_id: Optional[int] = None
        held_by_username: Optional[str] = None
        editors_map = (
            editors_from_redis
            if editors_from_redis is not None
            else active_editors.get(ctx.code, {})
        )
        node_map = editors_map.get(node_id, {})
        for uid, uname in node_map.items():
            if int(uid) != int(ctx.user.id):
                held_by_user_id = int(uid)
                held_by_username = uname
                break
        await _ctx_send(
            ctx,
            {
                "type": "node_edit_claimed",
                "node_id": node_id,
                "granted": False,
                "held_by_user_id": held_by_user_id,
                "held_by_username": held_by_username,
            },
            "node_edit_claimed",
        )
        logger.debug(
            "[CollabDebug] claim_node_edit denied user=%s code=%s node=%s held_by=%s",
            ctx.user.id, ctx.code, node_id, held_by_user_id,
        )
        return

    room = active_editors.setdefault(ctx.code, {})
    node_editors = room.setdefault(node_id, {})
    node_editors[ctx.user.id] = username
    color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
    emoji = ctx.user_emojis[ctx.user.id % len(ctx.user_emojis)]

    if is_ws_fanout_enabled():
        ok_redis = await apply_node_editor_delta_redis(
            ctx.code, str(node_id), int(ctx.user.id), True, str(username),
        )
        if not ok_redis:
            logger.warning(
                "[CanvasCollabWS] claim: Redis editor delta failed workshop=%s user=%s node=%s",
                ctx.code, ctx.user.id, node_id,
            )

    await broadcast_to_all(
        ctx.code,
        {
            "type": "node_editing",
            "node_id": node_id,
            "user_id": ctx.user.id,
            "username": username,
            "editing": True,
            "color": color,
            "emoji": emoji,
        },
    )
    logger.debug(
        "[CollabDebug] claim_node_edit granted user=%s code=%s node=%s",
        ctx.user.id, ctx.code, node_id,
    )
    await _ctx_send(
        ctx,
        {
            "type": "node_edit_claimed",
            "node_id": node_id,
            "granted": True,
        },
        "node_edit_claimed",
    )


_EDITOR_HANDLERS = {
    "ping": _handle_ping,
    "join": _handle_join_repeat,
    "resync": _handle_resync,
    "node_editing": _handle_node_editing,
    "node_editing_batch": _handle_node_editing_batch,
    "node_selected": _handle_node_selected,
    "claim_node_edit": _handle_claim_node_edit,
    "update": _handle_update,
    "role_change": handle_role_change,
}

_VIEWER_HANDLERS = {
    "ping": _handle_ping,
    "resync": _handle_resync,
}

_MSG_HANDLERS = _EDITOR_HANDLERS


async def run_canvas_collab_receive_loop(ctx: CollabWsContext) -> None:
    """Main receive loop until disconnect or error.

    Dispatches to _EDITOR_HANDLERS for host/editor connections and
    _VIEWER_HANDLERS for viewer connections.  Viewer sends of editor-only
    messages (update, node_editing, etc.) are rejected with close code 4015
    without running any validation or DB/Redis logic.
    """
    is_viewer = isinstance(ctx.handle, ViewerHandle)
    handlers = _VIEWER_HANDLERS if is_viewer else _EDITOR_HANDLERS
    while True:
        data = await ctx.websocket.receive_text()
        if inbound_text_exceeds_limit(data, WORKSHOP_MAX_WS_TEXT_BYTES):
            await _ctx_send(ctx, {"type": "error", "message": "Message too large"})
            continue
        if not ctx.rate_limiter.allow():
            try:
                record_ws_rate_limit_hit()
            except Exception as exc:
                logger.debug("Failed to record rate limit metric: %s", exc)
            await _ctx_send(ctx, {"type": "error", "message": "Rate limit exceeded"})
            continue

        now_loop = time.monotonic()
        if now_loop - ctx.authz_last_checked_monotonic >= 5.0:
            ctx.authz_last_checked_monotonic = now_loop
            participants_ok = True
            try:
                participant_ids = await get_online_collab_manager().get_participants(
                    ctx.code,
                )
            except Exception as exc:
                logger.warning(
                    "[CanvasCollabWS] authz participant refresh failed: %s", exc,
                )
                participants_ok = False
                participant_ids = []
            uid_loop = int(getattr(ctx.user, "id", 0))
            # Only revoke when the fetch succeeded — an empty list on Redis error
            # must NOT be treated as "participant not found" or every Redis hiccup
            # would disconnect all active users.
            if participants_ok and participant_ids and uid_loop not in participant_ids:
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": (
                            "You are no longer in this workshop — "
                            "please reconnect."
                        ),
                    },
                )
                await ctx.websocket.close(
                    code=4002,
                    reason="participant membership revoked",
                )
                return

        reval_sec = _collab_jwt_revalidate_interval_sec()
        if reval_sec > 0:
            now_m = time.monotonic()
            if now_m - ctx.jwt_last_revalidated_monotonic >= reval_sec:
                ctx.jwt_last_revalidated_monotonic = now_m
                user_chk, err_chk = await authenticate_websocket_user(ctx.websocket)
                uid_ctx = int(getattr(ctx.user, "id", -1))
                uid_chk = int(getattr(user_chk, "id", -2)) if user_chk else -3
                if err_chk or user_chk is None or uid_chk != uid_ctx:
                    await _ctx_send(
                        ctx,
                        {
                            "type": "error",
                            "message": "Session expired — please reconnect.",
                        },
                    )
                    await ctx.websocket.close(
                        code=4001,
                        reason="Authentication expired",
                    )
                    return

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await _ctx_send(ctx, {"type": "error", "message": "Invalid JSON"})
            continue

        if not isinstance(message, dict):
            await _ctx_send(
                ctx, {"type": "error", "message": "Message must be a JSON object"}
            )
            continue

        if collab_json_exceeds_depth(message, MAX_COLLAB_INBOUND_JSON_DEPTH):
            await _ctx_send(
                ctx,
                {
                    "type": "error",
                    "message": "JSON nesting depth exceeds server limit",
                },
            )
            continue

        msg_type = message.get("type")
        handler = handlers.get(msg_type)
        if handler:
            _t0 = time.perf_counter()
            try:
                await handler(ctx, message)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(
                    "[CanvasCollabWS] handler %s raised: %s", msg_type, exc
                )
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": "Internal error processing message. Please try again.",
                    },
                )
            asyncio.create_task(
                tdigest_record_latency(
                    f"handler:{msg_type}",
                    (time.perf_counter() - _t0) * 1000.0,
                )
            )
            continue

        if is_viewer and msg_type in _EDITOR_HANDLERS:
            await ctx.websocket.close(
                code=4015,
                reason="viewer: not authorized for this message type",
            )
            return

        await _ctx_send(
            ctx, {"type": "error", "message": f"Unknown message type: {msg_type}"}
        )
