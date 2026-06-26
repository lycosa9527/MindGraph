"""Rotating pair-code handler for DingTalk account bind/unbind."""

from __future__ import annotations

from typing import Any, Optional

from services.auth.dingtalk_bind_constants import (
    BIND_ERROR_UNBIND_NOT_LINKED,
    BIND_ERROR_UNBIND_STAFF_MISMATCH,
    PAIR_PURPOSE_UNBIND,
    PAIR_PURPOSE_UNKNOWN,
)
from services.auth.dingtalk_bind_redis import (
    get_bind_token_data,
    is_bind_code_guess_blocked,
    pair_purpose_from_payload,
    record_bind_code_guess_failure,
    resolve_bind_token_for_org_code,
)
from services.auth.dingtalk_bind_service import claim_dingtalk_qr_bind, claim_dingtalk_unbind_pair
from services.mindbot.bind.code_parse import extract_bind_code_from_text
from services.mindbot.bind.ingress_helpers import finish_pair_reply, is_valid_bind_staff_id
from services.mindbot.bind.messages import mindbot_code_from_claim_error
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.tools.audit_log import (
    log_tool_attempt,
    log_tool_outcome,
    log_tool_rejected,
)
from services.mindbot.tools.context import HttpResult, ToolIngressContext

_TOOL_NAME = "pair_code"
_RESOLVE_SENTINEL_TOKEN = "*"


def _user_id_from_payload(data: dict[str, Any] | None) -> int | None:
    if data is None:
        return None
    raw = data.get("user_id")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


class PairCodeToolHandler:
    """Intercept bare 6-digit pair codes (Bluetooth-style bind/unbind)."""

    tool_name = "pair_code"
    priority = 10

    def matches(self, ctx: ToolIngressContext) -> bool:
        """True when the message body is only a 6-digit pair code."""
        return extract_bind_code_from_text(ctx.text_in) is not None

    async def handle(self, ctx: ToolIngressContext) -> Optional[HttpResult]:
        """Resolve pair session by org + code and run bind or unbind claim."""
        bind_code = extract_bind_code_from_text(ctx.text_in)
        if not bind_code:
            return None

        org_id = int(ctx.cfg.organization_id)
        staff_id = (ctx.sender_staff_id or "").strip()
        pipeline_ctx = ctx.pipeline_ctx

        if not is_valid_bind_staff_id(staff_id):
            log_tool_rejected(
                tool=_TOOL_NAME,
                org_id=org_id,
                staff_id=staff_id,
                reason="invalid_staff",
                pipeline_ctx=pipeline_ctx,
            )
            return await self._finish(
                ctx,
                MindbotErrorCode.BIND_INVALID_STAFF,
                PAIR_PURPOSE_UNKNOWN,
            )

        if await is_bind_code_guess_blocked(staff_id, _RESOLVE_SENTINEL_TOKEN):
            return await self._finish(
                ctx,
                MindbotErrorCode.BIND_TOKEN_EXPIRED,
                PAIR_PURPOSE_UNKNOWN,
                ok=False,
            )

        token = await resolve_bind_token_for_org_code(org_id, bind_code)
        if not token:
            await record_bind_code_guess_failure(staff_id, _RESOLVE_SENTINEL_TOKEN)
            return await self._finish(
                ctx,
                MindbotErrorCode.BIND_TOKEN_EXPIRED,
                PAIR_PURPOSE_UNKNOWN,
                ok=False,
            )

        token_data = await get_bind_token_data(token)
        purpose = pair_purpose_from_payload(token_data)
        user_id = _user_id_from_payload(token_data)

        log_tool_attempt(
            tool=_TOOL_NAME,
            org_id=org_id,
            staff_id=staff_id,
            purpose=purpose,
            pipeline_ctx=pipeline_ctx,
        )

        if purpose == PAIR_PURPOSE_UNBIND:
            ok, err_code = await claim_dingtalk_unbind_pair(
                token=token,
                bind_code=bind_code,
                organization_id=org_id,
                dingtalk_staff_id=staff_id,
            )
            outcome = self._unbind_outcome(ok, err_code)
        else:
            ok, err_code = await claim_dingtalk_qr_bind(
                token=token,
                bind_code=bind_code,
                organization_id=org_id,
                dingtalk_staff_id=staff_id,
                linked_via="code_bind",
            )
            outcome = mindbot_code_from_claim_error(err_code) if not ok else MindbotErrorCode.BIND_OK

        return await self._finish(
            ctx,
            outcome,
            purpose,
            ok=ok,
            user_id=user_id,
        )

    @staticmethod
    def _unbind_outcome(ok: bool, err_code: str) -> MindbotErrorCode:
        if ok:
            return MindbotErrorCode.UNBIND_OK
        if err_code == BIND_ERROR_UNBIND_NOT_LINKED:
            return MindbotErrorCode.UNBIND_NOT_LINKED
        if err_code == BIND_ERROR_UNBIND_STAFF_MISMATCH:
            return MindbotErrorCode.UNBIND_STAFF_MISMATCH
        return mindbot_code_from_claim_error(err_code)

    @staticmethod
    async def _finish(
        ctx: ToolIngressContext,
        outcome: MindbotErrorCode,
        purpose: str,
        *,
        ok: bool | None = None,
        user_id: int | None = None,
    ) -> HttpResult:
        resolved_ok = (
            ok
            if ok is not None
            else outcome
            in (
                MindbotErrorCode.BIND_OK,
                MindbotErrorCode.UNBIND_OK,
            )
        )
        log_tool_outcome(
            tool=_TOOL_NAME,
            org_id=int(ctx.cfg.organization_id),
            staff_id=(ctx.sender_staff_id or "").strip(),
            purpose=purpose,
            outcome=outcome.value,
            ok=resolved_ok,
            user_id=user_id,
            pipeline_ctx=ctx.pipeline_ctx,
        )
        return await finish_pair_reply(
            ctx.cfg,
            ctx.body,
            ctx.session_webhook_valid,
            ctx.session_webhook_pinned_ip,
            ctx.pipeline_ctx,
            ctx.record_usage,
            ctx.hdr_for_code,
            outcome,
            purpose,
            tool=_TOOL_NAME,
        )
