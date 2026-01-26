"""School Zone Router.

API endpoints for organization-scoped content sharing.
Users can share MindMate courses and MindGraph diagrams within their organization.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.school_zone import SharedDiagram, SharedDiagramLike, SharedDiagramComment
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
            detail="You must belong to an organization to access school zone"
        )


def format_diagram_response(diagram: SharedDiagram, user_id: int, db: Session) -> dict:
    """Format a SharedDiagram for API response"""
    # Check if current user has liked this diagram
    is_liked = db.query(SharedDiagramLike).filter(
        SharedDiagramLike.diagram_id == diagram.id,
        SharedDiagramLike.user_id == user_id
    ).first() is not None

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
            "avatar": diagram.author.avatar or "👤"
        },
        "likes_count": diagram.likes_count,
        "comments_count": diagram.comments_count,
        "shares_count": diagram.shares_count,
        "views_count": diagram.views_count,
        "created_at": diagram.created_at.isoformat() if diagram.created_at else "",
        "is_liked": is_liked
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
    db: Session = Depends(get_db)
):
    """
    List shared diagrams within the user's organization.

    Only returns diagrams shared by users in the same organization.
    """
    require_organization(current_user)

    # Build query - filter by organization
    query = db.query(SharedDiagram).filter(
        SharedDiagram.organization_id == current_user.organization_id,
        SharedDiagram.is_active is True
    )

    # Apply content type filter
    if content_type:
        query = query.filter(SharedDiagram.content_type == content_type)

    # Apply category filter
    if category:
        query = query.filter(SharedDiagram.category == category)

    # Apply sorting
    if sort == "likes":
        query = query.order_by(SharedDiagram.likes_count.desc())
    elif sort == "comments":
        query = query.order_by(SharedDiagram.comments_count.desc())
    else:  # newest (default)
        query = query.order_by(SharedDiagram.created_at.desc())

    # Get total count
    total = query.count()

    # Paginate
    diagrams = query.offset((page - 1) * page_size).limit(page_size).all()

    # Format response
    posts = [format_diagram_response(d, current_user.id, db) for d in diagrams]

    return {
        "posts": posts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.post("/posts")
async def create_shared_diagram(
    data: SharedDiagramCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Share a diagram with the organization.

    Creates a new shared diagram visible to all users in the same organization.
    """
    require_organization(current_user)

    # Create the shared diagram
    diagram = SharedDiagram(
        title=data.title,
        description=data.description,
        content_type=data.content_type,
        category=data.category,
        diagram_data=data.diagram_data,
        thumbnail=data.thumbnail,
        organization_id=current_user.organization_id,
        author_id=current_user.id,
        created_at=datetime.utcnow()
    )

    db.add(diagram)
    db.commit()
    db.refresh(diagram)

    logger.info("User %s shared diagram '%s' in org %s", current_user.id, data.title, current_user.organization_id)

    return {
        "message": "Diagram shared successfully",
        "post": format_diagram_response(diagram, current_user.id, db)
    }


@router.get("/posts/{post_id}")
async def get_shared_diagram(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific shared diagram.

    Returns the diagram data including the full diagram_data for rendering.
    """
    require_organization(current_user)

    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id,
        SharedDiagram.is_active is True
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Increment view count
    diagram.views_count += 1
    db.commit()

    response = format_diagram_response(diagram, current_user.id, db)
    response["diagram_data"] = diagram.diagram_data

    return response


@router.delete("/posts/{post_id}")
async def delete_shared_diagram(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a shared diagram.

    Only the author or organization managers can delete diagrams.
    """
    require_organization(current_user)

    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Check permission: author or manager/admin
    is_author = diagram.author_id == current_user.id
    is_privileged = current_user.role in ('admin', 'manager')

    if not is_author and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own diagrams"
        )

    # Soft delete
    diagram.is_active = False
    db.commit()

    logger.info("User %s deleted shared diagram %s", current_user.id, post_id)

    return {"message": "Diagram deleted successfully"}


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle like on a shared diagram.

    If already liked, removes the like. Otherwise, adds a like.
    """
    require_organization(current_user)

    # Check diagram exists and is in user's org
    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id,
        SharedDiagram.is_active is True
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Check if already liked
    existing_like = db.query(SharedDiagramLike).filter(
        SharedDiagramLike.diagram_id == post_id,
        SharedDiagramLike.user_id == current_user.id
    ).first()

    if existing_like:
        # Remove like
        db.delete(existing_like)
        diagram.likes_count = max(0, diagram.likes_count - 1)
        is_liked = False
    else:
        # Add like
        like = SharedDiagramLike(
            diagram_id=post_id,
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )
        db.add(like)
        diagram.likes_count += 1
        is_liked = True

    db.commit()

    return {
        "is_liked": is_liked,
        "likes_count": diagram.likes_count
    }


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List comments on a shared diagram.
    """
    require_organization(current_user)

    # Check diagram exists and is in user's org
    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id,
        SharedDiagram.is_active is True
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Get comments
    query = db.query(SharedDiagramComment).filter(
        SharedDiagramComment.diagram_id == post_id,
        SharedDiagramComment.is_active is True
    ).order_by(SharedDiagramComment.created_at.desc())

    total = query.count()
    comments = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "comments": [
            {
                "id": c.id,
                "content": c.content,
                "author": {
                    "id": c.user_id,
                    "name": c.user.name or "Anonymous",
                    "avatar": c.user.avatar or "👤"
                },
                "created_at": c.created_at.isoformat() if c.created_at else ""
            }
            for c in comments
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a comment to a shared diagram.
    """
    require_organization(current_user)

    # Check diagram exists and is in user's org
    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id,
        SharedDiagram.is_active is True
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Create comment
    comment = SharedDiagramComment(
        diagram_id=post_id,
        user_id=current_user.id,
        content=data.content,
        created_at=datetime.utcnow()
    )

    db.add(comment)
    diagram.comments_count += 1
    db.commit()
    db.refresh(comment)

    return {
        "message": "Comment added successfully",
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "author": {
                "id": current_user.id,
                "name": current_user.name or "Anonymous",
                "avatar": current_user.avatar or "👤"
            },
            "created_at": comment.created_at.isoformat()
        }
    }


@router.delete("/posts/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a comment.

    Only the comment author or organization managers can delete comments.
    """
    require_organization(current_user)

    # SECURITY: First verify the diagram belongs to user's organization
    diagram = db.query(SharedDiagram).filter(
        SharedDiagram.id == post_id,
        SharedDiagram.organization_id == current_user.organization_id
    ).first()

    if not diagram:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found"
        )

    # Now get the comment
    comment = db.query(SharedDiagramComment).filter(
        SharedDiagramComment.id == comment_id,
        SharedDiagramComment.diagram_id == post_id
    ).first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )

    # Check permission: comment author, diagram author, or manager/admin
    is_comment_author = comment.user_id == current_user.id
    is_diagram_author = diagram.author_id == current_user.id
    is_privileged = current_user.role in ('admin', 'manager')

    if not is_comment_author and not is_diagram_author and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments"
        )

    # Soft delete
    comment.is_active = False
    diagram.comments_count = max(0, diagram.comments_count - 1)

    db.commit()

    logger.info("User %s deleted comment %s on diagram %s", current_user.id, comment_id, post_id)

    return {"message": "Comment deleted successfully"}


@router.get("/categories")
async def list_categories(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available categories for school zone content.
    """
    require_organization(current_user)

    # Return predefined categories
    categories = [
        "教学设计",
        "学科资源",
        "班级管理",
        "教研活动",
        "学生作品",
        "校本课程"
    ]

    return {"categories": categories}
