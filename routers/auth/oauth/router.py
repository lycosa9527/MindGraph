"""OAuth QR login and bind API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.oauth_user_link import OAUTH_PROVIDER_DINGTALK, OAUTH_PROVIDER_WECHAT
from repositories.oauth_user_link_repo import OauthUserLinkRepository
from routers.auth.dependencies import get_current_user
from services.auth.oauth.oauth_constants import (
    AUTH_ERROR_DISABLED,
    AUTH_ERROR_EXCHANGE_FAILED,
    AUTH_ERROR_INVALID_STATE,
    OAUTH_MODE_BIND,
    OAUTH_MODE_LOGIN,
    normalize_oauth_error_code,
)
from services.auth.oauth.oauth_login_service import (
    OauthLoginService,
    dingtalk_callback_url,
    encoded_callback_url,
    oauth_feature_enabled,
    public_site_base_url,
    resolve_provider_flags,
    wechat_callback_url,
)
from services.auth.oauth.oauth_post_login import issue_oauth_browser_session
from services.auth.oauth.oauth_state_redis import consume_oauth_state, mint_oauth_state
from services.auth.oauth.org_resolve import resolve_org_by_invitation_code
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth Login"])


class OauthProvidersResponse(BaseModel):
    """Enabled OAuth providers for invite-scoped login."""

    organization_id: int
    wechat_enabled: bool = False
    dingtalk_enabled: bool = False
    wechat_app_id: str = ""
    dingtalk_client_id: str = ""
    dingtalk_scope: str = "openid"
    wechat_redirect_uri: str = ""
    dingtalk_redirect_uri: str = ""


class OauthStartResponse(BaseModel):
    """Parameters for embedded QR widgets."""

    state: str
    app_id: str = Field("", alias="appId")
    client_id: str = Field("", alias="clientId")
    redirect_uri: str = Field("", alias="redirectUri")
    scope: str = ""

    model_config = {"populate_by_name": True}


class DingtalkCompleteRequest(BaseModel):
    """POST body for DingTalk authCode completion."""

    auth_code: str = Field(..., alias="authCode")
    state: str

    model_config = {"populate_by_name": True}


class OauthLinkItem(BaseModel):
    """One linked OAuth provider."""

    provider: str
    nickname: Optional[str] = None
    external_id_masked: str = ""


class OauthLinksResponse(BaseModel):
    """Current user's OAuth links in their org."""

    wechat: Optional[OauthLinkItem] = None
    dingtalk: Optional[OauthLinkItem] = None
    wechat_login_enabled: bool = False
    dingtalk_login_enabled: bool = False


def _mask_external_id(value: str) -> str:
    v = (value or "").strip()
    if len(v) <= 8:
        return "*" * len(v) if v else ""
    return f"{v[:4]}...{v[-4:]}"


def _home_redirect(
    *,
    error: Optional[str] = None,
    oauth_bind: Optional[str] = None,
) -> RedirectResponse:
    """Redirect to app home (bind flows while already signed in)."""
    if error:
        return RedirectResponse(url=f"/?error={error}", status_code=303)
    if oauth_bind:
        return RedirectResponse(url=f"/?oauth_bind={oauth_bind}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


def _auth_redirect(error: Optional[str] = None) -> RedirectResponse:
    """Redirect to login page (OAuth login failures)."""
    base = "/auth"
    if error:
        return RedirectResponse(url=f"{base}?error={error}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


def _oauth_failure_redirect(mode: str, error: str) -> RedirectResponse:
    """Send OAuth errors to the page the user can actually see."""
    if mode == OAUTH_MODE_BIND:
        return _home_redirect(error=error)
    return _auth_redirect(error)


@router.get("/providers", response_model=OauthProvidersResponse)
async def get_oauth_providers(
    invite: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_async_db),
):
    """Public: resolve org by invitation code and return enabled OAuth providers."""
    if not oauth_feature_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=AUTH_ERROR_DISABLED)
    org = await resolve_org_by_invitation_code(db, invite)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization_not_found")
    service = OauthLoginService(db)
    row = await service.get_org_config(org.id)
    flags = resolve_provider_flags(row)
    return OauthProvidersResponse(
        organization_id=org.id,
        wechat_enabled=flags.wechat_enabled,
        dingtalk_enabled=flags.dingtalk_enabled,
        wechat_app_id=flags.wechat_app_id,
        dingtalk_client_id=flags.dingtalk_client_id,
        dingtalk_scope=flags.dingtalk_scope,
        wechat_redirect_uri=encoded_callback_url(OAUTH_PROVIDER_WECHAT),
        dingtalk_redirect_uri=encoded_callback_url(OAUTH_PROVIDER_DINGTALK),
    )


