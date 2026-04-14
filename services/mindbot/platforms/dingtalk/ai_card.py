"""DingTalk AI interactive card: create/deliver + streaming markdown updates (OpenAPI only)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, NamedTuple, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.platforms.dingtalk.ai_card_errors import describe_ai_card_failure
from services.mindbot.platforms.dingtalk.constants import (
    PATH_CARD_INSTANCES_CREATE_AND_DELIVER,
    PATH_CARD_STREAMING_UPDATE,
)
from services.mindbot.platforms.dingtalk.http import post_v1_json_unverified, put_v1_json_unverified
from services.mindbot.platforms.dingtalk.oauth import (
    get_access_token,
    get_access_token_with_error,
    invalidate_access_token_cache,
)
from services.mindbot.platforms.dingtalk.response import dingtalk_v1_response_ok
from services.mindbot.platforms.dingtalk.session_webhook import sanitize_markdown_for_dingtalk
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_DEFAULT_PARAM_KEY = "content"
_MAX_STREAMING_CHARS = 950


class AiCardProbeResult(NamedTuple):
    """Result of admin probe for ``PUT /v1.0/card/streaming``."""

    ok: bool
    http_status: Optional[int]
    error_token: Optional[str]
    dingtalk_code: Optional[str]
    dingtalk_message: Optional[str]
    friendly_message: Optional[str]


def _dt_err(body: dict[str, Any]) -> tuple[str, str]:
    return str(body.get("code") or ""), str(body.get("message") or body.get("msg") or "")


def _streaming_probe_missing_card_accepted(body: dict[str, Any]) -> bool:
    """True when DingTalk reports no card for ``outTrackId`` (expected for admin probe)."""
    code, message = _dt_err(body)
    combined = f"{code} {message}".lower()
    if "outtrack" in combined or "not exist" in combined:
        return True
    if "card" in code.lower() and "exist" in combined:
        return True
    return False


def _http_detail(status: int) -> str:
    return f"http_{status}"


def mindbot_ai_card_param_key(cfg: OrganizationMindbotConfig) -> str:
    raw = (getattr(cfg, "dingtalk_ai_card_param_key", None) or "").strip()
    if raw:
        return raw
    return os.getenv("MINDBOT_DINGTALK_AI_CARD_PARAM_KEY_DEFAULT", _DEFAULT_PARAM_KEY).strip() or _DEFAULT_PARAM_KEY


def mindbot_ai_card_template_id(cfg: OrganizationMindbotConfig) -> str:
    return (getattr(cfg, "dingtalk_ai_card_template_id", None) or "").strip()


def mindbot_ai_card_wiring_enabled(cfg: OrganizationMindbotConfig) -> bool:
    """True when org config selects a template and OpenAPI client credentials exist."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False
    if not mindbot_ai_card_template_id(cfg):
        return False
    if not (cfg.dingtalk_client_id or "").strip():
        return False
    return True


def _im_group_deliver_robot_code(cfg: OrganizationMindbotConfig) -> str:
    """
    Value for ``imGroupOpenDeliverModel.robotCode``.

    Default matches ``imRobotOpenDeliverModel.robotCode`` in 1:1 chat
    (``dingtalk_robot_code``), which is what most HTTP robots use.

    Some internal non-scene orgs require the OpenAPI **AppKey**
    (``dingtalk_client_id``) instead; set ``MINDBOT_AI_CARD_GROUP_USE_APPKEY=true``.
    """
    app_key = (cfg.dingtalk_client_id or "").strip()
    robot = (cfg.dingtalk_robot_code or "").strip()
    if env_bool("MINDBOT_AI_CARD_GROUP_USE_APPKEY", False):
        return app_key or robot
    return robot or app_key


def _open_space_id_group(open_conversation_id: str) -> str:
    cid = open_conversation_id.strip()
    return f"dtv1.card//im_group.{cid}"


def _open_space_id_robot(user_id: str) -> str:
    uid = user_id.strip()
    return f"dtv1.card//im_robot.{uid}"


def _im_group_space_model() -> dict[str, Any]:
    return {"supportForward": True}


