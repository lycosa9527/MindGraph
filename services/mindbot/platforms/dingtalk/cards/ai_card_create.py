"""DingTalk AI card: body inspection, delivery pre-checks, createAndDeliver."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_CARD_INSTANCES_CREATE_AND_DELIVER,
)
from services.mindbot.platforms.dingtalk.api.http import post_v1_json_unverified
from services.mindbot.platforms.dingtalk.auth.oauth import get_access_token
from services.mindbot.platforms.dingtalk.api.response import dingtalk_v1_response_ok
from services.mindbot.platforms.dingtalk.messaging.session_webhook import sanitize_markdown_for_dingtalk
from services.mindbot.platforms.dingtalk.cards.stream_client import get_stream_manager
from services.mindbot.platforms.dingtalk.cards.ai_card_errors import describe_ai_card_failure
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_DEFAULT_PARAM_KEY = "content"
MAX_STREAMING_CHARS = 3000


def _dt_err(body: dict[str, Any]) -> tuple[str, str]:
    return str(body.get("code") or ""), str(body.get("message") or body.get("msg") or "")


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


def _clip_streaming_content(text: str) -> str:
    if len(text) <= MAX_STREAMING_CHARS:
        return text
    logger.warning(
        "[MindBot] dingtalk_ai_card_streaming_content_truncated chars=%s max=%s",
        len(text),
        MAX_STREAMING_CHARS,
    )
    return text[:MAX_STREAMING_CHARS]


def ai_card_overflow_remainder_for_markdown(markdown_full: str) -> str:
    """
    Return the sanitized markdown suffix after the AI card streaming character cap.

    Used for optional follow-up chat messages when the full reply exceeds the cap.
    """
    sanitized = sanitize_markdown_for_dingtalk(markdown_full)
    if len(sanitized) <= MAX_STREAMING_CHARS:
        return ""
    return sanitized[MAX_STREAMING_CHARS:]


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


async def prefetch_ai_card_access_token(cfg: OrganizationMindbotConfig) -> Optional[str]:
    """Optional: reuse one token across create + many streaming calls in a turn."""
    return await _access_token(cfg)


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

    For **IM groups**, a missing or LWCP-only sender is not an error — the caller
    routes to receiver-mode delivery (no ``openSpaceId`` / ``callbackType: STREAM``).
    ``preflight_error_or_none`` is only set for non-group 1:1 chats lacking a usable id.
    """
    ct = body.get("conversationType") or body.get("conversation_type")
    is_group = False
    if ct is not None:
        is_group = str(ct).strip().lower() in ("2", "group")
    conv = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv.strip() if isinstance(conv, str) else ""
    uid, err = _card_openapi_user_id_from_body(body)
    if is_group:
        # Groups with LWCP/no uid use receiver mode — not a preflight error.
        return is_group, conv_s, uid if not err else "", None
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

    For **groups**: only a missing ``conversationId`` is fatal.  Cross-org groups
    (LWCP sender) are routed to a plain-text buffer path by the pipeline before
    reaching ``createAndDeliver`` — see :func:`is_cross_org_group_body`.

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


def is_cross_org_group_body(body: dict[str, Any]) -> bool:
    """
    Return True when the callback body is a cross-org (external) group message.

    Cross-org groups have an LWCP token instead of a real ``senderStaffId``.
    AI card templates are enterprise-internal only; the pipeline buffers the full
    Dify response and sends it as a single plain message for these groups.
    """
    is_group, _conv, sender_staff, _err = _parse_group_body(body)
    return is_group and not sender_staff


def _open_space_id_group(open_conversation_id: str) -> str:
    return f"dtv1.card//im_group.{open_conversation_id.strip()}"


def _open_space_id_robot(user_id: str) -> str:
    return f"dtv1.card//im_robot.{user_id.strip()}"


def _im_group_space_model() -> dict[str, Any]:
    return {"supportForward": True}


def _im_group_robot_code(cfg: OrganizationMindbotConfig) -> str:
    """robotCode for imGroupOpenDeliverModel — AppKey (client_id) or robot code."""
    app_key = (cfg.dingtalk_client_id or "").strip()
    robot = (cfg.dingtalk_robot_code or "").strip()
    if env_bool("MINDBOT_AI_CARD_GROUP_USE_APPKEY", False):
        return app_key or robot
    return robot or app_key


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


