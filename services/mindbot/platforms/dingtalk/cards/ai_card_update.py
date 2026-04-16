"""DingTalk AI card: streaming updates, receiver-mode updates, admin probe."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, NamedTuple, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_CARD_INSTANCES,
    PATH_CARD_STREAMING_UPDATE,
)
from services.mindbot.platforms.dingtalk.api.http import put_v1_json_unverified
from services.mindbot.platforms.dingtalk.auth.oauth import (
    get_access_token_with_error,
    invalidate_access_token_cache,
)
from services.mindbot.platforms.dingtalk.api.response import dingtalk_v1_response_ok
from services.mindbot.platforms.dingtalk.messaging.session_webhook import sanitize_markdown_for_dingtalk
from services.mindbot.platforms.dingtalk.cards.ai_card_create import (
    _clip_streaming_content,
    _dt_err,
    _http_detail,
    _resolve_app_key,
    mindbot_ai_card_param_key,
    mindbot_ai_card_streaming_max_chars,
    mindbot_ai_card_template_id,
    prefetch_ai_card_access_token,
)
from services.mindbot.platforms.dingtalk.cards.ai_card_errors import describe_ai_card_failure
from services.mindbot.platforms.dingtalk.cards.streaming_qps import (
    acquire_dingtalk_streaming_qps_slot,
    dingtalk_streaming_body_is_qps_throttle,
)
from utils.env_helpers import env_bool, env_int

logger = logging.getLogger(__name__)


class AiCardProbeResult(NamedTuple):
    """Result of admin probe for ``PUT /v1.0/card/streaming``."""

    ok: bool
    http_status: Optional[int]
    error_token: Optional[str]
    dingtalk_code: Optional[str]
    dingtalk_message: Optional[str]
    friendly_message: Optional[str]


def _streaming_probe_missing_card_accepted(body: dict[str, Any]) -> bool:
    """True when DingTalk reports no card for ``outTrackId`` (expected for admin probe)."""
    code, message = _dt_err(body)
    combined = f"{code} {message}".lower()
    if "outtrack" in combined or "not exist" in combined:
        return True
    if "card" in code.lower() and "exist" in combined:
        return True
    return False


async def _card_put_with_retry(
    path: str,
    payload: dict[str, Any],
    access_token: str,
    cfg: OrganizationMindbotConfig,
    *,
    pipeline_ctx: str,
    log_prefix: str,
    out_short: str,
    on_qps_retry: Optional[Callable[[dict[str, Any]], None]] = None,
) -> tuple[int, Optional[dict[str, Any]], Optional[str]]:
    """PUT ``path`` with ``payload``, retrying on OAuth 401 (once) and QPS 403 throttle.

    The ``on_qps_retry`` callback, when provided, is called with the mutable ``payload``
    dict before each QPS sleep-and-retry so the caller can update fields like ``guid``.

    Returns ``(http_status, response_body, refreshed_token_or_none)``.  A non-None
    refreshed token must be stored by the caller so subsequent requests use the new token.
    """
    app_key_for_qps = (getattr(cfg, "dingtalk_client_id", None) or "").strip()
    original_token = access_token.strip()
    effective_token = original_token
    refreshed: Optional[str] = None
    status = 0
    resp_body: Optional[dict[str, Any]] = None
    oauth_attempted = False
    max_qps_retries = max(0, env_int("MINDBOT_DINGTALK_STREAMING_QPS_MAX_RETRIES", 4))
    qps_retries_done = 0

    while True:
        await acquire_dingtalk_streaming_qps_slot(app_key_for_qps)
        status, resp_body = await put_v1_json_unverified(
            path,
            effective_token,
            payload,
            timeout_seconds=60,
            parse_json_on_error=True,
        )
        if status == 401 and not oauth_attempted:
            oauth_attempted = True
            logger.info(
                "[MindBot] %s_oauth_retry %s http_status=401 out_track=%s",
                log_prefix,
                pipeline_ctx,
                out_short,
            )
            app_key = (cfg.dingtalk_client_id or "").strip()
            secret = cfg.dingtalk_app_secret.strip()
            if app_key and secret:
                await invalidate_access_token_cache(cfg.organization_id, app_key, secret)
            new_tok = await prefetch_ai_card_access_token(cfg)
            if new_tok:
                effective_token = new_tok
                refreshed = new_tok
                continue
            logger.warning(
                "[MindBot] %s_oauth_retry %s prefetch_failed_after_401",
                log_prefix,
                pipeline_ctx,
            )
            break
        if (
            status == 403
            and dingtalk_streaming_body_is_qps_throttle(resp_body)
            and qps_retries_done < max_qps_retries
        ):
            qps_retries_done += 1
            if on_qps_retry is not None:
                on_qps_retry(payload)
            logger.info(
                "[MindBot] %s_qps_retry %s http_status=403 attempt=%s/%s out_track=%s",
                log_prefix,
                pipeline_ctx,
                qps_retries_done,
                max_qps_retries,
                out_short,
            )
            await asyncio.sleep(1.0)
            continue
        break

    prop_tok: Optional[str] = refreshed if (refreshed and refreshed != original_token) else None
    return status, resp_body, prop_tok


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
    On DingTalk QPS throttle (HTTP 403 with QPS ``code``), sleeps ~1s and retries
    (see ``MINDBOT_DINGTALK_STREAMING_QPS_MAX_RETRIES``).
    Returns ``(ok, code, detail, refreshed_access_token)``. When non-None, the fourth
    value is a new token that must replace the previous one on ``card_state`` — including
    on failure after a 401 retry so follow-up calls (e.g. ``mark_ai_card_stream_error``)
    do not use a stale token.
    """
    param_key = mindbot_ai_card_param_key(cfg)
    sanitized = sanitize_markdown_for_dingtalk(markdown_full)
    cap = mindbot_ai_card_streaming_max_chars(cfg)
    content = _clip_streaming_content(sanitized, cap)
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

    payload: dict[str, Any] = {
        "outTrackId": out_track_id,
        "guid": str(uuid.uuid4()),
        "key": param_key,
        "content": content,
        "isFull": True,
        "isFinalize": is_finalize or is_error,
        "isError": is_error,
    }

    def _refresh_guid(p: dict[str, Any]) -> None:
        p["guid"] = str(uuid.uuid4())

    status, resp_body, prop_tok = await _card_put_with_retry(
        PATH_CARD_STREAMING_UPDATE,
        payload,
        access_token,
        cfg,
        pipeline_ctx=pipeline_ctx,
        log_prefix="ai_card_streaming",
        out_short=out_short,
        on_qps_retry=_refresh_guid,
    )

    if status == 0:
        logger.warning("[MindBot] ai_card_stream_failed %s reason=network_error", pipeline_ctx)
        return False, None, "network_error", prop_tok
    if status != 200:
        logger.debug(
            "[MindBot] ai_card_streaming_put_http %s status=%s out_track=%s finalize=%s",
            pipeline_ctx,
            status,
            out_short,
            is_finalize,
        )
        if resp_body and dingtalk_streaming_body_is_qps_throttle(resp_body):
            q_code, q_msg = _dt_err(resp_body)
            return False, q_code or None, q_msg or _http_detail(status), prop_tok
        return False, None, _http_detail(status), prop_tok
    if not resp_body:
        return False, None, "empty_body", prop_tok
    if dingtalk_v1_response_ok(resp_body):
        logger.debug(
            "[MindBot] ai_card_streaming_put_ok %s out_track=%s finalize=%s "
            "is_error=%s oauth_refreshed=%s",
            pipeline_ctx,
            out_short,
            is_finalize,
            is_error,
            prop_tok is not None,
        )
        return True, None, "", prop_tok
    code, msg = _dt_err(resp_body)
    logger.warning(
        "[MindBot] ai_card_stream_failed %s finalize=%s code=%s msg=%s friendly=%s",
        pipeline_ctx,
        is_finalize,
        code,
        msg,
        describe_ai_card_failure(code, msg),
    )
    return False, code or None, msg, prop_tok