def _im_robot_space_model() -> dict[str, Any]:
    return {
        "supportForward": False,
        "lastMessageI18n": {"ZH_CN": "AI", "EN_US": "AI"},
        "searchSupport": {
            "searchIcon": "@lALPDgQ9q8hFhlHNAXzNAqI",
            "searchTypeName": '{"zh_CN":"MindBot","en_US":"MindBot"}',
            "searchDesc": "MindBot",
        },
        "notification": {
            "alertContent": " ",
            "notificationOff": False,
        },
    }


def _clip_streaming_content(text: str) -> str:
    if len(text) <= _MAX_STREAMING_CHARS:
        return text
    logger.warning(
        "[MindBot] dingtalk_ai_card_streaming_content_truncated chars=%s max=%s",
        len(text),
        _MAX_STREAMING_CHARS,
    )
    return text[:_MAX_STREAMING_CHARS]


def ai_card_overflow_remainder_for_markdown(markdown_full: str) -> str:
    """
    Return the sanitized markdown suffix after the AI card streaming character cap.

    Used for optional follow-up chat messages when the full reply exceeds the cap.
    """
    sanitized = sanitize_markdown_for_dingtalk(markdown_full)
    if len(sanitized) <= _MAX_STREAMING_CHARS:
        return ""
    return sanitized[_MAX_STREAMING_CHARS:]


def _resolve_app_key(
    cfg: OrganizationMindbotConfig,
    app_key_override: Optional[str],
) -> str:
    if app_key_override is not None:
        stripped = app_key_override.strip()
        if stripped:
            return stripped
    return (cfg.dingtalk_client_id or "").strip()


async def _access_token(
    cfg: OrganizationMindbotConfig,
    *,
    app_key_override: Optional[str] = None,
) -> Optional[str]:
    app_key = _resolve_app_key(cfg, app_key_override)
    if not app_key:
        return None
    return await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )


def _is_lwcp_sender_token(value: str) -> bool:
    """
    True if ``value`` is a DingTalk lightweight participant token.

    These strings (e.g. ``$:LWCP_v1:$...``) are not valid ``userId`` / ``recipients``
    for ``createAndDeliver`` in default userId mode.
    """
    s = value.strip()
    return bool(s) and s.startswith("$:LWCP")


def _sender_body_keys() -> tuple[str, ...]:
    """Field names to try for a real OpenAPI user id (top-level or nested)."""
    base = (
        "senderStaffId",
        "sender_staff_id",
        "senderId",
        "sender_id",
        "senderUnionId",
        "sender_union_id",
        "unionId",
        "union_id",
        "senderOpenId",
        "openId",
        "openUserId",
    )
    extra = (os.getenv("MINDBOT_AI_CARD_EXTRA_SENDER_KEYS") or "").strip()
    if not extra:
        return base
    parts = tuple(p.strip() for p in extra.split(",") if p.strip())
    return base + parts


