"""Dify streaming vs blocking reply paths for MindBot (split from callback orchestrator).

SSE ``answer`` deltas pass through ``MindbotThinkingStreamFilter`` so chain-of-thought
is not streamed when disabled (see ``services.mindbot.core.reply_thinking``). Final
and AI-card wire text use ``format_mindbot_reply_for_dingtalk``; when CoT is shown,
``agent_thought`` from Dify is merged there if not already present in tag blocks.
``message_replace`` clears native thought in ``dify_stream`` and resets the stream
filter plus AI card buffer in ``on_dify_message_replace``.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from clients.dify import AsyncDifyClient, DifyFile
from services.mindbot.pipeline.context import DifyReplyContext
from services.mindbot.core.dify_stream import (
    mindbot_consume_dify_stream_batched,
    mindbot_stream_batch_params,
)
from services.mindbot.core.chain_of_thought_policy import effective_show_chain_of_thought
from services.mindbot.core.reply_thinking import (
    MindbotThinkingStreamFilter,
    format_mindbot_reply_for_dingtalk,
    native_reasoning_from_dify_blocking_response,
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
    send_full_reply,
    send_one_reply_chunk,
)
from services.mindbot.pipeline.send_tracker import (
    mark_complete,
    mark_error,
    mark_sending,
)
from services.mindbot.pipeline.ai_card_state import init_card_stream_state
from services.mindbot.platforms.dingtalk.cards.ai_card import (
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
from services.mindbot.platforms.dingtalk.cards.ai_card_create import (
    mindbot_ai_card_streaming_max_chars,
)
from services.mindbot.platforms.dingtalk.cards.ai_card_errors import describe_ai_card_failure
from services.mindbot.platforms.dingtalk.cards.streaming_qps import (
    dingtalk_streaming_body_is_qps_throttle,
)
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)


def _tracker_detail_for_full_send_fail(route: str, token_failed: bool) -> str:
    """Redis tracker ``err_detail`` when ``send_full_reply`` returns failure."""
    if token_failed:
        return f"{route}_dingtalk_token_failed"
    return f"{route}_send_failed"


async def run_streaming_dify_branch(
    ctx: DifyReplyContext,
    *,
    dify: AsyncDifyClient,
    text_in: str,
    user_id: str,
    dify_conv: Optional[str],
    files: list[DifyFile],
    dify_inputs: Optional[dict[str, Any]],
    stale_cb: Optional[Callable[[], Awaitable[None]]],
    release_semaphore_slot: Optional[Callable[[], None]] = None,
) -> tuple[int, dict[str, str]]:
    """Consume Dify SSE, send batched chunks to DingTalk, record usage."""
    cfg = ctx.cfg
    body = ctx.body
    session_webhook_valid = ctx.session_webhook_valid
    session_webhook_pinned_ip = ctx.session_webhook_pinned_ip
    conversation_id_dt = ctx.conversation_id_dt
    conv_key = ctx.conv_key
    record_usage = ctx.record_usage
    hdr = ctx.hdr
    redis_bind_dify_conversation = ctx.redis_bind_dify_conversation
    pipeline_ctx = ctx.pipeline_ctx
    msg_id = ctx.msg_id

    min_c, flush_s, max_p = mindbot_stream_batch_params()
    eff_show_cot = effective_show_chain_of_thought(cfg, body)
    think_filter = MindbotThinkingStreamFilter(
        show_chain_of_thought=eff_show_cot,
    )

    card_state = await init_card_stream_state(cfg, body, pipeline_ctx)

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        visible = think_filter.push(chunk)
        if not visible:
            return True, False
        if not card_state.first_chunk:
            card_state.first_chunk = True
            logger.info(
                "[MindBot] dify_first_chunk %s latency=%.1fs",
                pipeline_ctx,
                time.monotonic() - card_state.t0,
            )
        if card_state.buffer_only:
            # Cross-org group: accumulate silently; full response sent at end.
            card_state.cum += visible
            return True, False
        if card_state.plain_fallback_pending:
            # AI card error or QPS: accumulate silently; one full message at end.
            card_state.cum += visible
            return True, False
        if card_state.use_card:
            card_state.cum += visible
            wire_cum = card_state.hidden_reply_from_cum(cfg) if not eff_show_cot else card_state.cum
            if card_state.token is None:
                card_state.token = await prefetch_ai_card_access_token(cfg)
            tok = card_state.token
            if not tok:
                if not card_state.plain_fallback_pending:
                    await mark_error(msg_id, "ai_card_token_unavailable", pipeline_ctx)
                    card_state.plain_fallback_pending = True
                card_state.use_card = False
                return True, False
            if not card_state.created:
                out_id = str(uuid.uuid4())
                card_state.out_track_id = out_id
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
                    if not card_state.plain_fallback_pending:
                        await mark_error(
                            msg_id,
                            f"ai_card_create_failed:{c_code or ''}",
                            pipeline_ctx,
                        )
                        card_state.plain_fallback_pending = True
                    card_state.use_card = False
                    return True, False
                card_state.created = True
                card_state.update_mode = c_mode
            out_tid = card_state.out_track_id
            if not isinstance(out_tid, str) or not out_tid:
                return False, False
            use_receiver = card_state.update_mode == "receiver"
            if use_receiver:
                ok_s, s_code, s_detail, s_tok = await update_ai_card_receiver(
                    cfg,
                    access_token=tok,
                    out_track_id=out_tid,
                    markdown_full=wire_cum,
                    is_finalize=False,
                    pipeline_ctx=pipeline_ctx,
                )
            else:
                ok_s, s_code, s_detail, s_tok = await streaming_update_ai_card(
                    cfg,
                    access_token=tok,
                    out_track_id=out_tid,
                    markdown_full=wire_cum,
                    is_finalize=False,
                    pipeline_ctx=pipeline_ctx,
                )
            if s_tok:
                card_state.token = s_tok
            token_for_dt = card_state.token or tok
            if not ok_s:
                logger.warning(
                    "[MindBot] ai_card_stream_failed %s %s",
                    pipeline_ctx,
                    describe_ai_card_failure(s_code, s_detail),
                )
                # Mark the card as errored once, regardless of failure reason.
                if card_state.created and isinstance(out_tid, str) and not use_receiver:
                    mk_ok, mk_code, mk_detail, mk_tok = await mark_ai_card_stream_error(
                        cfg,
                        access_token=str(token_for_dt),
                        out_track_id=out_tid,
                        pipeline_ctx=pipeline_ctx,
                    )
                    if mk_tok:
                        card_state.token = mk_tok
                    if not mk_ok:
                        logger.warning(
                            "[MindBot] ai_card_mark_error_failed %s %s",
                            pipeline_ctx,
                            describe_ai_card_failure(mk_code, mk_detail),
                        )
                card_state.use_card = False
                if not card_state.plain_fallback_pending:
                    if dingtalk_streaming_body_is_qps_throttle(
                        {"code": s_code or "", "message": s_detail or ""},
                    ):
                        await mark_error(msg_id, "ai_card_stream_qps", pipeline_ctx)
                        logger.warning(
                            "[MindBot] ai_card_qps_exhausted_fallback %s switching_to_plain_message",
                            pipeline_ctx,
                        )
                    else:
                        await mark_error(
                            msg_id,
                            f"ai_card_stream_failed:{s_code or ''}",
                            pipeline_ctx,
                        )
                    card_state.plain_fallback_pending = True
                return True, False
            card_state.card_chars_confirmed = len(wire_cum)
            return True, False
        return await send_one_reply_chunk(
            cfg,
            body,
            session_webhook_valid,
            visible,
            pipeline_ctx=pipeline_ctx,
            pinned_ip=session_webhook_pinned_ip,
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
            card_state.created,
            card_state.update_mode,
        )
        tok = card_state.token
        out_tid = card_state.out_track_id
        is_stream_mode = card_state.update_mode != "receiver"
        if card_state.created and isinstance(out_tid, str) and tok and is_stream_mode:
            await mark_ai_card_stream_error(
                cfg,
                access_token=str(tok),
                out_track_id=out_tid,
                pipeline_ctx=pipeline_ctx,
            )
        think_filter.reset()
        card_state.reset(cfg)

    await mark_sending(msg_id, pipeline_ctx)
    full, new_conv, err_tok, usage_dify, native_reasoning = await mindbot_consume_dify_stream_batched(
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
        on_stream_started=release_semaphore_slot,
    )
    full_str = full if isinstance(full, str) else ""
    formatted_full = format_mindbot_reply_for_dingtalk(
        full_str,
        show_chain_of_thought=eff_show_cot,
        chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
        native_reasoning=native_reasoning,
    )
    use_cum_for_reply = not err_tok and ((card_state.created and card_state.use_card) or card_state.buffer_only)
    reply_text = (
        format_mindbot_reply_for_dingtalk(
            card_state.cum,
            show_chain_of_thought=eff_show_cot,
            chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
            native_reasoning=native_reasoning,
        )
        if use_cum_for_reply
        else formatted_full
    )
    tracker_complete_recorded = False
    skip_terminal_mark_complete = False
    # Cross-org buffer path: send the complete accumulated response as one message.
    if card_state.buffer_only and not err_tok and reply_text.strip():
        logger.info(
            "[MindBot] cross_org_buffer_send %s reply_chars=%s",
            pipeline_ctx,
            len(reply_text),
        )
        ok_cross, token_failed_cross = await send_full_reply(
            cfg,
            body,
            session_webhook_valid,
            reply_text,
            pipeline_ctx=pipeline_ctx,
            pinned_ip=session_webhook_pinned_ip,
        )
        if not ok_cross:
            await mark_error(
                msg_id,
                _tracker_detail_for_full_send_fail("cross_org", token_failed_cross),
                pipeline_ctx,
            )
            skip_terminal_mark_complete = True
    # AI card error / QPS fallback: one full markdown message after a short delay.
    if card_state.plain_fallback_pending and not err_tok:
        if formatted_full.strip():
            logger.warning(
                "[MindBot] plain_fallback_send %s chars=%s delay_s=5",
                pipeline_ctx,
                len(formatted_full),
            )
            await asyncio.sleep(5)
            ok_fb, token_failed_fb = await send_full_reply(
                cfg,
                body,
                session_webhook_valid,
                formatted_full,
                pipeline_ctx=pipeline_ctx,
                pinned_ip=session_webhook_pinned_ip,
            )
            if ok_fb:
                await mark_complete(msg_id, pipeline_ctx)
                tracker_complete_recorded = True
            else:
                await mark_error(
                    msg_id,
                    _tracker_detail_for_full_send_fail("plain_fallback", token_failed_fb),
                    pipeline_ctx,
                )
                skip_terminal_mark_complete = True
        else:
            skip_terminal_mark_complete = True
    if (
        not err_tok
        and card_state.use_card
        and card_state.created
        and isinstance(card_state.out_track_id, str)
        and card_state.token
    ):
        fin_ok = await card_state.finalize(cfg, reply_text, pipeline_ctx)
        if fin_ok and env_bool("MINDBOT_AI_CARD_APPEND_OVERFLOW_REMAINDER", False):
            remainder = ai_card_overflow_remainder_for_markdown(
                reply_text,
                max_chars=mindbot_ai_card_streaming_max_chars(cfg),
            )
            if remainder.strip():
                await send_one_reply_chunk(
                    cfg,
                    body,
                    session_webhook_valid,
                    remainder,
                    pipeline_ctx=pipeline_ctx,
                    pinned_ip=session_webhook_pinned_ip,
                )
        if not fin_ok:
            await mark_error(msg_id, "ai_card_finalize_failed", pipeline_ctx)
            if reply_text.strip():
                logger.warning(
                    "[MindBot] ai_card_finalize_fallback %s chars=%s delay_s=5",
                    pipeline_ctx,
                    len(reply_text),
                )
                await asyncio.sleep(5)
                ok_fin_fb, token_failed_fin = await send_full_reply(
                    cfg,
                    body,
                    session_webhook_valid,
                    reply_text,
                    pipeline_ctx=pipeline_ctx,
                    pinned_ip=session_webhook_pinned_ip,
                )
                if ok_fin_fb:
                    await mark_complete(msg_id, pipeline_ctx)
                    tracker_complete_recorded = True
                else:
                    await mark_error(
                        msg_id,
                        _tracker_detail_for_full_send_fail(
                            "finalize_fallback",
                            token_failed_fin,
                        ),
                        pipeline_ctx,
                    )
                    skip_terminal_mark_complete = True
            else:
                skip_terminal_mark_complete = True
    if err_tok == "dify_error":
        logger.warning(
            "[MindBot] dify_streaming_outcome %s outcome=dify_error reply_chars=%s",
            pipeline_ctx,
            len(reply_text),
        )
        await mark_error(msg_id, "dify_error", pipeline_ctx)
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
        await mark_error(msg_id, "dify_empty", pipeline_ctx)
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
        await mark_error(msg_id, "token_failed", pipeline_ctx)
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
        await mark_error(msg_id, "send_failed", pipeline_ctx)
        await record_usage(
            MindbotErrorCode.SESSION_WEBHOOK_FAILED,
            reply_text=reply_text,
            dify_conversation_id=new_conv,
            usage=usage_dify,
            streaming=True,
        )
        return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_FAILED)
    if isinstance(new_conv, str) and new_conv.strip() and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv.strip(),
            CONV_KEY_TTL_SECONDS,
        )
    _rp = reply_text[:80].replace("\n", " ")
    _re = "…" if len(reply_text) > 80 else ""
    logger.info(
        "[MindBot] done %s chars=%s elapsed=%.1fs reply=%r",
        pipeline_ctx,
        len(reply_text),
        time.monotonic() - card_state.t0,
        _rp + _re,
    )
    if not tracker_complete_recorded and not skip_terminal_mark_complete:
        await mark_complete(msg_id, pipeline_ctx)
    await record_usage(
        MindbotErrorCode.OK,
        reply_text=reply_text,
        dify_conversation_id=new_conv,
        usage=usage_dify,
        streaming=True,
    )
    return 200, hdr(MindbotErrorCode.OK)


async def run_blocking_send_branch(
    ctx: DifyReplyContext,
    *,
    resp: dict[str, Any],
    usage_block: Optional[dict[str, int]],
    raw_sw: Any,
) -> tuple[int, dict[str, str]]:
    """Send blocking Dify answer to DingTalk (session webhook and/or OpenAPI)."""
    cfg = ctx.cfg
    body = ctx.body
    session_webhook_valid = ctx.session_webhook_valid
    session_webhook_pinned_ip = ctx.session_webhook_pinned_ip
    conversation_id_dt = ctx.conversation_id_dt
    conv_key = ctx.conv_key
    record_usage = ctx.record_usage
    hdr = ctx.hdr
    redis_bind_dify_conversation = ctx.redis_bind_dify_conversation
    pipeline_ctx = ctx.pipeline_ctx
    msg_id = ctx.msg_id

    answer = (resp or {}).get("answer", "")
    if not isinstance(answer, str):
        answer = str(answer)
    eff_show_cot = effective_show_chain_of_thought(cfg, body)
    native_blocking = native_reasoning_from_dify_blocking_response(resp) if isinstance(resp, dict) else ""
    answer = format_mindbot_reply_for_dingtalk(
        answer,
        show_chain_of_thought=eff_show_cot,
        chain_of_thought_max_chars=int(cfg.chain_of_thought_max_chars),
        native_reasoning=native_blocking,
    )
    new_conv = (resp or {}).get("conversation_id")
    dify_cid_block: Optional[str] = None
    if isinstance(new_conv, str) and new_conv.strip():
        dify_cid_block = new_conv.strip()
    if isinstance(new_conv, str) and new_conv.strip() and conversation_id_dt:
        await redis_bind_dify_conversation(
            conv_key,
            new_conv.strip(),
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
            await mark_error(
                msg_id,
                f"ai_card_blocking_stream_failed:{st_code or ''}",
                pipeline_ctx,
            )
            return False
        return True

    await mark_sending(msg_id, pipeline_ctx)
    if await try_ai_card_blocking():
        await attachments_after_answer_ok()
        await record_usage(
            MindbotErrorCode.OK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        await mark_complete(msg_id, pipeline_ctx)
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
                await mark_complete(msg_id, pipeline_ctx)
                return 200, hdr(MindbotErrorCode.OK)
            if token_failed:
                await mark_error(msg_id, "dingtalk_token_failed", pipeline_ctx)
                await record_usage(
                    MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                    reply_text=answer,
                    dify_conversation_id=dify_cid_block,
                    usage=usage_block,
                    streaming=False,
                )
                return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
            await mark_error(msg_id, "session_webhook_invalid_url", pipeline_ctx)
            await record_usage(
                MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.SESSION_WEBHOOK_INVALID_URL)

        if await post_session_webhook(
            session_webhook_valid,
            answer,
            pipeline_ctx=pipeline_ctx,
            pinned_ip=session_webhook_pinned_ip,
        ):
            await attachments_after_answer_ok()
            await record_usage(
                MindbotErrorCode.OK,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            await mark_complete(msg_id, pipeline_ctx)
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
            await mark_complete(msg_id, pipeline_ctx)
            return 200, hdr(MindbotErrorCode.OK)
        if token_failed:
            await mark_error(msg_id, "dingtalk_token_failed", pipeline_ctx)
            await record_usage(
                MindbotErrorCode.DINGTALK_TOKEN_FAILED,
                reply_text=answer,
                dify_conversation_id=dify_cid_block,
                usage=usage_block,
                streaming=False,
            )
            return 200, hdr(MindbotErrorCode.DINGTALK_TOKEN_FAILED)
        await mark_error(msg_id, "session_webhook_failed", pipeline_ctx)
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
        await mark_complete(msg_id, pipeline_ctx)
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
        await mark_error(msg_id, "missing_session_webhook", pipeline_ctx)
        await record_usage(
            MindbotErrorCode.MISSING_SESSION_WEBHOOK,
            reply_text=answer,
            dify_conversation_id=dify_cid_block,
            usage=usage_block,
            streaming=False,
        )
        return 200, hdr(MindbotErrorCode.MISSING_SESSION_WEBHOOK)

    if token_failed:
        await mark_error(msg_id, "dingtalk_token_failed", pipeline_ctx)
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
    await mark_error(msg_id, "dingtalk_openapi_reply_failed", pipeline_ctx)
    await record_usage(
        MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED,
        reply_text=answer,
        dify_conversation_id=dify_cid_block,
        usage=usage_block,
        streaming=False,
    )
    return 200, hdr(MindbotErrorCode.DINGTALK_OPENAPI_REPLY_FAILED)