async def update_ai_card_receiver(
    cfg: OrganizationMindbotConfig,
    *,
    access_token: str,
    out_track_id: str,
    markdown_full: str,
    is_finalize: bool,
    pipeline_ctx: str = "",
) -> tuple[bool, Optional[str], str, Optional[str]]:
    """
    PUT /v1.0/card/instances/{outTrackId} — receiver-flow card update.

    Used for group cards created via ``receiver:{spaceType,spaceId}`` (no
    ``callbackType: STREAM``).  Each call replaces the full card content, simulating
    the streaming typewriter effect seen with the STREAM flow.

    On HTTP 401, invalidates cached OAuth token and retries once with a fresh token.
    On DingTalk QPS throttle (HTTP 403 with QPS ``code``), sleeps ~1s and retries
    (see ``MINDBOT_DINGTALK_STREAMING_QPS_MAX_RETRIES``).
    Returns ``(ok, code, detail, refreshed_access_token)``.
    """
    param_key = mindbot_ai_card_param_key(cfg)
    sanitized = sanitize_markdown_for_dingtalk(markdown_full)
    cap = mindbot_ai_card_streaming_max_chars(cfg)
    content = _clip_streaming_content(sanitized, cap)
    out_short = (out_track_id.strip()[:12] + "…") if len(out_track_id.strip()) > 12 else out_track_id.strip()
    logger.debug(
        "[MindBot] ai_card_receiver_put %s out_track=%s finalize=%s "
        "param_key=%s wire_chars=%s",
        pipeline_ctx,
        out_short,
        is_finalize,
        param_key,
        len(content),
    )

    payload: dict[str, Any] = {
        "outTrackId": out_track_id.strip(),
        "cardData": {
            "cardParamMap": {param_key: content},
        },
    }

    status, resp_body, prop_tok = await _card_put_with_retry(
        PATH_CARD_INSTANCES,
        payload,
        access_token,
        cfg,
        pipeline_ctx=pipeline_ctx,
        log_prefix="ai_card_receiver",
        out_short=out_short,
    )

    if status == 0:
        logger.warning("[MindBot] ai_card_receiver_failed %s reason=network_error", pipeline_ctx)
        return False, None, "network_error", prop_tok
    if status != 200:
        logger.debug(
            "[MindBot] ai_card_receiver_put_http %s status=%s out_track=%s finalize=%s",
            pipeline_ctx,
            status,
            out_short,
            is_finalize,
        )
        if resp_body and dingtalk_streaming_body_is_qps_throttle(resp_body):
            q_code, q_msg = _dt_err(resp_body)
            return False, q_code or None, q_msg or _http_detail(status), prop_tok
        return False, None, _http_detail(status), prop_tok
    if not resp_body:
        return False, None, "empty_body", prop_tok
    if dingtalk_v1_response_ok(resp_body):
        logger.debug(
            "[MindBot] ai_card_receiver_put_ok %s out_track=%s finalize=%s oauth_refreshed=%s",
            pipeline_ctx,
            out_short,
            is_finalize,
            prop_tok is not None,
        )
        return True, None, "", prop_tok
    code, msg = _dt_err(resp_body)
    logger.warning(
        "[MindBot] ai_card_receiver_failed %s finalize=%s code=%s msg=%s friendly=%s",
        pipeline_ctx,
        is_finalize,
        code,
        msg,
        describe_ai_card_failure(code, msg),
    )
    return False, code or None, msg, prop_tok


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
    await acquire_dingtalk_streaming_qps_slot(app_key_resolved)
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