def _sender_dicts_from_body(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Root body plus common nested maps that may carry sender ids."""
    out: list[dict[str, Any]] = [body]
    ext = body.get("extension")
    if isinstance(ext, dict):
        out.append(ext)
    biz = body.get("bizData")
    if isinstance(biz, dict):
        out.append(biz)
    return out


def _card_openapi_user_id_from_body(body: dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    Resolve ``userId`` / ``recipients`` for card ``createAndDeliver``.

    Prefer ``senderStaffId``, then ``senderId``, then union/open ids. Skip **LWCP**
    tokens. Scans ``extension`` / ``bizData`` when present. Returns
    ``("", "no_sender_staff")`` or ``("", "no_openapi_user_id")`` when nothing usable
    exists.
    """
    saw_nonempty = False
    keys = _sender_body_keys()
    for container in _sender_dicts_from_body(body):
        for key in keys:
            raw = container.get(key)
            if isinstance(raw, str):
                st = raw.strip()
            elif raw is not None:
                st = str(raw).strip()
            else:
                continue
            if not st:
                continue
            saw_nonempty = True
            if not _is_lwcp_sender_token(st):
                return st, None
    if saw_nonempty:
        return "", "no_openapi_user_id"
    return "", "no_sender_staff"


def _parse_group_body(
    body: dict[str, Any],
) -> tuple[bool, str, str, Optional[str]]:
    """
    Return ``(is_group, conversation_id, openapi_user_id, preflight_error_or_none)``.

    For **IM groups**, when no resolvable user id exists (missing or only LWCP),
    ``openapi_user_id`` may be empty and ``preflight_error_or_none`` None if
    ``MINDBOT_AI_CARD_GROUP_ANONYMOUS_DELIVER`` allows space-only delivery (omit
    ``userId`` / ``recipients``).
    """
    ct = body.get("conversationType") or body.get("conversation_type")
    is_group = False
    if ct is not None:
        is_group = str(ct).strip().lower() in ("2", "group")
    conv = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv.strip() if isinstance(conv, str) else ""
    uid, err = _card_openapi_user_id_from_body(body)
    if err and is_group and env_bool("MINDBOT_AI_CARD_GROUP_ANONYMOUS_DELIVER", True):
        if err in ("no_openapi_user_id", "no_sender_staff"):
            return is_group, conv_s, "", None
    if err:
        return is_group, conv_s, "", err
    return is_group, conv_s, uid, None


def ai_card_body_deliverable(body: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Fast pre-check: can ``createAndDeliver`` run for this callback body?

    Returns ``(True, None)`` when delivery is possible.
    Returns ``(False, reason)`` when it cannot proceed, e.g.:
    - ``"no_openapi_user_id"`` — 1:1 chat but only LWCP tokens available
    - ``"no_sender_staff"``   — 1:1 chat with no sender id at all
    - ``"no_conversation_id"`` — group chat but no conversationId

    For **groups**: anonymous deliver (no ``recipients``) matches the official SDK
    default and is expected to work.  Only a missing ``conversationId`` is fatal.

    Does **not** check org config. Pair with :func:`mindbot_ai_card_wiring_enabled`.
    """
    is_group, conv_s, _uid, err = _parse_group_body(body)
    if is_group:
        if not conv_s:
            return False, "no_conversation_id"
        return True, None
    if err:
        return False, err
    return True, None


async def create_and_deliver_ai_card(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    *,
    out_track_id: str,
    initial_markdown: str,
    pipeline_ctx: str = "",
) -> tuple[bool, Optional[str], str]:
    """
    POST createAndDeliver for one IM group or IM robot space.

    ``initial_markdown`` is placed in ``cardParamMap`` under the configured param key.

    Returns ``(ok, dingtalk_code, detail)``. ``detail`` is an internal reason key or
    DingTalk ``message`` when ``dingtalk_code`` is set.
    """
    token = await _access_token(cfg)
    if not token:
        logger.warning("[MindBot] ai_card_create_failed %s reason=no_token", pipeline_ctx)
        return False, None, "no_token"
    template_id = mindbot_ai_card_template_id(cfg)
    param_key = mindbot_ai_card_param_key(cfg)
    is_group, conv_s, sender_staff, preflight = _parse_group_body(body)
    if preflight:
        logger.warning(
            "[MindBot] ai_card_create_failed %s reason=%s",
            pipeline_ctx,
            preflight,
        )
        return False, None, preflight
    if not is_group and not sender_staff:
        logger.warning(
            "[MindBot] ai_card_create_failed %s reason=no_openapi_user_id",
            pipeline_ctx,
        )
        return False, None, "no_openapi_user_id"
    user_id = sender_staff
    robot_code = cfg.dingtalk_robot_code.strip()
    group_deliver_robot = _im_group_deliver_robot_code(cfg)
    if is_group:
        if not conv_s:
            logger.warning("[MindBot] ai_card_create_failed %s reason=no_conversation_id", pipeline_ctx)
            return False, None, "no_conversation_id"
        open_space_id = _open_space_id_group(conv_s)
        im_group_dm: dict[str, Any] = {"robotCode": group_deliver_robot}
        if sender_staff:
            im_group_dm["recipients"] = [sender_staff]
            im_group_dm["atUserIds"] = {sender_staff: ""}
        payload = {
            "cardTemplateId": template_id,
            "outTrackId": out_track_id,
            "callbackType": "STREAM",
            "cardData": {"cardParamMap": {param_key: initial_markdown}},
            "openSpaceId": open_space_id,
            "imGroupOpenSpaceModel": _im_group_space_model(),
            "imGroupOpenDeliverModel": im_group_dm,
        }
        if sender_staff:
            payload["userId"] = user_id
        else:
            logger.info(
                "[MindBot] ai_card_group_anonymous_deliver %s (no userId/recipients; "
                "LWCP or missing sender — card visible to all group members)",
                pipeline_ctx,
            )
    else:
        open_space_id = _open_space_id_robot(sender_staff)
        payload = {
            "userId": user_id,
            "cardTemplateId": template_id,
            "outTrackId": out_track_id,
            "callbackType": "STREAM",
            "cardData": {"cardParamMap": {param_key: initial_markdown}},
            "openSpaceId": open_space_id,
            "imRobotOpenSpaceModel": _im_robot_space_model(),
            "imRobotOpenDeliverModel": {
                "spaceType": "IM_ROBOT",
                "robotCode": robot_code,
            },
        }
    logger.debug(
        "[MindBot] ai_card_create_post %s path=%s template_id=%s group=%s "
        "out_track_prefix=%s",
        pipeline_ctx,
        PATH_CARD_INSTANCES_CREATE_AND_DELIVER,
        (template_id or "")[:20],
        is_group,
        (out_track_id or "")[:12],
    )
    status, resp_body = await post_v1_json_unverified(
        PATH_CARD_INSTANCES_CREATE_AND_DELIVER,
        token,
        payload,
        timeout_seconds=60,
        parse_json_on_error=True,
    )
    if status == 0:
        logger.warning("[MindBot] ai_card_create_failed %s reason=network_error", pipeline_ctx)
        return False, None, "network_error"
    if status != 200:
        if isinstance(resp_body, dict):
            code_err, msg_err = _dt_err(resp_body)
            if code_err or msg_err:
                logger.warning(
                    "[MindBot] ai_card_create_failed %s code=%s msg=%s friendly=%s",
                    pipeline_ctx,
                    code_err,
                    msg_err,
                    describe_ai_card_failure(code_err, msg_err),
                )
                return False, code_err or None, msg_err
        return False, None, _http_detail(status)
    if not resp_body:
        return False, None, "empty_body"
    if dingtalk_v1_response_ok(resp_body):
        logger.info(
            "[MindBot] ai_card_create_ok %s out_track_id=%s group=%s",
            pipeline_ctx,
            out_track_id[:16],
            is_group,
        )
        return True, None, ""
    code, msg = _dt_err(resp_body)
    logger.warning(
        "[MindBot] ai_card_create_failed %s code=%s msg=%s friendly=%s",
        pipeline_ctx,
        code,
        msg,
        describe_ai_card_failure(code, msg),
    )
    return False, code or None, msg


async def streaming_update_ai_card(
    cfg: OrganizationMindbotConfig,
    *,
    access_token: str,
    out_track_id: str,
    markdown_full: str,
    is_finalize: bool,
    pipeline_ctx: str = "",
    is_error: bool = False,
) -> tuple[bool, Optional[str], str, Optional[str]]:
    """
    PUT /v1.0/card/streaming — full markdown for the template variable (``isFull`` true).

    DingTalk requires full markdown for each streaming frame when the variable is markdown.
    Set ``is_error`` to finalize the stream in an error state (native AI card support).

    On HTTP 401, invalidates cached OAuth token and retries once with a fresh token.
    Returns ``(ok, code, detail, refreshed_access_token)``. When non-None, the fourth
    value is a new token that must replace the previous one on ``card_state`` — including
    on failure after a 401 retry so follow-up calls (e.g. ``mark_ai_card_stream_error``)
    do not use a stale token.
    """
    param_key = mindbot_ai_card_param_key(cfg)
    sanitized = sanitize_markdown_for_dingtalk(markdown_full)
    content = _clip_streaming_content(sanitized)
    out_short = (out_track_id.strip()[:12] + "…") if len(out_track_id.strip()) > 12 else out_track_id.strip()
    logger.debug(
        "[MindBot] ai_card_streaming_put %s out_track=%s finalize=%s is_error=%s "
        "param_key=%s markdown_chars=%s sanitized_chars=%s wire_chars=%s",
        pipeline_ctx,
        out_short,
        is_finalize,
        is_error,
        param_key,
        len(markdown_full),
        len(sanitized),
        len(content),
    )
    payload = {
        "outTrackId": out_track_id,
        "guid": str(uuid.uuid4()),
        "key": param_key,
        "content": content,
        "isFull": True,
        "isFinalize": is_finalize or is_error,
        "isError": is_error,
    }
    original_token = access_token.strip()
    effective_token = original_token
    refreshed: Optional[str] = None
    status = 0
    resp_body: Optional[dict[str, Any]] = None
    for attempt in range(2):
        status, resp_body = await put_v1_json_unverified(
            PATH_CARD_STREAMING_UPDATE,
            effective_token,
            payload,
            timeout_seconds=60,
        )
        if status == 401 and attempt == 0:
            logger.info(
                "[MindBot] ai_card_streaming_oauth_retry %s http_status=401 "
                "path=%s out_track=%s",
                pipeline_ctx,
                PATH_CARD_STREAMING_UPDATE,
                out_short,
            )
            app_key = (cfg.dingtalk_client_id or "").strip()
            secret = cfg.dingtalk_app_secret.strip()
            if app_key and secret:
                await invalidate_access_token_cache(
                    cfg.organization_id,
                    app_key,
                    secret,
                )
            new_tok = await prefetch_ai_card_access_token(cfg)
            if new_tok:
                effective_token = new_tok
                refreshed = new_tok
                continue
            logger.warning(
                "[MindBot] ai_card_streaming_oauth_retry %s prefetch_failed_after_401",
                pipeline_ctx,
            )
        break

    def _propagate_token() -> Optional[str]:
        if refreshed and refreshed != original_token:
            return refreshed
        return None

    if status == 0:
        logger.warning("[MindBot] ai_card_stream_failed %s reason=network_error", pipeline_ctx)
        return False, None, "network_error", _propagate_token()
    if status != 200:
        logger.debug(
            "[MindBot] ai_card_streaming_put_http %s status=%s out_track=%s finalize=%s",
            pipeline_ctx,
            status,
            out_short,
            is_finalize,
        )
        return False, None, _http_detail(status), _propagate_token()
    if not resp_body:
        return False, None, "empty_body", _propagate_token()
    if dingtalk_v1_response_ok(resp_body):
        tok_out = _propagate_token()
        logger.debug(
            "[MindBot] ai_card_streaming_put_ok %s out_track=%s finalize=%s "
            "is_error=%s oauth_refreshed=%s",
            pipeline_ctx,
            out_short,
            is_finalize,
            is_error,
            tok_out is not None,
        )
        return True, None, "", tok_out
    code, msg = _dt_err(resp_body)
    logger.warning(
        "[MindBot] ai_card_stream_failed %s finalize=%s code=%s msg=%s friendly=%s",
        pipeline_ctx,
        is_finalize,
        code,
        msg,
        describe_ai_card_failure(code, msg),
    )
    return False, code or None, msg, _propagate_token()


async def mark_ai_card_stream_error(
    cfg: OrganizationMindbotConfig,
    *,
    access_token: str,
    out_track_id: str,
    pipeline_ctx: str = "",
) -> tuple[bool, Optional[str], str, Optional[str]]:
    """
    Finalize streaming with ``isError: true`` (see DingTalk streaming update API).

    Uses minimal content to satisfy non-empty content checks.
    """
    return await streaming_update_ai_card(
        cfg,
        access_token=access_token,
        out_track_id=out_track_id,
        markdown_full=" ",
        is_finalize=True,
        pipeline_ctx=pipeline_ctx,
        is_error=True,
    )


async def prefetch_ai_card_access_token(cfg: OrganizationMindbotConfig) -> Optional[str]:
    """Optional: reuse one token across create + many streaming calls in a turn."""
    return await _access_token(cfg)


def _probe_friendly(
    ok: bool,
    error_token: Optional[str],
    dingtalk_code: Optional[str],
    dingtalk_message: Optional[str],
) -> Optional[str]:
    if ok:
        return None
    return describe_ai_card_failure(dingtalk_code, error_token or dingtalk_message or "")


async def probe_ai_card_streaming_update_api(
    cfg: OrganizationMindbotConfig,
    *,
    template_id_override: Optional[str] = None,
    dingtalk_client_id_override: Optional[str] = None,
) -> AiCardProbeResult:
    """
    Admin probe for ``PUT /v1.0/card/streaming`` (AI card streaming update).

    Uses a random ``outTrackId`` that does not exist. DingTalk returns a business
    error when the card is missing; that still proves OAuth and the streaming
    endpoint accept the call (see DingTalk streaming update API).
    """
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        et = "openapi_disabled"
        return AiCardProbeResult(
            False,
            None,
            et,
            None,
            None,
            _probe_friendly(False, et, None, None),
        )
    effective_tpl = (template_id_override or "").strip() or mindbot_ai_card_template_id(cfg)
    if not effective_tpl:
        et = "template_not_configured"
        return AiCardProbeResult(
            False,
            None,
            et,
            None,
            None,
            _probe_friendly(False, et, None, None),
        )
    if not _resolve_app_key(cfg, dingtalk_client_id_override):
        et = "client_id_required"
        return AiCardProbeResult(
            False,
            None,
            et,
            None,
            None,
            _probe_friendly(False, et, None, None),
        )
    app_key_resolved = _resolve_app_key(cfg, dingtalk_client_id_override)
    token, oauth_err = await get_access_token_with_error(
        cfg.organization_id,
        app_key_resolved,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        et = "token_failed"
        detail = (oauth_err or "").strip()
        friendly = (
            describe_ai_card_failure(None, detail)
            if detail
            else _probe_friendly(False, et, None, None)
        )
        return AiCardProbeResult(
            False,
            None,
            et,
            None,
            oauth_err or None,
            friendly,
        )
    payload = {
        "outTrackId": str(uuid.uuid4()),
        "guid": str(uuid.uuid4()),
        "key": mindbot_ai_card_param_key(cfg),
        "content": " ",
        "isFull": True,
        "isFinalize": False,
        "isError": False,
    }
    status, body = await put_v1_json_unverified(
        PATH_CARD_STREAMING_UPDATE,
        token,
        payload,
        timeout_seconds=15,
        parse_json_on_error=True,
    )
    if status == 0:
        et = "network_error"
        return AiCardProbeResult(
            False,
            None,
            et,
            None,
            None,
            _probe_friendly(False, et, None, None),
        )
    if status != 200:
        if body and _streaming_probe_missing_card_accepted(body):
            code, message = _dt_err(body)
            return AiCardProbeResult(
                True,
                status,
                None,
                code or None,
                message or None,
                None,
            )
        hd = _http_detail(status)
        return AiCardProbeResult(
            False,
            status,
            None,
            None,
            None,
            _probe_friendly(False, None, None, hd),
        )
    if not body:
        et = "empty_body"
        return AiCardProbeResult(
            False,
            status,
            et,
            None,
            None,
            _probe_friendly(False, et, None, None),
        )
    if dingtalk_v1_response_ok(body):
        return AiCardProbeResult(True, status, None, None, None, None)
    code, message = _dt_err(body)
    if _streaming_probe_missing_card_accepted(body):
        return AiCardProbeResult(True, status, None, code or None, message or None, None)
    combined = f"{code} {message}".lower()
    if "permission" in combined or "forbidden" in combined or "scope" in combined:
        return AiCardProbeResult(
            False,
            status,
            None,
            code or None,
            message or None,
            _probe_friendly(False, None, code, message),
        )
    return AiCardProbeResult(True, status, None, code or None, message or None, None)
