"""Admin API for per-organization OAuth login configuration."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from repositories.organization_oauth_config_repo import OrganizationOauthConfigRepository
from routers.auth.dependencies import require_admin
from services.auth.oauth.oauth_login_service import (
    dingtalk_callback_url,
    public_site_base_url,
    wechat_callback_url,
)
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["Admin OAuth"])


class OrganizationOauthConfigResponse(BaseModel):
    """OAuth settings for one organization."""

    organization_id: int
    wechat_login_enabled: bool = False
    dingtalk_login_enabled: bool = False
    dingtalk_login_app_key: str = ""
    dingtalk_login_app_secret_set: bool = False
    dingtalk_corp_id: str = ""
    wechat_app_id: str = ""
    feature_oauth_login: bool = False
    wechat_callback_url: str = ""
    dingtalk_callback_url: str = ""
    site_base_url: str = ""


class OrganizationOauthConfigUpdate(BaseModel):
    """Patch body for org OAuth config."""

    wechat_login_enabled: Optional[bool] = None
    dingtalk_login_enabled: Optional[bool] = None
    dingtalk_login_app_key: Optional[str] = Field(None, alias="dingtalkLoginAppKey")
    dingtalk_login_app_secret: Optional[str] = Field(None, alias="dingtalkLoginAppSecret")
    dingtalk_corp_id: Optional[str] = Field(None, alias="dingtalkCorpId")
    clear_dingtalk_secret: bool = Field(False, alias="clearDingtalkSecret")

    model_config = {"populate_by_name": True}


def _to_response(org_id: int, row) -> OrganizationOauthConfigResponse:
    secret_set = bool((row.dingtalk_login_app_secret or "").strip()) if row else False
    app_key = (row.dingtalk_login_app_key or "").strip() if row else ""
    corp = (row.dingtalk_corp_id or "").strip() if row else ""
    wechat_on = bool(row.wechat_login_enabled) if row else False
    ding_on = bool(row.dingtalk_login_enabled) if row else False
    return OrganizationOauthConfigResponse(
        organization_id=org_id,
        wechat_login_enabled=wechat_on,
        dingtalk_login_enabled=ding_on,
        dingtalk_login_app_key=app_key,
        dingtalk_login_app_secret_set=secret_set,
        dingtalk_corp_id=corp,
        wechat_app_id=(config.WECHAT_OAUTH_APP_ID or "").strip(),
        feature_oauth_login=config.FEATURE_OAUTH_LOGIN,
        wechat_callback_url=wechat_callback_url(),
        dingtalk_callback_url=dingtalk_callback_url(),
        site_base_url=public_site_base_url(),
    )


@router.get("/{organization_id}/oauth-config", response_model=OrganizationOauthConfigResponse)
async def get_organization_oauth_config(
    organization_id: int,
    _scope: AdminScope = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Get OAuth QR login settings for a school."""
    repo = OrganizationOauthConfigRepository(db)
    try:
        row = await repo.get_by_org(organization_id)
        return _to_response(organization_id, row)
    except DATABASE_ERRORS as exc:
        logger.error("Failed to load oauth config: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="load_failed") from exc


@router.put("/{organization_id}/oauth-config", response_model=OrganizationOauthConfigResponse)
async def update_organization_oauth_config(
    organization_id: int,
    body: OrganizationOauthConfigUpdate,
    _scope: AdminScope = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Update OAuth QR login settings for a school."""
    if not config.FEATURE_OAUTH_LOGIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature_disabled")
    repo = OrganizationOauthConfigRepository(db)
    try:
        row = await repo.upsert(
            organization_id=organization_id,
            wechat_login_enabled=body.wechat_login_enabled,
            dingtalk_login_enabled=body.dingtalk_login_enabled,
            dingtalk_login_app_key=body.dingtalk_login_app_key,
            dingtalk_login_app_secret=body.dingtalk_login_app_secret,
            dingtalk_corp_id=body.dingtalk_corp_id,
            clear_dingtalk_secret=body.clear_dingtalk_secret,
        )
        await db.commit()
        return _to_response(organization_id, row)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("Failed to save oauth config: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="save_failed") from exc
