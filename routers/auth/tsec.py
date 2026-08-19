"""Tencent T-Sec captcha: AppId mint + ticket exchange."""

from __future__ import annotations

import logging
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from models.domain.messages import Language, Messages, get_request_language
from services.auth.tsec.aid_encrypted import AidEncryptedError, mint_aid_encrypted
from services.auth.tsec.config import (
    PROVIDER_TSEC,
    effective_captcha_provider,
    tencent_captcha_app_id,
    tencent_captcha_app_secret_key,
)
from services.auth.tsec.exchange import exchange_tsec_ticket
from services.auth.tsec.result import TsecVerifyTrace
from services.redis.rate_limiting.redis_rate_limiter import check_captcha_rate_limit
from services.utils.error_types import REDIS_ERRORS
from utils.auth import CAPTCHA_SESSION_COOKIE_NAME, RATE_LIMIT_WINDOW_MINUTES, is_https
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter()


class TsecExchangeRequest(BaseModel):
    """Frontend TencentCaptcha callback fields used for verify + audit."""

    ticket: str = Field(..., min_length=8, max_length=2048)
    randstr: str = Field(..., min_length=1, max_length=64)
    sid: Optional[str] = Field(default=None, max_length=128)
    verify_duration: Optional[int] = Field(default=None, ge=0, le=600_000)
    action_duration: Optional[int] = Field(default=None, ge=0, le=600_000)


class TsecAidEncryptedResponse(BaseModel):
    """One-time AppId ciphertext for TencentCaptcha options."""

    aid_encrypted: str
    aid_encrypted_type: Literal["cbc"] = "cbc"


def _request_language(request: Request, x_language: Optional[str]) -> Language:
    """Resolve UI language from headers."""
    accept_language = request.headers.get("Accept-Language", "")
    return get_request_language(x_language, accept_language)


def _require_tsec_provider() -> None:
    """Hide T-Sec routes unless the live provider is tsec."""
    if effective_captcha_provider() != PROVIDER_TSEC:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _enforce_tsec_session_rate_limit(
    request: Request,
    response: Response,
    lang: Language,
) -> None:
    """Reuse the SVG captcha session cookie for T-Sec mint/exchange."""
    session_token = request.cookies.get(CAPTCHA_SESSION_COOKIE_NAME) or str(uuid.uuid4())
    try:
        is_allowed, _ = await check_captcha_rate_limit(session_token)
    except REDIS_ERRORS as exc:
        logger.error("T-Sec rate limit check failed: %s", exc, exc_info=True)
        is_allowed = True
    if not is_allowed:
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)

    response.set_cookie(
        key=CAPTCHA_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_https(request),
        samesite="lax",
        max_age=RATE_LIMIT_WINDOW_MINUTES * 60,
    )


@router.get("/tsec/aid-encrypted")
async def get_tsec_aid_encrypted(
    request: Request,
    response: Response,
    x_language: Optional[str] = Header(None, alias="X-Language"),
) -> TsecAidEncryptedResponse:
    """Mint a one-time ``aidEncrypted`` (unique IV) for CaptchaAppId 强制校验."""
    lang = _request_language(request, x_language)
    _require_tsec_provider()
    await _enforce_tsec_session_rate_limit(request, response, lang)
    response.headers["Cache-Control"] = "no-store"
    try:
        minted = mint_aid_encrypted(
            tencent_captcha_app_id(),
            tencent_captcha_app_secret_key(),
        )
    except AidEncryptedError as exc:
        logger.error("T-Sec aidEncrypted mint failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Messages.error("captcha_verify_failed", lang),
        ) from exc
    return TsecAidEncryptedResponse(
        aid_encrypted=minted["aid_encrypted"],
        aid_encrypted_type=minted["aid_encrypted_type"],
    )


@router.post("/tsec/exchange")
async def exchange_tsec_captcha(
    payload: TsecExchangeRequest,
    request: Request,
    response: Response,
    x_language: Optional[str] = Header(None, alias="X-Language"),
):
    """Verify a T-Sec ticket and return captcha_id + captcha for existing auth APIs."""
    lang = _request_language(request, x_language)
    _require_tsec_provider()
    await _enforce_tsec_session_rate_limit(request, response, lang)

    minted, reason = await exchange_tsec_ticket(
        payload.ticket,
        payload.randstr,
        get_client_ip(request),
        trace=TsecVerifyTrace(
            sid=payload.sid,
            verify_duration=payload.verify_duration,
            action_duration=payload.action_duration,
        ),
    )
    if minted is None:
        logger.warning("T-Sec exchange rejected: %s", reason)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("captcha_verify_failed", lang),
        )
    return minted
