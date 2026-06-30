"""Admin COS management router."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from routers.auth.dependencies import require_settings_cos
from services.admin import cos_admin_service
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth/admin/cos",
    tags=["Admin - COS Management"],
)


@router.get("/status")
async def cos_status(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """COS overview: connection, config, artifact health."""
    try:
        return cos_admin_service.get_cos_overview_status()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] status failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/backups")
async def cos_backups(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Local and COS PostgreSQL backup lists."""
    try:
        return cos_admin_service.get_cos_backups_payload()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] backups failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/backups/trigger")
async def cos_backup_trigger(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Run pg_dump backup now (includes COS upload when enabled)."""
    try:
        return await cos_admin_service.trigger_backup_now_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] backup trigger failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/crowdsec/status")
async def cos_crowdsec_status(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """CrowdSec local vs COS sync status."""
    try:
        return await cos_admin_service.get_crowdsec_status_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] crowdsec status failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/crowdsec/sync")
async def cos_crowdsec_sync(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Role-aware CrowdSec sync (network+upload or COS pull)."""
    try:
        return await cos_admin_service.trigger_crowdsec_sync_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] crowdsec sync failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/qdrant/status")
async def cos_qdrant_status(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Qdrant version and COS mirror status."""
    try:
        return await cos_admin_service.get_qdrant_status_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] qdrant status failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/qdrant/publish")
async def cos_qdrant_publish(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Publisher: fetch GitHub tarball and upload to COS."""
    try:
        return await cos_admin_service.trigger_qdrant_publish_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] qdrant publish failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/qdrant/install")
async def cos_qdrant_install(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Consumer: download Qdrant from COS and install (requires root)."""
    try:
        return await cos_admin_service.trigger_qdrant_install_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] qdrant install failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/celery/status")
async def cos_celery_status(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Celery version and COS mirror status."""
    try:
        return await cos_admin_service.get_celery_status_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] celery status failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/celery/publish")
async def cos_celery_publish(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Publisher: fetch PyPI wheel and upload to COS."""
    try:
        return await cos_admin_service.trigger_celery_publish_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] celery publish failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/celery/install")
async def cos_celery_install(
    _scope: AdminScope = Depends(require_settings_cos),
) -> Dict[str, Any]:
    """Consumer: download Celery wheel from COS and pip install."""
    try:
        return await cos_admin_service.trigger_celery_install_admin()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminCOS] celery install failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
