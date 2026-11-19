"""Keep every bound pair on the slide the open course is showing.

The instructor's computer publishes the slide. Glasses bound to that user, and
to the organization the course is running for, follow it. A tap asks the
instructor to advance, then every pair speaks the slide the course lands on.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.domain.auth import User
from models.domain.learning_space import GlassesWearerBind
from models.domain.training import TrainingCourse
from services.features.training.courses.constants import optional_glasses_line, optional_glasses_reveal
from services.features.training.play_advance import resolve_play_cursor
from services.features.training.session_store import get_session
from services.features.training.storage.backend import get_bytes
from services.learning_space.glasses_contract import sheet_id_from_payload
from services.learning_space.glasses_events import publish_glasses_event
from services.redis.redis_client import get_redis
from services.utils.error_types import REDIS_ERRORS
from utils.db.session_open import system_rls_session

KEY_PREFIX = "mg:glasses:play:"
CURSOR_PREFIX = "mg:glasses:cursor:"
FOLLOW_PREFIX = "mg:glasses:follow:"
VOICE_CUE_PREFIX = "mg:glasses:voice-cue:"
TTL_SECONDS = 30
CURSOR_TTL_SECONDS = 1800
VOICE_CUE_TTL_SECONDS = 20
PLAY_CONTINUE = "请点击继续"
PLAY_NOT_STARTED = "老师还没开始上课，请等待"
PLAY_STARTED = "老师已开始上课，请稍候"
PLAY_OVER = "课程已结束，这是最后一页"
PLAY_DONE = PLAY_OVER
VOICE_PREFIX = "/api/learning-space/glasses/voice?"


def play_key(user_id: int) -> str:
    """Redis slot for the latest slide cue of one account."""
    return f"{KEY_PREFIX}{int(user_id)}"


def cursor_key(user_id: int) -> str:
    """Where this account is in the course the glasses are playing."""
    return f"{CURSOR_PREFIX}{int(user_id)}"


def follow_key(user_id: int) -> str:
    """The slide the computer wants these glasses to show."""
    return f"{FOLLOW_PREFIX}{int(user_id)}"


def store_play(redis: Any, user_id: int, body: dict[str, Any]) -> bool:
    """Keep the newest cue. False when Redis refuses."""
    if redis is None:
        return False
    try:
        redis.set(play_key(user_id), json.dumps(body, ensure_ascii=False), ex=TTL_SECONDS)
    except REDIS_ERRORS:
        return False
    return True


def take_play(redis: Any, user_id: int) -> dict[str, Any] | None:
    """Read and clear the cue. None is the idle case."""
    if redis is None:
        return None
    key = play_key(user_id)
    try:
        raw = redis.get(key)
        redis.delete(key)
    except REDIS_ERRORS:
        return None
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def load_cursor(redis: Any, user_id: int) -> dict[str, Any] | None:
    """The playback cursor, or None when this account has not started a course."""
    if redis is None:
        return None
    try:
        raw = redis.get(cursor_key(user_id))
    except REDIS_ERRORS:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _json_object(raw: Any) -> dict[str, Any] | None:
    """One JSON object from Redis, or None when the slot is empty or not an object."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def read_follow(redis: Any, user_id: int) -> dict[str, Any] | None:
    """The slide waiting for the glasses. None means the computer has not started a course."""
    if redis is None:
        return None
    try:
        raw = redis.get(follow_key(user_id))
    except REDIS_ERRORS:
        return None
    return _json_object(raw)


def write_follow(redis: Any, user_id: int, body: dict[str, Any]) -> bool:
    """Replace the slide the glasses should show. False when Redis refuses."""
    if redis is None:
        return False
    try:
        redis.set(follow_key(user_id), json.dumps(body, ensure_ascii=False), ex=CURSOR_TTL_SECONDS)
    except REDIS_ERRORS:
        return False
    return True


def next_follow_seq(redis: Any, user_id: int) -> int:
    """The sequence number of the next slide the glasses have not shown yet."""
    current = read_follow(redis, user_id)
    if current is None:
        return 1
    return _as_int(current.get("seq"), 0) + 1


def clear_cursor(redis: Any, user_id: int) -> None:
    """Forget the slide after the course stops."""
    if redis is None:
        return
    try:
        redis.delete(cursor_key(user_id))
    except REDIS_ERRORS:
        return


def play_target_user(state: dict[str, Any] | None, wearer_id: int) -> int:
    """A live course tap reaches the instructor. A preview tap stays with the wearer."""
    if not isinstance(state, dict):
        return wearer_id
    instructor = state.get("instructor_id")
    if isinstance(instructor, bool) or not isinstance(instructor, int) or instructor <= 0:
        return wearer_id
    return instructor


