"""MindMate conversation folder API routes."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.mindmate_folders import (
    MindmateConversationFolder,
    MindmateFolder,
    generate_mindmate_folder_uuid,
)
from models.requests.requests_mindmate_folders import (
    MindmateFolderCreateRequest,
    MindmateFolderUpdateRequest,
    MindmateMoveFolderRequest,
)
from models.responses import (
    MindmateFolderAssignment,
    MindmateFolderItem,
    MindmateFolderListResponse,
    MindmateFolderResponse,
)
from utils.auth import get_current_user
from utils.db.session_open import user_rls_session

from .helpers import check_endpoint_rate_limit, get_rate_limit_identifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mindmate-folders"])


def _clean_folder_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Folder name is required")
    return cleaned


def _clean_folder_id(folder_id: str | None) -> str | None:
    if folder_id is None:
        return None
    cleaned = folder_id.strip()
    if not cleaned:
        return None
    try:
        uuid.UUID(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid folder id") from exc
    return cleaned


def _folder_item(folder: MindmateFolder, conversation_count: int) -> MindmateFolderItem:
    return MindmateFolderItem(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        conversation_count=conversation_count,
        created_at=folder.created_at or datetime.now(UTC),
        updated_at=folder.updated_at or datetime.now(UTC),
    )


def _folder_response(folder: MindmateFolder) -> MindmateFolderResponse:
    return MindmateFolderResponse(
        id=folder.id,
        name=folder.name,
        sort_order=folder.sort_order,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.get("/mindmate-folders", response_model=MindmateFolderListResponse)
async def list_mindmate_folders(
    request: Request,
    current_user=Depends(get_current_user),
):
    """List the current user's MindMate folders and conversation assignments."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_folders", identifier, max_requests=100, window_seconds=60)

    try:
        async with user_rls_session(current_user.id) as db:
            count_expr = func.count(MindmateConversationFolder.id)
            result = await db.execute(
                select(MindmateFolder, count_expr)
                .outerjoin(
                    MindmateConversationFolder,
                    MindmateConversationFolder.folder_id == MindmateFolder.id,
                )
                .where(MindmateFolder.user_id == current_user.id)
                .group_by(MindmateFolder.id)
                .order_by(MindmateFolder.sort_order.asc(), MindmateFolder.created_at.asc())
            )
            rows = result.all()
            assignment_rows = await db.execute(
                select(
                    MindmateConversationFolder.conversation_id,
                    MindmateConversationFolder.folder_id,
                ).where(MindmateConversationFolder.user_id == current_user.id)
            )
            assignments = assignment_rows.all()
    except SQLAlchemyError as exc:
        logger.error("[MindmateFolders] list failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to list folders") from exc

    folders = [_folder_item(folder, int(count or 0)) for folder, count in rows]
    return MindmateFolderListResponse(
        folders=folders,
        assignments=[
            MindmateFolderAssignment(conversation_id=conversation_id, folder_id=folder_id)
            for conversation_id, folder_id in assignments
        ],
    )


@router.post("/mindmate-folders", response_model=MindmateFolderResponse)
async def create_mindmate_folder(
    req: MindmateFolderCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Create a MindMate archive folder."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_folders", identifier, max_requests=60, window_seconds=60)

    max_sort = await db.scalar(
        select(func.max(MindmateFolder.sort_order)).where(MindmateFolder.user_id == current_user.id)
    )
    now = datetime.now(UTC)
    folder = MindmateFolder(
        id=generate_mindmate_folder_uuid(),
        user_id=current_user.id,
        name=_clean_folder_name(req.name),
        sort_order=(max_sort or 0) + 1,
        created_at=now,
        updated_at=now,
    )
    db.add(folder)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[MindmateFolders] create failed user=%s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to create folder") from exc
    await db.refresh(folder)

    logger.info("[MindmateFolders] Created folder %s for user %s", folder.id, current_user.id)
    return _folder_response(folder)


@router.patch("/mindmate-folders/{folder_id}", response_model=MindmateFolderResponse)
async def update_mindmate_folder(
    folder_id: str,
    req: MindmateFolderUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Rename a MindMate archive folder."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_folders", identifier, max_requests=60, window_seconds=60)

    result = await db.execute(
        select(MindmateFolder).where(
            MindmateFolder.id == folder_id,
            MindmateFolder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder.name = _clean_folder_name(req.name)
    folder.updated_at = datetime.now(UTC)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[MindmateFolders] update failed folder=%s: %s", folder_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update folder") from exc
    await db.refresh(folder)
    return _folder_response(folder)


@router.delete("/mindmate-folders/{folder_id}")
async def delete_mindmate_folder(
    folder_id: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Delete a folder. Conversations inside become uncategorized."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_folders", identifier, max_requests=60, window_seconds=60)

    result = await db.execute(
        select(MindmateFolder).where(
            MindmateFolder.id == folder_id,
            MindmateFolder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        await db.delete(folder)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[MindmateFolders] delete failed folder=%s: %s", folder_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete folder") from exc

    logger.info("[MindmateFolders] Deleted folder %s for user %s", folder_id, current_user.id)
    return {"success": True, "message": "Folder deleted"}


@router.put("/mindmate-folders/conversations/{conversation_id}")
async def move_mindmate_conversation(
    conversation_id: str,
    req: MindmateMoveFolderRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Assign a Dify conversation to a folder, or clear that assignment."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("mindmate_folders", identifier, max_requests=60, window_seconds=60)

    conv_id = conversation_id.strip()
    if not conv_id or len(conv_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid conversation id")

    folder_id = _clean_folder_id(req.folder_id)
    if folder_id is not None:
        folder = await db.scalar(
            select(MindmateFolder).where(
                MindmateFolder.id == folder_id,
                MindmateFolder.user_id == current_user.id,
            )
        )
        if folder is None:
            raise HTTPException(status_code=404, detail="Folder not found")

    existing = await db.scalar(
        select(MindmateConversationFolder).where(
            MindmateConversationFolder.user_id == current_user.id,
            MindmateConversationFolder.conversation_id == conv_id,
        )
    )
    try:
        if folder_id is None:
            if existing is not None:
                await db.execute(delete(MindmateConversationFolder).where(MindmateConversationFolder.id == existing.id))
        elif existing is None:
            db.add(
                MindmateConversationFolder(
                    user_id=current_user.id,
                    conversation_id=conv_id,
                    folder_id=folder_id,
                    created_at=datetime.now(UTC),
                )
            )
        else:
            existing.folder_id = folder_id
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("[MindmateFolders] move failed conv=%s: %s", conv_id, exc)
        raise HTTPException(status_code=500, detail="Failed to move conversation") from exc

    return {"success": True, "folder_id": folder_id}