@router.get("/wechat/start", response_model=OauthStartResponse)
async def wechat_login_start(
    invite: str = Query(..., min_length=1),
    mode: str = Query(OAUTH_MODE_LOGIN),
    db: AsyncSession = Depends(get_async_db),
):
    """Mint state and return WxLogin parameters."""
    org = await resolve_org_by_invitation_code(db, invite)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization_not_found")
    service = OauthLoginService(db)
    await service.assert_provider_enabled(org.id, OAUTH_PROVIDER_WECHAT)
    flags = resolve_provider_flags(await service.get_org_config(org.id))
    bind_user_id = None
    if mode == OAUTH_MODE_BIND:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="use_bind_start")
    state = await mint_oauth_state(
        organization_id=org.id,
        provider=OAUTH_PROVIDER_WECHAT,
        mode=mode,
        user_id=bind_user_id,
    )
    return OauthStartResponse(
        state=state,
        appId=flags.wechat_app_id,
        redirectUri=encoded_callback_url(OAUTH_PROVIDER_WECHAT),
        scope="snsapi_login",
    )


@router.get("/wechat/bind/start", response_model=OauthStartResponse)
async def wechat_bind_start(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticated: start WeChat bind flow."""
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_organization")
    service = OauthLoginService(db)
    await service.assert_provider_enabled(current_user.organization_id, OAUTH_PROVIDER_WECHAT)
    flags = resolve_provider_flags(await service.get_org_config(current_user.organization_id))
    state = await mint_oauth_state(
        organization_id=int(current_user.organization_id),
        provider=OAUTH_PROVIDER_WECHAT,
        mode=OAUTH_MODE_BIND,
        user_id=int(current_user.id),
    )
    return OauthStartResponse(
        state=state,
        appId=flags.wechat_app_id,
        redirectUri=encoded_callback_url(OAUTH_PROVIDER_WECHAT),
        scope="snsapi_login",
    )


@router.get("/wechat/callback")
async def wechat_oauth_callback(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    """WeChat redirect callback after scan."""
    if not code or not state:
        return _auth_redirect(AUTH_ERROR_INVALID_STATE)
    payload = await consume_oauth_state(state)
    if payload is None or payload.provider != OAUTH_PROVIDER_WECHAT:
        return _auth_redirect(AUTH_ERROR_INVALID_STATE)
    service = OauthLoginService(db)
    try:
        await service.assert_provider_enabled(payload.organization_id, OAUTH_PROVIDER_WECHAT)
        external_id, openid, nickname = await service.exchange_wechat_identity(code)
        if payload.mode == OAUTH_MODE_BIND:
            if payload.user_id is None:
                return _oauth_failure_redirect(OAUTH_MODE_BIND, AUTH_ERROR_INVALID_STATE)
            await service.complete_bind(
                organization_id=payload.organization_id,
                user_id=payload.user_id,
                provider=OAUTH_PROVIDER_WECHAT,
                external_id=external_id,
                openid=openid,
                nickname=nickname,
            )
            await db.commit()
            return _home_redirect(oauth_bind=OAUTH_PROVIDER_WECHAT)
        user = await service.resolve_login_user(
            organization_id=payload.organization_id,
            provider=OAUTH_PROVIDER_WECHAT,
            external_id=external_id,
        )
        await issue_oauth_browser_session(user, request, response, db, method="oauth_wechat")
        await db.commit()
        return _auth_redirect()
    except ValueError as exc:
        await db.rollback()
        return _oauth_failure_redirect(payload.mode, normalize_oauth_error_code(exc))
    except BACKGROUND_INFRA_ERRORS as exc:
        await db.rollback()
        logger.error("WeChat callback failed: %s", exc, exc_info=True)
        return _oauth_failure_redirect(payload.mode, AUTH_ERROR_EXCHANGE_FAILED)


@router.get("/dingtalk/start", response_model=OauthStartResponse)
async def dingtalk_login_start(
    invite: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_async_db),
):
    """Mint state and return DTFrameLogin parameters."""
    org = await resolve_org_by_invitation_code(db, invite)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization_not_found")
    service = OauthLoginService(db)
    row = await service.assert_provider_enabled(org.id, OAUTH_PROVIDER_DINGTALK)
    flags = resolve_provider_flags(row)
    use_corp = bool((row.dingtalk_corp_id or "").strip())
    state = await mint_oauth_state(
        organization_id=org.id,
        provider=OAUTH_PROVIDER_DINGTALK,
        mode=OAUTH_MODE_LOGIN,
        use_corp_scope=use_corp,
    )
    return OauthStartResponse(
        state=state,
        clientId=flags.dingtalk_client_id,
        redirectUri=encoded_callback_url(OAUTH_PROVIDER_DINGTALK),
        scope=flags.dingtalk_scope,
    )


@router.get("/dingtalk/bind/start", response_model=OauthStartResponse)
async def dingtalk_bind_start(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticated: start DingTalk bind flow."""
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_organization")
    service = OauthLoginService(db)
    row = await service.assert_provider_enabled(current_user.organization_id, OAUTH_PROVIDER_DINGTALK)
    flags = resolve_provider_flags(row)
    use_corp = bool((row.dingtalk_corp_id or "").strip())
    state = await mint_oauth_state(
        organization_id=int(current_user.organization_id),
        provider=OAUTH_PROVIDER_DINGTALK,
        mode=OAUTH_MODE_BIND,
        user_id=int(current_user.id),
        use_corp_scope=use_corp,
    )
    return OauthStartResponse(
        state=state,
        clientId=flags.dingtalk_client_id,
        redirectUri=encoded_callback_url(OAUTH_PROVIDER_DINGTALK),
        scope=flags.dingtalk_scope,
    )


async def _complete_dingtalk_flow(
    *,
    auth_code: str,
    state: str,
    request: Request,
    response: Response,
    db: AsyncSession,
    json_response: bool = False,
) -> RedirectResponse | dict[str, bool]:
    payload = await consume_oauth_state(state)
    if payload is None or payload.provider != OAUTH_PROVIDER_DINGTALK:
        if json_response:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=AUTH_ERROR_INVALID_STATE)
        return _auth_redirect(AUTH_ERROR_INVALID_STATE)
    service = OauthLoginService(db)
    try:
        row = await service.assert_provider_enabled(payload.organization_id, OAUTH_PROVIDER_DINGTALK)
        external_id, open_id, nick, _corp = await service.exchange_dingtalk_identity(row, auth_code)
        if payload.mode == OAUTH_MODE_BIND:
            if payload.user_id is None:
                if json_response:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=AUTH_ERROR_INVALID_STATE)
                return _oauth_failure_redirect(payload.mode, AUTH_ERROR_INVALID_STATE)
            await service.complete_bind(
                organization_id=payload.organization_id,
                user_id=payload.user_id,
                provider=OAUTH_PROVIDER_DINGTALK,
                external_id=external_id,
                openid=open_id,
                nickname=nick,
            )
            await db.commit()
            if json_response:
                return {"ok": True}
            return _home_redirect(oauth_bind=OAUTH_PROVIDER_DINGTALK)
        user = await service.resolve_login_user(
            organization_id=payload.organization_id,
            provider=OAUTH_PROVIDER_DINGTALK,
            external_id=external_id,
        )
        await issue_oauth_browser_session(user, request, response, db, method="oauth_dingtalk")
        await db.commit()
        if json_response:
            return {"ok": True}
        return _auth_redirect()
    except ValueError as exc:
        await db.rollback()
        if json_response:
            raise OauthLoginService.map_value_error(exc) from exc
        return _oauth_failure_redirect(payload.mode, normalize_oauth_error_code(exc))
    except BACKGROUND_INFRA_ERRORS as exc:
        await db.rollback()
        logger.error("DingTalk complete failed: %s", exc, exc_info=True)
        if json_response:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=AUTH_ERROR_EXCHANGE_FAILED,
            ) from exc
        return _oauth_failure_redirect(payload.mode, AUTH_ERROR_EXCHANGE_FAILED)