def save_cursor(
    redis: Any,
    user_id: int,
    course_id: str,
    cursor: dict[str, Any],
    instructor_id: int = 0,
) -> None:
    """Remember the slide and who may advance it."""
    if redis is None:
        return
    body: dict[str, Any] = {
        "course_id": course_id,
        "index": int(cursor["index"]),
        "mark": int(cursor["mark"]),
        "read": int(cursor["read"]),
    }
    if instructor_id > 0:
        body["instructor_id"] = int(instructor_id)
    try:
        redis.set(cursor_key(user_id), json.dumps(body), ex=CURSOR_TTL_SECONDS)
    except REDIS_ERRORS:
        return


def _as_int(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return int(value)


def encode_recording(audio: bytes) -> str:
    """The recording carried in the play response, so the glasses do not fetch it again."""
    return base64.standard_b64encode(audio).decode("ascii")


def queue_voice_cue(redis: Any, user_id: int, course_id: str, index: int) -> bool:
    """Ask the bound glasses to play this slide's recording. False when Redis refuses."""
    if redis is None or index < 0:
        return False
    body = json.dumps({"course_id": course_id, "index": int(index)})
    try:
        redis.set(f"{VOICE_CUE_PREFIX}{int(user_id)}", body, ex=VOICE_CUE_TTL_SECONDS)
    except REDIS_ERRORS:
        return False
    return True


def take_voice_cue(redis: Any, user_id: int) -> tuple[str, int] | None:
    """The recording the editor just asked the glasses to play. None is idle."""
    if redis is None:
        return None
    key = f"{VOICE_CUE_PREFIX}{int(user_id)}"
    try:
        raw = redis.get(key)
        redis.delete(key)
    except REDIS_ERRORS:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    course_id = str(parsed.get("course_id") or "")
    index = parsed.get("index")
    if not course_id or isinstance(index, bool) or not isinstance(index, int) or index < 0:
        return None
    return course_id, index


def glasses_voice_path(course_id: str, index: int) -> str:
    """Relative address of one slide's recording. The glasses add their bind token."""
    return f"{VOICE_PREFIX}course={course_id}&index={int(index)}"


def play_cue(payload: dict[str, Any], course_id: str, position: int) -> dict[str, Any]:
    """The line and reveal the builder applies for one stored step."""
    line = optional_glasses_line(payload.get("glasses_line")) or PLAY_CONTINUE
    reveal = optional_glasses_reveal(payload.get("glasses_reveal"))
    cue = {
        "course_id": course_id,
        "position": position,
        "reveal": reveal,
        "display": line,
    }
    voice = payload.get("voice_url")
    if isinstance(voice, str) and voice.startswith(VOICE_PREFIX):
        cue["voice"] = voice
    return cue


def _visible(course: TrainingCourse, owner: int) -> bool:
    """A system course plays for any bound account. Any other course plays for its owner."""
    if course.is_system:
        return True
    return course.owner_id == owner


async def _bound_owner_id(token: str) -> int | None:
    """Account id for a wearer token, or None when the glasses are not bound."""
    token_id = sheet_id_from_payload(token) or (token or "").strip()
    if len(token_id) != 36:
        return None
    async with system_rls_session() as db:
        result = await db.execute(select(GlassesWearerBind).where(GlassesWearerBind.id == token_id))
        row = result.scalar_one_or_none()
    if row is None or row.bound_at is None:
        return None
    return int(row.owner_user_id)


async def _load_course_steps(owner: int, course_id: str) -> list[dict[str, Any]] | None:
    """Ordered slide payloads, or None when this account cannot play the course."""
    rows = await _course_rows(owner, course_id)
    if rows is None:
        return None
    return [payload for payload, _voice_key in rows]


async def take_queued_recording(token: str) -> bytes | None:
    """The recording the editor queued for these glasses, or None when nothing is waiting."""
    owner = await _bound_owner_id(token)
    if owner is None:
        return None
    cue = take_voice_cue(get_redis(), owner)
    if cue is None:
        return None
    course_id, index = cue
    return await glasses_voice_bytes(token, course_id, index)


def _follow_allows(packet: dict[str, Any] | None, course_id: str, index: int) -> bool:
    """The instructor already published this slide to these glasses."""
    if not isinstance(packet, dict) or not packet.get("active"):
        return False
    return str(packet.get("course_id") or "") == course_id and _as_int(packet.get("position"), -1) == index


async def glasses_voice_bytes(token: str, course_id: str, index: int) -> bytes | None:
    """The slide recording for a bound pair, or None when there is nothing to play."""
    if index < 0:
        return None
    owner = await _bound_owner_id(token)
    if owner is None:
        return None
    shared = _follow_allows(read_follow(get_redis(), owner), course_id, index)
    rows = await _course_rows(owner, course_id, shared=shared)
    if rows is None or index >= len(rows):
        return None
    voice_key = rows[index][1]
    if not voice_key:
        return None
    return await get_bytes(voice_key)


async def _bound_org_ids(organization_id: int) -> list[int]:
    """Accounts in this organization whose glasses have finished binding."""
    if organization_id <= 0:
        return []
    async with system_rls_session() as db:
        result = await db.execute(
            select(GlassesWearerBind.owner_user_id)
            .join(User, User.id == GlassesWearerBind.owner_user_id)
            .where(
                GlassesWearerBind.bound_at.is_not(None),
                User.organization_id == int(organization_id),
            )
        )
        return [int(row) for row in result.scalars().all()]


async def _course_rows(
    owner: int,
    course_id: str,
    *,
    shared: bool = False,
) -> list[tuple[dict[str, Any], str]] | None:
    """Each slide payload, and the object key of its recording when one was saved."""
    async with system_rls_session() as db:
        result = await db.execute(
            select(TrainingCourse)
            .where(TrainingCourse.id == course_id)
            .options(selectinload(TrainingCourse.steps), selectinload(TrainingCourse.assets))
        )
        course = result.scalar_one_or_none()
        if course is None or not (shared or _visible(course, owner)):
            return None
        ordered = sorted(course.steps, key=lambda row: row.position)
        assets = {asset.id: asset.logical_key or "" for asset in course.assets}
        rows: list[tuple[dict[str, Any], str]] = []
        for index, row in enumerate(ordered):
            payload = dict(row.payload or {})
            voice_id = str(payload.get("voice_asset_id") or "")
            voice_key = assets.get(voice_id, "")
            if voice_key:
                payload["voice_url"] = glasses_voice_path(course_id, index)
            rows.append((payload, voice_key))
    return rows


def _cue_for_cursor(
    steps: list[dict[str, Any]],
    course_id: str,
    cursor: dict[str, int],
    *,
    action: str,
    slide_changed: bool,
) -> dict[str, Any]:
    """What the builder applies, and the line the glasses speak."""
    index = cursor["index"]
    payload = steps[index] if 0 <= index < len(steps) else {}
    base = play_cue(payload, course_id, index)
    if action == "next" and not slide_changed:
        base["display"] = PLAY_CONTINUE
        base["reveal"] = ""
        base.pop("voice", None)
    base["action"] = action
    base["mark_step"] = cursor["mark"]
    base["read_index"] = cursor["read"]
    return base


def _follow_packet(
    seq: int,
    *,
    active: bool,
    done: bool,
    cue: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The slide record the glasses poll. Audio is attached later, not stored."""
    source = cue or {}
    return {
        "seq": seq,
        "active": active,
        "done": done,
        "course_id": str(source.get("course_id") or ""),
        "position": _as_int(source.get("position"), 0),
        "display": str(source.get("display") or ""),
        "reveal": str(source.get("reveal") or ""),
        "voice": bool(source.get("voice")),
    }


async def _slide_audience(user_id: int, organization_id: int, course_id: str, *, clearing: bool) -> list[int]:
    """Who hears this slide. A live course reaches every bound pair in the organization."""
    if organization_id <= 0:
        return [user_id]
    session = await get_session(organization_id)
    instructor = int(session.get("instructor_id") or 0) if isinstance(session, dict) else 0
    state = str(session.get("state") or "") if isinstance(session, dict) else ""
    if instructor != int(user_id):
        if state in {"live", "paused"}:
            return []
        return [user_id]
    playing = str(session.get("course_id") or "") if isinstance(session, dict) else ""
    if not clearing and playing and playing != course_id:
        return [user_id]
    owners = await _bound_org_ids(organization_id)
    if user_id not in owners:
        owners.append(user_id)
    return owners


def _write_slide(
    redis: Any,
    caller: int,
    owners: list[int],
    packet: dict[str, Any],
    course_id: str,
    cursor: dict[str, Any] | None,
    instructor_id: int,
) -> bool:
    """Store one slide for each bound account. False when the caller's own write fails."""
    wrote_caller = False
    for owner in owners:
        seq = next_follow_seq(redis, owner)
        body = dict(packet)
        body["seq"] = seq
        if not write_follow(redis, owner, body):
            if owner == caller:
                return False
            continue
        if cursor is None:
            clear_cursor(redis, owner)
        else:
            save_cursor(redis, owner, course_id, cursor, instructor_id)
        if owner == caller:
            wrote_caller = True
    return wrote_caller


async def publish_glasses_slide(
    user_id: int,
    course_id: str,
    index: int,
    mark: int,
    read: int,
    *,
    done: bool,
    organization_id: int = 0,
) -> bool:
    """Tell the bound glasses which slide the computer is showing. False when that fails."""
    redis = get_redis()
    clearing = index < 0 or not course_id
    owners = await _slide_audience(user_id, organization_id, course_id, clearing=clearing)
    if not owners:
        return True
    if clearing:
        packet = _follow_packet(0, active=False, done=True)
        wrote = _write_slide(redis, user_id, owners, packet, "", None, 0)
        if wrote:
            await _notify_follow(owners)
        return wrote
    steps = await _load_course_steps(user_id, course_id)
    if steps is None or index >= len(steps):
        return False
    previous = load_cursor(redis, user_id)
    same_slide = (
        isinstance(previous, dict)
        and previous.get("course_id") == course_id
        and _as_int(previous.get("index"), -1) == index
    )
    cursor = {"index": index, "mark": mark, "read": read}
    cue = _cue_for_cursor(
        steps,
        course_id,
        cursor,
        action="open",
        slide_changed=not same_slide,
    )
    if same_slide or done:
        cue.pop("voice", None)
    if done:
        cue["display"] = PLAY_DONE
    packet = _follow_packet(0, active=True, done=done, cue=cue)
    instructor = user_id if organization_id > 0 else 0
    wrote = _write_slide(redis, user_id, owners, packet, course_id, cursor, instructor)
    if wrote:
        await _notify_follow(owners)
    return wrote


async def _notify_follow(owners: list[int]) -> None:
    """Wake each bound pair so it fetches the slide once."""
    for owner in owners:
        await publish_glasses_event(owner, "follow")


async def glasses_owner_id(token: str) -> int | None:
    """Account id for a wearer token, or None when the glasses are not bound."""
    return await _bound_owner_id(token)


async def glasses_follow_view(token: str, since: int) -> dict[str, Any] | None:
    """The slide the computer published after ``since``. None when nothing is new."""
    owner = await _bound_owner_id(token)
    if owner is None:
        return None
    packet = read_follow(get_redis(), owner)
    if packet is None or _as_int(packet.get("seq"), 0) <= since:
        return None
    body = {
        "ok": True,
        "seq": _as_int(packet.get("seq"), 0),
        "active": bool(packet.get("active")),
        "done": bool(packet.get("done")),
        "display": str(packet.get("display") or ""),
        "reveal": str(packet.get("reveal") or ""),
        "position": _as_int(packet.get("position"), 0),
    }
    if packet.get("voice") and body["active"]:
        audio = await glasses_voice_bytes(token, str(packet.get("course_id") or ""), body["position"])
        if audio:
            body["voice_b64"] = encode_recording(audio)
    return body


async def enqueue_glasses_play(token: str, payload: str) -> dict[str, Any]:
    """A tap asks the computer to advance. The glasses speak the slide the computer then shows."""
    if (payload or "").strip() != "next":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown play code")
    owner = await _bound_owner_id(token)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glasses are not bound")
    redis = get_redis()
    loaded = load_cursor(redis, owner)
    state = loaded if isinstance(loaded, dict) else {}
    course_id = str(state.get("course_id") or "")
    if not course_id:
        return {"ok": True, "accepted": False, "notice": "waiting", "display": PLAY_NOT_STARTED}
    if await _tap_is_finished(owner, state):
        return {"ok": True, "accepted": False, "notice": "over", "display": PLAY_OVER}
    cue = {"action": "next", "course_id": course_id, "position": _as_int(state.get("index"), 0)}
    target = play_target_user(state, owner)
    if not store_play(redis, target, cue):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Play queue is unavailable")
    await publish_glasses_event(target, "play")
    return {"ok": True, "accepted": True, "notice": "started", "display": PLAY_STARTED}


def cursor_is_finished(steps: list[dict[str, Any]], index: int, mark: int, read: int) -> bool:
    """True when another tap would stay on this slide. That slide is the end of the course."""
    if not steps:
        return False
    at = min(max(index, 0), len(steps) - 1)
    live = dict(steps[at])
    live["mark_step"] = mark
    interact = live.get("interact")
    if isinstance(interact, dict):
        copied = dict(interact)
        copied["play_index"] = read
        live["interact"] = copied
    nxt, nxt_mark, nxt_read = resolve_play_cursor(steps, at, live, 1)
    landed = 0 if nxt_read is None else int(nxt_read)
    return (nxt, nxt_mark, landed) == (at, mark, read)


async def _tap_is_finished(owner: int, state: dict[str, Any]) -> bool:
    """The open course has nowhere left to go from this cursor."""
    course_id = str(state.get("course_id") or "")
    steps = await _load_course_steps(owner, course_id)
    if not steps:
        return False
    return cursor_is_finished(
        steps,
        _as_int(state.get("index"), 0),
        _as_int(state.get("mark"), 1),
        _as_int(state.get("read"), 0),
    )


async def drain_glasses_play(user_id: int) -> dict[str, Any]:
    """The cue waiting for the signed-in course builder. Null is the idle case."""
    return {"play": take_play(get_redis(), int(user_id))}
