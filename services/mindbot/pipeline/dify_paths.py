"""Dify streaming vs blocking reply paths for MindBot (split from callback orchestrator)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from clients.dify import AsyncDifyClient, DifyFile
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.dify_stream import (
    mindbot_consume_dify_stream_batched,
    mindbot_stream_batch_params,
)
from services.mindbot.core.reply_thinking import (
    MindbotThinkingStreamFilter,
    format_mindbot_reply_for_dingtalk,
)
from services.mindbot.core.redis_keys import CONV_KEY_TTL_SECONDS
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.outbound.media import (
    send_blocking_response_attachments,
    send_dify_native_segment,
)
from services.mindbot.outbound.text import (
    post_session_webhook,
    reply_via_openapi,
    send_one_reply_chunk,
)
from services.mindbot.platforms.dingtalk.ai_card import (
    ai_card_body_deliverable,
    ai_card_overflow_remainder_for_markdown,
    create_and_deliver_ai_card,
    is_cross_org_group_body,
    mark_ai_card_stream_error,
    mindbot_ai_card_wiring_enabled,
    prefetch_ai_card_access_token,
    streaming_update_ai_card,
    update_ai_card_receiver,
)
from services.mindbot.platforms.dingtalk.ai_card_errors import describe_ai_card_failure
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)


async def run_streaming_dify_branch(
    *,
    cfg: OrganizationMindbotConfig,
    dify: AsyncDifyClient,
    text_in: str,
    user_id: str,
    dify_conv: Optional[str],
    files: list[DifyFile],
    body: dict[str, Any],
    session_webhook_valid: Optional[str],
    conversation_id_dt: str,
    conv_key: str,
    dify_inputs: Optional[dict[str, Any]],
    stale_cb: Optional[Callable[[], Awaitable[None]]],
    record_usage: Callable[..., Awaitable[None]],
    hdr: Callable[[MindbotErrorCode], dict[str, str]],
    redis_bind_dify_conversation: Callable[..., Awaitable[None]],
    pipeline_ctx: str = "",
) -> tuple[int, dict[str, str]]:
    """Consume Dify SSE, send batched chunks to DingTalk, record usage."""
    min_c, flush_s, max_p = mindbot_stream_batch_params()
    think_filter = MindbotThinkingStreamFilter(
        show_chain_of_thought=bool(cfg.show_chain_of_thought),
    )

    _card_wiring = mindbot_ai_card_wiring_enabled(cfg)
    if _card_wiring:
        _deliverable, _skip_reason = ai_card_body_deliverable(body)
        if not _deliverable:
            logger.info(
                "[MindBot] ai_card_skipped %s reason=%s",
                pipeline_ctx,
                _skip_reason,
            )
            _card_wiring = False
    # Cross-org (external) groups use LWCP sender tokens — AI card templates are
    # enterprise-internal only.  Buffer the full Dify response and send it as one
    # plain message at the end instead.
    _is_cross_org = is_cross_org_group_body(body)
    if _is_cross_org and _card_wiring:
        logger.info(
            "[MindBot] ai_card_skipped %s reason=cross_org_group",
            pipeline_ctx,
        )
        _card_wiring = False
    _outbound = "ai_card" if _card_wiring else ("buffer→plain" if _is_cross_org else "plain")
    logger.info(
        "[MindBot] route %s outbound=%s",
        pipeline_ctx,
        _outbound,
    )

    card_state: dict[str, Any] = {
        "use_card": _card_wiring,
        "buffer_only": _is_cross_org,
        "cum": "",
        "out_track_id": None,
        "token": None,
        "created": False,
        "update_mode": "stream",
        "_t0": time.monotonic(),
        "_first_chunk": False,
    }

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        visible = think_filter.push(chunk)
        if not visible:
            return True, False
        if not card_state["_first_chunk"]:
            card_state["_first_chunk"] = True
            logger.info(
                "[MindBot] dify_first_chunk %s latency=%.1fs",
                pipeline_ctx,
                time.monotonic() - card_state["_t0"],
            )
        if card_state.get("buffer_only"):
            # Cross-org group: accumulate silently; full response sent at end.
            card_state["cum"] += visible
            return True, False
        if card_state["use_card"]:
            card_state["cum"] += visible
            if card_state["token"] is None:
                card_state["token"] = await prefetch_ai_card_access_token(cfg)
            tok = card_state["token"]
            if not tok:
                card_state["use_card"] = False
                return await send_one_reply_chunk(
                    cfg,
                    body,
                    session_webhook_valid,
                    visible,
                    pipeline_ctx=pipeline_ctx,
                )
            if not card_state["created"]:
                out_id = str(uuid.uuid4())
                card_state["out_track_id"] = out_id
                ok_c, c_code, c_detail, c_mode = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id=out_id,
                    initial_markdown="",
                    pipeline_ctx=pipeline_ctx,
                )
                if not ok_c:
                    logger.warning(
                        "[MindBot] ai_card_create_failed %s %s",
                        pipeline_ctx,
                        describe_ai_card_failure(c_code, c_detail),
                    )
                    card_state["use_card"] = False
                    return await send_one_reply_chunk(
                        cfg,
                        body,
                        session_webhook_valid,
                        visible,
                        pipeline_ctx=pipeline_ctx,
                    )
                card_state["created"] = True
                card_state["update_mode"] = c_mode
            out_tid = card_state["out_track_id"]
            if not isinstance(out_tid, str) or not out_tid:
                return False, False
            use_receiver = card_state.get("update_mode") == "receiver"
            if use_receiver:
                ok_s, s_code, s_detail, s_tok = await update_ai_card_receiver(
                    cfg,
                    access_token=tok,
                    out_track_id=out_tid,
                    markdown_full=card_state["cum"],
                    is_finalize=False,
                    pipeline_ctx=pipeline_ctx,
                )
            else:
                ok_s, s_code, s_detail, s_tok = await streaming_update_ai_card(
                    cfg,
                    access_token=tok,
                    out_track_id=out_tid,
                    markdown_full=card_state["cum"],
                    is_finalize=False,
                    pipeline_ctx=pipeline_ctx,
                )
            if s_tok:
                card_state["token"] = s_tok
            token_for_dt = card_state.get("token") or tok
            if not ok_s:
                logger.warning(
                    "[MindBot] ai_card_stream_failed %s %s",
                    pipeline_ctx,
                    describe_ai_card_failure(s_code, s_detail),
                )
                if card_state.get("created") and isinstance(out_tid, str) and not use_receiver:
                    mk_ok, mk_code, mk_detail, mk_tok = await mark_ai_card_stream_error(
                        cfg,
                        access_token=str(token_for_dt),
                        out_track_id=out_tid,
                        pipeline_ctx=pipeline_ctx,
                    )
                    if mk_tok:
                        card_state["token"] = mk_tok
                    if not mk_ok:
                        logger.warning(
                            "[MindBot] ai_card_mark_error_failed %s %s",
                            pipeline_ctx,
                            describe_ai_card_failure(mk_code, mk_detail),
                        )
                card_state["use_card"] = False
                return await send_one_reply_chunk(
                    cfg,
                    body,
                    session_webhook_valid,
                    card_state["cum"],
                    pipeline_ctx=pipeline_ctx,
                )
            return True, False
        return await send_one_reply_chunk(
            cfg,
            body,
            session_webhook_valid,
            visible,
            pipeline_ctx=pipeline_ctx,
        )

    async def on_media(kind: str, payload: dict[str, Any]) -> tuple[bool, bool]:
        if not env_bool("MINDBOT_DIFY_NATIVE_MEDIA_ENABLED", True):
            return True, False
        return await send_dify_native_segment(
            cfg,
            body,
            kind,
            payload,
            pipeline_ctx=pipeline_ctx,
        )

    async def on_dify_message_replace() -> None:
        """Reset AI card and thinking filter when Dify replaces the streamed answer."""
        logger.info(
            "[MindBot] mindbot_pipeline_message_replace %s had_card_created=%s update_mode=%s",
            pipeline_ctx,
            bool(card_state.get("created")),
            card_state.get("update_mode"),
        )
        tok = card_state.get("token")
        out_tid = card_state.get("out_track_id")
        is_stream_mode = card_state.get("update_mode") != "receiver"
        if card_state.get("created") and isinstance(out_tid, str) and tok and is_stream_mode:
            await mark_ai_card_stream_error(
                cfg,
                access_token=str(tok),
                out_track_id=out_tid,
                pipeline_ctx=pipeline_ctx,
            )
        think_filter.reset()
        card_state["cum"] = ""
        card_state["out_track_id"] = None
        card_state["token"] = None
        card_state["created"] = False
        card_state["update_mode"] = "stream"
        card_state["use_card"] = (
            mindbot_ai_card_wiring_enabled(cfg) and not card_state.get("buffer_only")
        )

    full, new_conv, err_tok, usage_dify = await mindbot_consume_dify_stream_batched(
        dify,
        text=text_in,
        user_id=user_id,
        conversation_id=dify_conv,
        files=files,
        min_chars=min_c,
        flush_interval_s=flush_s,
        max_parts=max_p,
        on_batch=on_batch,
        inputs=dify_inputs,
        on_stale_conversation=stale_cb,
        pipeline_ctx=pipeline_ctx,
        on_media=on_media,
        on_message_replace=on_dify_message_replace,
    )
    full_str = full if isinstance(full, str) else ""
    formatted_full = format_mindbot_reply_for_dingtalk(
        full_str,
        show_chain_of_thought=bool(cfg.show_chain_of_thought),
        chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
    )
    use_cum_for_reply = not err_tok and (
        (card_state.get("created") and card_state.get("use_card"))
        or card_state.get("buffer_only")
    )
    reply_text = (
        format_mindbot_reply_for_dingtalk(
            card_state["cum"],
            show_chain_of_thought=bool(cfg.show_chain_of_thought),
            chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
        )
        if use_cum_for_reply
        else formatted_full
    )
    # Cross-org buffer path: send the complete accumulated response as one message.
    if card_state.get("buffer_only") and not err_tok and reply_text.strip():
        logger.info(
            "[MindBot] cross_org_buffer_send %s reply_chars=%s",
            pipeline_ctx,
            len(reply_text),
        )
        await send_one_reply_chunk(
            cfg,
            body,
            session_webhook_valid,
            reply_text,
            pipeline_ctx=pipeline_ctx,
        )
    if (
        not err_tok
        and card_state.get("use_card")
        and card_state.get("created")
        and isinstance(card_state.get("out_track_id"), str)
        and card_state.get("token")
    ):
        fin_use_receiver = card_state.get("update_mode") == "receiver"
        if fin_use_receiver:
            fin_ok, fin_code, fin_detail, fin_tok = await update_ai_card_receiver(
                cfg,
                access_token=str(card_state["token"]),
                out_track_id=str(card_state["out_track_id"]),
                markdown_full=reply_text,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        else:
            fin_ok, fin_code, fin_detail, fin_tok = await streaming_update_ai_card(
                cfg,
                access_token=str(card_state["token"]),
                out_track_id=str(card_state["out_track_id"]),
                markdown_full=reply_text,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        if fin_tok:
            card_state["token"] = fin_tok
        if fin_ok and env_bool("MINDBOT_AI_CARD_APPEND_OVERFLOW_REMAINDER", False):
            remainder = ai_card_overflow_remainder_for_markdown(reply_text)
            if remainder.strip():
                await send_one_reply_chunk(
                    cfg,
                    body,
                    session_webhook_valid,
                    remainder,
                    pipeline_ctx=pipeline_ctx,
                )
        if not fin_ok:
            logger.warning(
                "[MindBot] ai_card_finalize_failed %s %s",
                pipeline_ctx,
                describe_ai_card_failure(fin_code, fin_detail),
            )
            if not fin_use_receiver:
                mk_ok, mk_code, mk_detail, mk_tok = await mark_ai_card_stream_error(
                    cfg,
                    access_token=str(card_state["token"]),
                    out_track_id=str(card_state["out_track_id"]),
                    pipeline_ctx=pipeline_ctx,
                )
                if mk_tok:
                    card_state["token"] = mk_tok
                if not mk_ok:
                    logger.warning(
                        "[MindBot] ai_card_mark_error_after_finalize_failed %s %s",
                        pipeline_ctx,
                        describe_ai_card_failure(mk_code, mk_detail),
                    )
            await send_one_reply_chunk(
                cfg,
                body,
                session_webhook_valid,
                reply_text,
                pipeline_ctx=pipeline_ctx,
            )
    if err_tok == "dify_error":
        logger.warning(
            "[MindBot] dify_streaming_outcome %s outcome=dify_error reply_chars=%s",
            pipeline_ctx,
            len(reply_text),
        )
        await record_usage(
            MindbotErrorCode.DIFY_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DIFY_FAILED)
    if err_tok == "dify_empty":
        logger.warning(
            "[MindBot] dify_streaming_outcome %s outcome=dify_empty",
            pipeline_ctx,
        )
        await record_usage(
            MindbotErrorCode.DIFY_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DIFY_FAILED)
    if err_tok == "token_failed":
        logger.warning(
            "[MindBot] dify_streaming_outcome %s outcome=dingtalk_token_failed",
            pipeline_ctx,
        )
        await record_usage(
            MindbotErrorCode.DINGTALK_TOKEN_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
    if err_tok == "send_failed":
        logger.warning(
            "[MindBot] dify_streaming_outcome %s outcome=outbound_send_failed",
            pipeline_ctx,
        )
        await record_usage(
            MindbotErrorCode.SESSION_WEBHOOK_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_FAILED)
    if isinstance(new_conv, str) and new_conv and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv,
            CONV_KEY_TTL_SECONDS,
        )
    _rp = reply_text[:80].replace("\n", " ")
    _re = "…" if len(reply_text) > 80 else ""
    logger.info(
        "[MindBot] done %s chars=%s elapsed=%.1fs reply=%r",
        pipeline_ctx,
        len(reply_text),
        time.monotonic() - card_state["_t0"],
        _rp + _re,
    )
    await record_usage(
        MindbotErrorCode.OK,
        reply_text=reply_text,
        dify_conversation_id=new_conv,
        usage=usage_dify,
        streaming=True,
    )
    return 200, hdr(MindbotErrorCode.OK)


async def run_blocking_send_branch(
    *,
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    resp: dict[str, Any],
    usage_block: Optional[dict[str, int]],
    raw_sw: Any,
    session_webhook_valid: Optional[str],
    conversation_id_dt: str,
    conv_key: str,
    record_usage: Callable[..., Awaitable[None]],
    hdr: Callable[[MindbotErrorCode], dict[str, str]],
    redis_bind_dify_conversation: Callable[..., Awaitable[None]],
    pipeline_ctx: str = "",
) -> tuple[int, dict[str, str]]:
    """Send blocking Dify answer to DingTalk (session webhook and/or OpenAPI)."""
    answer = (resp or {}).get("answer", "")
    if not isinstance(answer, str):
        answer = str(answer)
    answer = format_mindbot_reply_for_dingtalk(
        answer,
        show_chain_of_thought=bool(cfg.show_chain_of_thought),
        chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
    )
    new_conv = (resp or {}).get("conversation_id")
    dify_cid_block: Optional[str] = None
    if isinstance(new_conv, str) and new_conv.strip():
        dify_cid_block = new_conv.strip()
    if isinstance(new_conv, str) and new_conv and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv,
            CONV_KEY_TTL_SECONDS,
        )

    async def attachments_after_answer_ok() -> None:
        await send_blocking_response_attachments(
            cfg,
            body,
            resp,
            pipeline_ctx=pipeline_ctx,
        )

    async def try_ai_card_blocking() -> bool:
        if not answer.strip():
            return False
        if not mindbot_ai_card_wiring_enabled(cfg):
            return False
        deliverable, skip_reason = ai_card_body_deliverable(body)
        if not deliverable:
            logger.info(
                "[MindBot] ai_card_skipped %s reason=%s",
                pipeline_ctx,
                skip_reason,
            )
            return False
        if is_cross_org_group_body(body):
            logger.info(
                "[MindBot] ai_card_skipped %s reason=cross_org_group",
                pipeline_ctx,
            )
            return False
        tok = await prefetch_ai_card_access_token(cfg)
        if not tok:
            return False
        out_id = str(uuid.uuid4())
        ok_create, cr_code, cr_detail, cr_mode = await create_and_deliver_ai_card(
            cfg,
            body,
            out_track_id=out_id,
            initial_markdown="",
            pipeline_ctx=pipeline_ctx,
        )
        if not ok_create:
            logger.warning(
                "[MindBot] ai_card_blocking_create_failed %s %s",
                pipeline_ctx,
                describe_ai_card_failure(cr_code, cr_detail),
            )
            return False
        use_receiver = cr_mode == "receiver"
        if use_receiver:
            ok_stream, st_code, st_detail, st_tok = await update_ai_card_receiver(
                cfg,
                access_token=tok,
                out_track_id=out_id,
                markdown_full=answer,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        else:
            ok_stream, st_code, st_detail, st_tok = await streaming_update_ai_card(
                cfg,
                access_token=tok,
                out_track_id=out_id,
                markdown_full=answer,
                is_finalize=True,
                pipeline_ctx=pipeline_ctx,
            )
        token_for_mark = st_tok or tok
        if not ok_stream:
            logger.warning(
                "[MindBot] ai_card_blocking_stream_failed %s %s",
                pipeline_ctx,
                describe_ai_card_failure(st_code, st_detail),
            )
            if not use_receiver:
                mk_ok, mk_code, mk_detail, _mk_tok = await mark_ai_card_stream_error(
                    cfg,
                    access_token=str(token_for_mark),
                    out_track_id=out_id,
                    pipeline_ctx=pipeline_ctx,
                )
                if not mk_ok:
                    logger.warning(
                        "[MindBot] ai_card_blocking_mark_error_failed %s %s",
                        pipeline_ctx,
                        describe_ai_card_failure(mk_code, mk_detail),
                    )
            return False
        return True

    if await try_ai_card_blocking():
        await attachments_after_answer_ok()
        await record_usage(
            MindbotErrorCode.OK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.OK)

    if isinstance(raw_sw, str) and raw_sw.strip():
        if not session_webhook_valid:
            openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer, pipeline_ctx=pipeline_ctx)
            if openapi_ok:
                await attachments_after_answer_ok()
                await record_usage(
                    MindbotErrorCode.OK,
                    reply_text=answer,
                    dify_conversation_id=dify_cid_block,
                    usage=usage_block,
                    streaming=False,
                )
                return 200, hdr(MindbotErrorCode.OK)
            if token_failed:
                await record_usage(
                    MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                    reply_text=answer,
                    dify_conversation_id=dify_cid_block,
                    usage=usage_block,
                    streaming=False,
                )
                return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
            await record_usage(
                MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL)

        if await post_session_webhook(session_webhook_valid, answer, pipeline_ctx=pipeline_ctx):
            await attachments_after_answer_ok()
            await record_usage(
                MindbotErrorCode.OK,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.OK)
        openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer, pipeline_ctx=pipeline_ctx)
        if openapi_ok:
            await attachments_after_answer_ok()
            await record_usage(
                MindbotErrorCode.OK,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.OK)
        if token_failed:
            await record_usage(
                MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
        await record_usage(
            MindbotErrorCode.SESSION_WEBHOOK_FAILED,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_FAILED)

    openapi_ok, token_failed = await reply_via_openapi(cfg, body, answer, pipeline_ctx=pipeline_ctx)
    if openapi_ok:
        await attachments_after_answer_ok()
        await record_usage(
            MindbotErrorCode.OK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.OK)

    can_fallback = (
        env_bool("MINDBOT_OPENAPI_ENABLED", True)
        and env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True)
        and bool((cfg.dingtalk_client_id or "").strip())
    )
    if not can_fallback:
        logger.warning(
            "[MindBot] outbound_blocked %s missing_session_webhook openapi_unconfigured",
            pipeline_ctx,
        )
        await record_usage(
            MindbotErrorCode.MISSING_SESSION_WEBHOOK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.MISSING_SESSION_WEBHOOK)

    if token_failed:
        await record_usage(
            MindbotErrorCode.DINGTALK_TOKEN_FAILED,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)

    logger.warning(
        "[MindBot] outbound_blocked %s openapi_fallback_send_failed",
        pipeline_ctx,
    )
    await record_usage(
        MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED,
        reply_text=answer,
        dify_conversation_id=dify_cid_block,
        usage=usage_block,
        streaming=False,
    )
    return 200, hdr(MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED)