@router.post("/dingtalk/complete")
async def dingtalk_complete_post(
    body: DingtalkCompleteRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """Primary DingTalk login/bind completion from JS callback."""
    if not oauth_feature_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=AUTH_ERROR_DISABLED)
    return await _complete_dingtalk_flow(
        auth_code=body.auth_code,
        state=body.state,
        request=request,
        response=response,
        db=db,
        json_response=True,
    )


@router.get("/dingtalk/callback")
async def dingtalk_callback_get(
    request: Request,
    response: Response,
    auth_code: Optional[str] = Query(None, alias="authCode"),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    """Fallback DingTalk redirect callback."""
    if not auth_code or not state:
        return _auth_redirect(AUTH_ERROR_INVALID_STATE)
    return await _complete_dingtalk_flow(
        auth_code=auth_code,
        state=state,
        request=request,
        response=response,
        db=db,
    )


@router.post("/dingtalk/bind/complete")
async def dingtalk_bind_complete_post(
    body: DingtalkCompleteRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    """DingTalk bind completion from JS callback (alias)."""
    if not oauth_feature_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=AUTH_ERROR_DISABLED)
    return await _complete_dingtalk_flow(
        auth_code=body.auth_code,
        state=body.state,
        request=request,
        response=response,
        db=db,
        json_response=True,
    )


@router.get("/links", response_model=OauthLinksResponse)
async def get_oauth_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return OAuth link status for account bindings UI."""
    if not oauth_feature_enabled():
        return OauthLinksResponse()
    org_id = current_user.organization_id
    if not org_id:
        return OauthLinksResponse()
    service = OauthLoginService(db)
    row = await service.get_org_config(org_id)
    flags = resolve_provider_flags(row)
    repo = OauthUserLinkRepository(db)
    links = await repo.list_for_user(org_id, current_user.id)
    wechat_item: Optional[OauthLinkItem] = None
    dingtalk_item: Optional[OauthLinkItem] = None
    for link in links:
        item = OauthLinkItem(
            provider=link.provider,
            nickname=link.nickname,
            external_id_masked=_mask_external_id(link.external_id),
        )
        if link.provider == OAUTH_PROVIDER_WECHAT:
            wechat_item = item
        elif link.provider == OAUTH_PROVIDER_DINGTALK:
            dingtalk_item = item
    return OauthLinksResponse(
        wechat=wechat_item,
        dingtalk=dingtalk_item,
        wechat_login_enabled=flags.wechat_enabled,
        dingtalk_login_enabled=flags.dingtalk_enabled,
    )


@router.delete("/links/{provider}")
async def delete_oauth_link(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Self-unbind OAuth provider."""
    if not oauth_feature_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=AUTH_ERROR_DISABLED)
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_organization")
    repo = OauthUserLinkRepository(db)
    try:
        deleted = await repo.delete_for_user(
            int(current_user.organization_id),
            int(current_user.id),
            provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link_not_found")
    await db.commit()
    return {"status": "ok"}


@router.get("/config/callback-urls")
async def oauth_callback_urls(
    current_user: User = Depends(get_current_user),
):
    """Admin hint: public callback URLs for school IT."""
    _ = current_user
    return {
        "site_base": public_site_base_url(),
        "wechat_callback": wechat_callback_url(),
        "dingtalk_callback": dingtalk_callback_url(),
    }