async def create_and_deliver_ai_card(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    *,
    out_track_id: str,
    initial_markdown: str,
    pipeline_ctx: str = "",
) -> tuple[bool, Optional[str], str, str]:
    """
    POST createAndDeliver for one IM group or IM robot space.

    ``initial_markdown`` is placed in ``cardParamMap`` under the configured param key.

    Returns ``(ok, dingtalk_code, detail, update_mode)``.  ``update_mode`` is
    ``"stream"`` (use ``streaming_update_ai_card`` / ``PUT /v1.0/card/streaming``).
    On failure ``update_mode`` is ``""``.

    For group delivery the Stream SDK WebSocket connection is required by DingTalk
    before it accepts ``callbackType: "STREAM"``.  ``ensure_client`` is called
    lazily here; cross-org (LWCP) groups are already filtered out by the pipeline
    via :func:`is_cross_org_group_body` and never reach this function.
    """
    token = await _access_token(cfg)
    if not token:
        logger.warning("[MindBot] ai_card_create_failed %s reason=no_token", pipeline_ctx)
        return False, None, "no_token", ""
    template_id = mindbot_ai_card_template_id(cfg)
    param_key = mindbot_ai_card_param_key(cfg)
    is_group, conv_s, sender_staff, preflight = _parse_group_body(body)
    if preflight:
        logger.warning(
            "[MindBot] ai_card_create_failed %s reason=%s",
            pipeline_ctx,
            preflight,
        )
        return False, None, preflight, ""
    if not is_group and not sender_staff:
        logger.warning(
            "[MindBot] ai_card_create_failed %s reason=no_openapi_user_id",
            pipeline_ctx,
        )
        return False, None, "no_openapi_user_id", ""
    robot_code = cfg.dingtalk_robot_code.strip()
    if is_group:
        if not conv_s:
            logger.warning("[MindBot] ai_card_create_failed %s reason=no_conversation_id", pipeline_ctx)
            return False, None, "no_conversation_id", ""
        # Ensure the Stream SDK WebSocket is connected before calling
        # createAndDeliver — DingTalk requires an active Stream SDK connection
        # to accept callbackType="STREAM" for group cards.
        await get_stream_manager().ensure_client(
            (cfg.dingtalk_client_id or "").strip(),
            (cfg.dingtalk_app_secret or "").strip(),
        )
        open_space_id = _open_space_id_group(conv_s)
        # Omit recipients / atUserIds so the card is visible to all group members.
        # Setting recipients targets delivery (often only the @mentioned user sees it).
        group_deliver: dict[str, Any] = {
            "robotCode": _im_group_robot_code(cfg),
        }
        # Cross-org groups (LWCP sender, no sender_staff) are filtered out by
        # is_cross_org_group_body() in the pipeline before reaching this point.
        payload = {
            "cardTemplateId": template_id,
            "outTrackId": out_track_id,
            "callbackType": "STREAM",
            "cardData": {"cardParamMap": {param_key: initial_markdown}},
            "openSpaceId": open_space_id,
            "imGroupOpenSpaceModel": _im_group_space_model(),
            "imRobotOpenSpaceModel": {"supportForward": True},
            "imGroupOpenDeliverModel": group_deliver,
        }
        update_mode = "stream"
    else:
        open_space_id = _open_space_id_robot(sender_staff)
        payload = {
            "userId": sender_staff,
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
        update_mode = "stream"
    logger.debug(
        "[MindBot] ai_card_create_post %s path=%s template_id=%s group=%s "
        "update_mode=%s out_track_prefix=%s",
        pipeline_ctx,
        PATH_CARD_INSTANCES_CREATE_AND_DELIVER,
        (template_id or "")[:20],
        is_group,
        update_mode,
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
        return False, None, "network_error", ""
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
                return False, code_err or None, msg_err, ""
        return False, None, _http_detail(status), ""
    if not resp_body:
        return False, None, "empty_body", ""
    if dingtalk_v1_response_ok(resp_body):
        logger.info(
            "[MindBot] ai_card_create_ok %s out_track_id=%s group=%s update_mode=%s",
            pipeline_ctx,
            out_track_id[:16],
            is_group,
            update_mode,
        )
        return True, None, "", update_mode
    code, msg = _dt_err(resp_body)
    logger.warning(
        "[MindBot] ai_card_create_failed %s code=%s msg=%s friendly=%s",
        pipeline_ctx,
        code,
        msg,
        describe_ai_card_failure(code, msg),
    )
    return False, code or None, msg, ""
