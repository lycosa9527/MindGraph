"""Admin error collection API — list, filter, and inspect captured errors."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from config.db_sessions import open_async_session
from models.domain.error_event import ErrorEvent, ErrorGroup
from routers.auth.dependencies import require_settings_errors
from services.monitoring.alert_dispatcher import AlertDispatcher
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter()


class ErrorEventItem(BaseModel):
    """Summary row for one error event."""

    id: int
    group_id: int
    fingerprint: str
    severity: str
    source: str
    component: str
    exception_type: str
    message: str
    request_id: str | None = None
    user_id: int | None = None
    http_path: str | None = None
    http_status: int | None = None
    created_at: datetime
    tags: dict[str, Any] | None = None


class ErrorEventDetail(ErrorEventItem):
    """Full error event including stacktrace."""

    stacktrace: str | None = None


class ErrorGroupItem(BaseModel):
    """Aggregated fingerprint group."""

    id: int
    fingerprint: str
    severity: str
    source: str
    component: str
    exception_type: str
    sample_message: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    muted: bool


class ErrorSummaryResponse(BaseModel):
    """Dashboard summary for error collection."""

    total_events_24h: int
    total_events_7d: int
    by_severity_24h: dict[str, int]
    by_source_24h: dict[str, int]
    top_groups_24h: list[ErrorGroupItem]
    alert_config: dict[str, Any]


class PaginatedEventsResponse(BaseModel):
    """Paginated error event list."""

    events: list[ErrorEventItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedGroupsResponse(BaseModel):
    """Paginated fingerprint group list."""

    groups: list[ErrorGroupItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class MuteGroupRequest(BaseModel):
    """Toggle alert muting for a fingerprint group."""

    muted: bool = Field(..., description="Whether to mute alerts for this fingerprint group")


def _event_item(row: ErrorEvent) -> ErrorEventItem:
    return ErrorEventItem(
        id=row.id,
        group_id=row.group_id,
        fingerprint=row.fingerprint,
        severity=row.severity,
        source=row.source,
        component=row.component,
        exception_type=row.exception_type,
        message=row.message,
        request_id=row.request_id,
        user_id=row.user_id,
        http_path=row.http_path,
        http_status=row.http_status,
        created_at=row.created_at,
        tags=row.tags,
    )


def _group_item(row: ErrorGroup) -> ErrorGroupItem:
    return ErrorGroupItem(
        id=row.id,
        fingerprint=row.fingerprint,
        severity=row.severity,
        source=row.source,
        component=row.component,
        exception_type=row.exception_type,
        sample_message=row.sample_message,
        occurrence_count=row.occurrence_count,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        muted=row.muted,
    )


def _pagination(total: int, page: int, page_size: int) -> dict[str, int]:
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


@router.get("/admin/errors/summary", dependencies=[Depends(require_settings_errors)])
async def error_collection_summary(scope: AdminScope = Depends(require_settings_errors)):
    """Summary stats for the error collection dashboard."""
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    try:
        async with open_async_session() as session:
            total_24h = int(
                (
                    await session.execute(
                        select(func.count()).select_from(ErrorEvent).where(ErrorEvent.created_at >= since_24h)
                    )
                ).scalar_one()
            )
            total_7d = int(
                (
                    await session.execute(
                        select(func.count()).select_from(ErrorEvent).where(ErrorEvent.created_at >= since_7d)
                    )
                ).scalar_one()
            )

            severity_rows = (
                await session.execute(
                    select(ErrorEvent.severity, func.count())
                    .where(ErrorEvent.created_at >= since_24h)
                    .group_by(ErrorEvent.severity)
                )
            ).all()
            by_severity = {str(sev): int(count) for sev, count in severity_rows}

            source_rows = (
                await session.execute(
                    select(ErrorEvent.source, func.count())
                    .where(ErrorEvent.created_at >= since_24h)
                    .group_by(ErrorEvent.source)
                )
            ).all()
            by_source = {str(src): int(count) for src, count in source_rows}

            top_groups_rows = (
                await session.execute(
                    select(ErrorGroup)
                    .where(ErrorGroup.last_seen_at >= since_24h)
                    .order_by(ErrorGroup.occurrence_count.desc(), ErrorGroup.last_seen_at.desc())
                    .limit(10)
                )
            ).scalars().all()

        logger.info("Admin %s viewed error collection summary", scope.actor.phone)
        return ErrorSummaryResponse(
            total_events_24h=total_24h,
            total_events_7d=total_7d,
            by_severity_24h=by_severity,
            by_source_24h=by_source,
            top_groups_24h=[_group_item(row) for row in top_groups_rows],
            alert_config=AlertDispatcher.config_summary(),
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Failed to load error summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load error summary",
        ) from exc


@router.get("/admin/errors/events", dependencies=[Depends(require_settings_errors)])
async def list_error_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: str | None = Query(None),
    source: str | None = Query(None),
    component: str | None = Query(None),
    hours: int = Query(168, ge=1, le=720),
    scope: AdminScope = Depends(require_settings_errors),
):
    """Paginated list of captured error events."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    filters = [ErrorEvent.created_at >= since]
    if severity:
        filters.append(ErrorEvent.severity == severity.lower())
    if source:
        filters.append(ErrorEvent.source == source.lower())
    if component:
        filters.append(ErrorEvent.component.ilike(f"%{component}%"))

    try:
        async with open_async_session() as session:
            total = int(
                (await session.execute(select(func.count()).select_from(ErrorEvent).where(*filters))).scalar_one()
            )
            rows = (
                await session.execute(
                    select(ErrorEvent)
                    .where(*filters)
                    .order_by(ErrorEvent.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()

        logger.info("Admin %s listed error events page=%s", scope.actor.phone, page)
        meta = _pagination(total, page, page_size)
        return PaginatedEventsResponse(events=[_event_item(row) for row in rows], **meta)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Failed to list error events: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list error events",
        ) from exc


@router.get("/admin/errors/events/{event_id}", dependencies=[Depends(require_settings_errors)])
async def get_error_event(
    event_id: int,
    scope: AdminScope = Depends(require_settings_errors),
):
    """Single error event with stacktrace."""
    try:
        async with open_async_session() as session:
            row = (await session.execute(select(ErrorEvent).where(ErrorEvent.id == event_id))).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error event not found")
        logger.info("Admin %s viewed error event %s", scope.actor.phone, event_id)
        item = _event_item(row)
        return ErrorEventDetail(**item.model_dump(), stacktrace=row.stacktrace)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Failed to load error event %s: %s", event_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load error event",
        ) from exc


@router.get("/admin/errors/groups", dependencies=[Depends(require_settings_errors)])
async def list_error_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: str | None = Query(None),
    source: str | None = Query(None),
    hours: int = Query(168, ge=1, le=720),
    scope: AdminScope = Depends(require_settings_errors),
):
    """Paginated fingerprint groups."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    filters = [ErrorGroup.last_seen_at >= since]
    if severity:
        filters.append(ErrorGroup.severity == severity.lower())
    if source:
        filters.append(ErrorGroup.source == source.lower())

    try:
        async with open_async_session() as session:
            total = int(
                (await session.execute(select(func.count()).select_from(ErrorGroup).where(*filters))).scalar_one()
            )
            rows = (
                await session.execute(
                    select(ErrorGroup)
                    .where(*filters)
                    .order_by(ErrorGroup.last_seen_at.desc(), ErrorGroup.occurrence_count.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).scalars().all()

        logger.info("Admin %s listed error groups page=%s", scope.actor.phone, page)
        meta = _pagination(total, page, page_size)
        return PaginatedGroupsResponse(groups=[_group_item(row) for row in rows], **meta)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Failed to list error groups: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list error groups",
        ) from exc


@router.put("/admin/errors/groups/{group_id}/mute", dependencies=[Depends(require_settings_errors)])
async def mute_error_group(
    group_id: int,
    body: MuteGroupRequest,
    scope: AdminScope = Depends(require_settings_errors),
):
    """Mute or unmute alert notifications for a fingerprint group."""
    try:
        async with open_async_session() as session:
            result = await session.execute(
                update(ErrorGroup).where(ErrorGroup.id == group_id).values(muted=body.muted)
            )
            await session.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error group not found")
        logger.info("Admin %s set group %s muted=%s", scope.actor.phone, group_id, body.muted)
        return {"group_id": group_id, "muted": body.muted}
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("Failed to mute error group %s: %s", group_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update error group",
        ) from exc


@router.get("/admin/errors/settings", dependencies=[Depends(require_settings_errors)])
async def error_collection_settings(scope: AdminScope = Depends(require_settings_errors)):
    """Read-only alert and retention configuration."""
    logger.info("Admin %s viewed error collection settings", scope.actor.phone)
    return AlertDispatcher.config_summary()
