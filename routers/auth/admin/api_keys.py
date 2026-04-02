"""Admin API Key Management Endpoints.

Admin-only API key management endpoints:
- GET /admin/api_keys - List all API keys with usage stats
- POST /admin/api_keys - Create new API key
- PUT /admin/api_keys/{key_id} - Update API key settings
- DELETE /admin/api_keys/{key_id} - Delete/revoke API key
- PUT /admin/api_keys/{key_id}/toggle - Toggle API key active status

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import sum as sa_sum

from config.database import get_async_db
from models.domain.auth import User, APIKey
from models.domain.messages import Messages
from models.domain.token_usage import TokenUsage
from utils.auth import generate_api_key

from ..dependencies import get_language_dependency, require_admin
from ..helpers import utc_to_beijing_iso


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/api_keys", dependencies=[Depends(require_admin)])
async def list_api_keys_admin(
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    _lang: str = Depends(get_language_dependency),
) -> List[Dict[str, Any]]:
    """List all API keys with usage stats (ADMIN ONLY)"""
    keys = (await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))).scalars().all()

    token_stats_by_key = {}

    try:
        for key in keys:
            key_token_stats = (
                await db.execute(
                    select(
                        sa_sum(TokenUsage.input_tokens).label("input_tokens"),
                        sa_sum(TokenUsage.output_tokens).label("output_tokens"),
                        sa_sum(TokenUsage.total_tokens).label("total_tokens"),
                    ).where(TokenUsage.api_key_id == key.id, TokenUsage.success)
                )
            ).first()

            if key_token_stats:
                token_stats_by_key[key.id] = {
                    "input_tokens": int(key_token_stats.input_tokens or 0),
                    "output_tokens": int(key_token_stats.output_tokens or 0),
                    "total_tokens": int(key_token_stats.total_tokens or 0),
                }
            else:
                token_stats_by_key[key.id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
    except (ImportError, Exception) as e:
        logger.debug("TokenUsage not available: %s", e)
        for key in keys:
            token_stats_by_key[key.id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

    result = []
    for key in keys:
        token_stats = token_stats_by_key.get(key.id, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        result.append(
            {
                "id": key.id,
                "key": key.key,
                "name": key.name,
                "description": key.description,
                "quota_limit": key.quota_limit,
                "usage_count": key.usage_count,
                "is_active": key.is_active,
                "created_at": utc_to_beijing_iso(key.created_at),
                "last_used_at": utc_to_beijing_iso(key.last_used_at),
                "expires_at": utc_to_beijing_iso(key.expires_at),
                "usage_percentage": round((key.usage_count / key.quota_limit * 100), 1) if key.quota_limit else 0,
                "token_stats": token_stats,
            }
        )

    return result


@router.post("/admin/api_keys", dependencies=[Depends(require_admin)])
async def create_api_key_admin(
    request_body: dict,
    _http_request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: str = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Create new API key (ADMIN ONLY)"""
    name = request_body.get("name")
    description = request_body.get("description", "")
    quota_limit = request_body.get("quota_limit")
    expires_days = request_body.get("expires_days")

    if not name:
        error_msg = Messages.error("name_required", lang)
        raise HTTPException(status_code=400, detail=error_msg)

    key = await db.run_sync(lambda session: generate_api_key(name, description, quota_limit, session))

    if expires_days:
        key_record = (await db.execute(select(APIKey).where(APIKey.key == key))).scalars().first()
        if key_record:
            key_record.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
            await db.commit()

    return {
        "message": Messages.success("api_key_created", lang),
        "key": key,
        "name": name,
        "quota_limit": quota_limit or "unlimited",
        "warning": Messages.warning("api_key_save_warning", lang),
    }


@router.put("/admin/api_keys/{key_id}", dependencies=[Depends(require_admin)])
async def update_api_key_admin(
    key_id: int,
    request_body: dict,
    _http_request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: str = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Update API key settings (ADMIN ONLY)"""
    key_record = (await db.execute(select(APIKey).where(APIKey.id == key_id))).scalars().first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)

    if "name" in request_body:
        key_record.name = request_body["name"]
    if "description" in request_body:
        key_record.description = request_body["description"]
    if "quota_limit" in request_body:
        key_record.quota_limit = request_body["quota_limit"]
    if "is_active" in request_body:
        key_record.is_active = request_body["is_active"]
    if "usage_count" in request_body:
        key_record.usage_count = request_body["usage_count"]

    await db.commit()

    return {
        "message": Messages.success("api_key_updated", lang),
        "key": {
            "id": key_record.id,
            "name": key_record.name,
            "quota_limit": key_record.quota_limit,
            "usage_count": key_record.usage_count,
            "is_active": key_record.is_active,
        },
    }


@router.delete("/admin/api_keys/{key_id}", dependencies=[Depends(require_admin)])
async def delete_api_key_admin(
    key_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: str = Depends(get_language_dependency),
) -> Dict[str, str]:
    """Delete/revoke API key (ADMIN ONLY)"""
    key_record = (await db.execute(select(APIKey).where(APIKey.id == key_id))).scalars().first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)

    key_name = key_record.name
    await db.delete(key_record)
    await db.commit()

    return {"message": f"API key '{key_name}' deleted successfully"}


@router.put("/admin/api_keys/{key_id}/toggle", dependencies=[Depends(require_admin)])
async def toggle_api_key_admin(
    key_id: int,
    _request: Request,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    lang: str = Depends(get_language_dependency),
) -> Dict[str, Any]:
    """Toggle API key active status (ADMIN ONLY)"""
    key_record = (await db.execute(select(APIKey).where(APIKey.id == key_id))).scalars().first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)

    key_record.is_active = not key_record.is_active
    await db.commit()

    if key_record.is_active:
        message = Messages.success("api_key_activated", lang, key_record.name)
    else:
        message = Messages.success("api_key_deactivated", lang, key_record.name)

    return {"message": message, "is_active": key_record.is_active}
