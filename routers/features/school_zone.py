"""School Zone Router.

API endpoints for organization-scoped content sharing.
Users can share MindMate courses and MindGraph diagrams within their organization.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import User
from models.domain.school_zone import (
    SharedDiagram,
    SharedDiagramLike,
    SharedDiagramComment,
)
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/school-zone", tags=["School Zone"])


# =============================================================================
# Pydantic Models
# =============================================================================


class SharedDiagramCreate(BaseModel):
    """Request model for creating a shared diagram"""

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    content_type: str = Field(..., pattern="^(mindgraph|mindmate)$")
    category: Optional[str] = Field(None, max_length=50)
    diagram_data: Optional[str] = None
    thumbnail: Optional[str] = None


class SharedDiagramResponse(BaseModel):
    """Response model for a shared diagram"""

    id: str
    title: str
    description: Optional[str]
    content_type: str
    category: Optional[str]
    thumbnail: Optional[str]
    author: dict
    likes_count: int
    comments_count: int
    shares_count: int
    views_count: int
    created_at: str
    is_liked: bool = False

    class Config:
        """Pydantic configuration for SharedDiagramResponse."""

        from_attributes = True


class CommentCreate(BaseModel):
    """Request model for creating a comment"""

    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    """Response model for a comment"""

    id: int
    content: str
    author: dict
    created_at: str

    class Config:
        """Pydantic configuration for SharedDiagramResponse."""

        from_attributes = True


# =============================================================================
# Helper Functions
# =============================================================================


def require_organization(user: User):
    """Check that user belongs to an organization."""
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to an organization to access school zone",
        )


async def format_diagram_response(
    diagram: SharedDiagram,
    user_id: int,
    db: AsyncSession,
    liked_ids: Optional[set] = None,
) -> dict:
    """Format a SharedDiagram for API response.

    Pass ``liked_ids`` (a pre-loaded set of diagram IDs liked by ``user_id``)
    to avoid an extra SELECT per diagram on list endpoints.
    """
    if liked_ids is not None:
        is_liked = diagram.id in liked_ids
    else:
        result = await db.execute(
            select(SharedDiagramLike).where(
                SharedDiagramLike.diagram_id == diagram.id,
                SharedDiagramLike.user_id == user_id,
            )
        )
        is_liked = result.scalar_one_or_none() is not None

    return {
        "id": diagram.id,
        "title": diagram.title,
        "description": diagram.description,
        "content_type": diagram.content_type,
        "category": diagram.category,
        "thumbnail": diagram.thumbnail,
        "author": {
            "id": diagram.author_id,
            "name": diagram.author.name or "Anonymous",
            "avatar": diagram.author.avatar or "👤",
        },
        "likes_count": diagram.likes_count,
        "comments_count": diagram.comments_count,
        "shares_count": diagram.shares_count,
        "views_count": diagram.views_count,
        "created_at": diagram.created_at.isoformat() if diagram.created_at else "",
        "is_liked": is_liked,
    }


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/posts")
async def list_shared_diagrams(
    content_type: Optional[str] = Query(None, description="Filter by content type: mindgraph or mindmate"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort: Optional[str] = Query("newest", description="Sort order: newest, likes, comments"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List shared diagrams within the user's organization.

    Only returns diagrams shared by users in the same organization.
    """
    require_organization(current_user)

    stmt = (
        select(SharedDiagram)
        .options(selectinload(SharedDiagram.author))
        .where(
            SharedDiagram.organization_id == current_user.organization_id,
            SharedDiagram.is_active.is_(True),
        )
    )

    if content_type:
        stmt = stmt.where(SharedDiagram.content_type == content_type)

    if category:
        stmt = stmt.where(SharedDiagram.category == category)

    if sort == "likes":
        stmt = stmt.order_by(SharedDiagram.likes_count.desc())
    elif sort == "comments":
        stmt = stmt.order_by(SharedDiagram.comments_count.desc())
    else:
        stmt = stmt.order_by(SharedDiagram.created_at.desc())

    count_result = await db.execute(select(sa_count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    diagrams = result.scalars().all()

    # Batch-load likes for this user to avoid N+1 (one SELECT per diagram).
    liked_ids: set = set()
    if diagrams:
        diagram_ids = [d.id for d in diagrams]
        liked_rows = (
            await db.execute(
                select(SharedDiagramLike.diagram_id).where(
                    SharedDiagramLike.user_id == current_user.id,
                    SharedDiagramLike.diagram_id.in_(diagram_ids),
                )
            )
        ).all()
        liked_ids = {row[0] for row in liked_rows}

    posts = []
    for diagram in diagrams:
        posts.append(await format_diagram_response(diagram, current_user.id, db, liked_ids))

    return {
        "posts": posts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/posts")
async def create_shared_diagram(
    data: SharedDiagramCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Share a diagram with the organization.

    Creates a new shared diagram visible to all users in the same organization.
    """
    require_organization(current_user)

    diagram = SharedDiagram(
        title=data.title,
        description=data.description,
        content_type=data.content_type,
        category=data.category,
        diagram_data=data.diagram_data,
        thumbnail=data.thumbnail,
        organization_id=current_user.organization_id,
        author_id=current_user.id,
        created_at=datetime.now(UTC),
    )

    db.add(diagram)
    try:
        await db.commit()
        await db.refresh(diagram)
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "User %s shared diagram '%s' in org %s",
        current_user.id,
        data.title,
        current_user.organization_id,
    )

    return {
        "message": "Diagram shared successfully",
        "post": await format_diagram_response(diagram, current_user.id, db),
    }


@router.get("/posts/{post_id}")
async def get_shared_diagram(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific shared diagram.

    Returns the diagram data including the full diagram_data for rendering.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
            SharedDiagram.is_active.is_(True),
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    await db.execute(
        update(SharedDiagram).where(SharedDiagram.id == post_id).values(views_count=SharedDiagram.views_count + 1)
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    response = await format_diagram_response(diagram, current_user.id, db)
    response["diagram_data"] = diagram.diagram_data

    return response


@router.delete("/posts/{post_id}")
async def delete_shared_diagram(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a shared diagram.

    Only the author or organization managers can delete diagrams.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    is_author = diagram.author_id == current_user.id
    is_privileged = current_user.role in ("admin", "manager")

    if not is_author and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own diagrams",
        )

    diagram.is_active = False
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info("User %s deleted shared diagram %s", current_user.id, post_id)

    return {"message": "Diagram deleted successfully"}


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Toggle like on a shared diagram.

    If already liked, removes the like. Otherwise, adds a like.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
            SharedDiagram.is_active.is_(True),
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    result = await db.execute(
        select(SharedDiagramLike).where(
            SharedDiagramLike.diagram_id == post_id,
            SharedDiagramLike.user_id == current_user.id,
        )
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        await db.delete(existing_like)
        await db.execute(
            update(SharedDiagram)
            .where(SharedDiagram.id == post_id)
            .values(likes_count=func.greatest(SharedDiagram.likes_count - 1, 0))
        )
        is_liked = False
    else:
        like = SharedDiagramLike(
            diagram_id=post_id,
            user_id=current_user.id,
            created_at=datetime.now(UTC),
        )
        db.add(like)
        await db.execute(
            update(SharedDiagram).where(SharedDiagram.id == post_id).values(likes_count=SharedDiagram.likes_count + 1)
        )
        is_liked = True

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Re-fetch the authoritative count after the atomic update.
    result = await db.execute(select(SharedDiagram.likes_count).where(SharedDiagram.id == post_id))
    likes_count = result.scalar_one_or_none() or 0
    return {"is_liked": is_liked, "likes_count": likes_count}


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List comments on a shared diagram.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
            SharedDiagram.is_active.is_(True),
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    comment_stmt = (
        select(SharedDiagramComment)
        .options(joinedload(SharedDiagramComment.user))
        .where(
            SharedDiagramComment.diagram_id == post_id,
            SharedDiagramComment.is_active.is_(True),
        )
        .order_by(SharedDiagramComment.created_at.desc())
    )

    count_result = await db.execute(select(sa_count()).select_from(comment_stmt.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(comment_stmt.offset((page - 1) * page_size).limit(page_size))
    comments = result.unique().scalars().all()

    return {
        "comments": [
            {
                "id": c.id,
                "content": c.content,
                "author": {
                    "id": c.user_id,
                    "name": c.user.name or "Anonymous",
                    "avatar": c.user.avatar or "👤",
                },
                "created_at": (c.created_at.isoformat() if c.created_at else ""),
            }
            for c in comments
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Add a comment to a shared diagram.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
            SharedDiagram.is_active.is_(True),
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    comment = SharedDiagramComment(
        diagram_id=post_id,
        user_id=current_user.id,
        content=data.content,
        created_at=datetime.now(UTC),
    )

    db.add(comment)
    await db.execute(
        update(SharedDiagram).where(SharedDiagram.id == post_id).values(comments_count=SharedDiagram.comments_count + 1)
    )
    try:
        await db.commit()
        await db.refresh(comment)
    except Exception:
        await db.rollback()
        raise

    return {
        "message": "Comment added successfully",
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "author": {
                "id": current_user.id,
                "name": current_user.name or "Anonymous",
                "avatar": current_user.avatar or "👤",
            },
            "created_at": comment.created_at.isoformat(),
        },
    }


@router.delete("/posts/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a comment.

    Only the comment author or organization managers can delete comments.
    """
    require_organization(current_user)

    result = await db.execute(
        select(SharedDiagram).where(
            SharedDiagram.id == post_id,
            SharedDiagram.organization_id == current_user.organization_id,
        )
    )
    diagram = result.scalar_one_or_none()

    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")

    result = await db.execute(
        select(SharedDiagramComment).where(
            SharedDiagramComment.id == comment_id,
            SharedDiagramComment.diagram_id == post_id,
        )
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    is_comment_author = comment.user_id == current_user.id
    is_diagram_author = diagram.author_id == current_user.id
    is_privileged = current_user.role in ("admin", "manager")

    if not is_comment_author and not is_diagram_author and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )

    comment.is_active = False
    await db.execute(
        update(SharedDiagram)
        .where(SharedDiagram.id == post_id)
        .values(comments_count=func.greatest(SharedDiagram.comments_count - 1, 0))
    )

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "User %s deleted comment %s on diagram %s",
        current_user.id,
        comment_id,
        post_id,
    )

    return {"message": "Comment deleted successfully"}


@router.get("/categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    """
    Get list of available categories for school zone content.
    """
    require_organization(current_user)

    categories = [
        "教学设计",
        "学科资源",
        "班级管理",
        "教研活动",
        "学生作品",
        "校本课程",
    ]

    return {"categories": categories}
