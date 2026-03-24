"""Community Router.

API endpoints for global community content sharing.
Users share MindGraph diagrams to the public community.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
import uuid as uuid_module
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from config.database import get_db
from models.domain.auth import User
from models.domain.community import CommunityPost, CommunityPostComment, CommunityPostLike
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.community_helpers import (
    COMMUNITY_THUMBNAIL_DIR,
    commit_post_update,
    delete_spec_json,
    delete_thumbnail,
    prepare_post_id_and_spec,
    resolve_update_thumbnail_path,
    save_post_and_thumbnail,
    save_spec_json,
    validate_and_parse_spec,
)
from services.redis.cache.redis_community_cache import invalidate_all, invalidate_post
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/community", tags=["Community"])

ALLOWED_DIAGRAM_TYPES = frozenset({
    "mind_map", "mindmap", "concept_map", "bubble_map", "double_bubble_map",
    "circle_map", "tree_map", "brace_map", "flow_map", "multi_flow_map",
    "bridge_map", "MindGraph", "MindMate",
})
ALLOWED_CATEGORIES = frozenset({
    "学习笔记", "教学设计", "读书感悟", "工作总结", "创意灵感", "知识整理",
})
ALLOWED_SORT = frozenset({"newest", "likes", "comments"})


def _format_post_response(
    post: CommunityPost,
    current_user: Optional[User],
    db: Session,
) -> dict:
    """Format CommunityPost for API response."""
    user_id = current_user.id if current_user else None
    is_liked = False
    if user_id:
        is_liked = (
            db.query(CommunityPostLike)
            .filter(
                CommunityPostLike.post_id == post.id,
                CommunityPostLike.user_id == user_id,
            )
            .first()
            is not None
        )

    thumbnail_url = None
    if post.thumbnail_path:
        thumbnail_url = f"/static/{post.thumbnail_path}"
    spec_json_url = f"/static/community/{post.id}.json"

    can_edit = _can_edit_post(post, current_user) if current_user else False

    return {
        "id": post.id,
        "title": post.title,
        "description": post.description,
        "category": post.category,
        "diagram_type": post.diagram_type,
        "thumbnail_url": thumbnail_url,
        "spec_json_url": spec_json_url,
        "author": {
            "id": post.author_id,
            "name": post.author.name or "Anonymous",
            "avatar": post.author.avatar or "👤",
            "organization": (
                post.author.organization.name
                if post.author.organization
                else None
            ),
        },
        "likes_count": post.likes_count,
        "comments_count": post.comments_count,
        "created_at": post.created_at.isoformat() if post.created_at else "",
        "is_liked": is_liked,
        "can_edit": can_edit,
    }


def _validate_diagram_type(value: str) -> None:
    """Validate diagram_type against whitelist."""
    if value not in ALLOWED_DIAGRAM_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid diagram_type. Allowed: {sorted(ALLOWED_DIAGRAM_TYPES)}",
        )


def _validate_category(value: Optional[str]) -> None:
    """Validate category against whitelist (None allowed)."""
    if value is not None and value not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Allowed: {sorted(ALLOWED_CATEGORIES)}",
        )


def _validate_sort(value: str) -> None:
    """Validate sort parameter."""
    if value not in ALLOWED_SORT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort. Allowed: {sorted(ALLOWED_SORT)}",
        )


def _validate_post_id(post_id: str) -> None:
    """Validate post_id is a valid UUID. Prevents path traversal in file ops."""
    try:
        uuid_module.UUID(post_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid post ID format",
        ) from None


def _can_edit_post(post: CommunityPost, current_user: User) -> bool:
    """True if current_user may edit/delete this post.

    Allowed: author, admin, superadmin, or manager of author's organization.
    """
    if post.author_id == current_user.id:
        return True
    if getattr(current_user, "role", None) in ("admin", "superadmin"):
        return True
    if getattr(current_user, "role", None) == "manager" and current_user.organization_id:
        author_org = getattr(post.author, "organization_id", None) if post.author else None
        return author_org == current_user.organization_id
    return False


def _can_delete_comment(comment: CommunityPostComment, current_user: User) -> bool:
    """True if current_user may delete this comment.

    Allowed: comment author, admin, or manager of comment author's organization.
    """
    if comment.user_id == current_user.id:
        return True
    if getattr(current_user, "role", None) in ("admin", "superadmin"):
        return True
    if getattr(current_user, "role", None) == "manager" and current_user.organization_id:
        author_org = getattr(comment.user, "organization_id", None) if comment.user else None
        return author_org == current_user.organization_id
    return False


@router.get("/posts")
def list_posts(
    _request: Request,
    mine: bool = Query(False, description="Only current user's posts"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter: MindGraph or MindMate"),
    category: Optional[str] = Query(None),
    sort: str = Query("newest", description="newest, likes, comments"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List community posts. Login required. Use mine=1 for 'Me' tab."""
    _validate_sort(sort)
    if type_filter:
        _validate_diagram_type(type_filter)
    if category:
        _validate_category(category)

    query = db.query(CommunityPost)

    if mine:
        query = query.filter(CommunityPost.author_id == current_user.id)

    if type_filter:
        query = query.filter(CommunityPost.diagram_type == type_filter)

    if category:
        query = query.filter(CommunityPost.category == category)

    if sort == "likes":
        query = query.order_by(CommunityPost.likes_count.desc())
    elif sort == "comments":
        query = query.order_by(CommunityPost.comments_count.desc())
    else:
        query = query.order_by(CommunityPost.created_at.desc())

    total = query.count()
    posts = (
        query.options(
            joinedload(CommunityPost.author).joinedload(User.organization)
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "posts": [
            _format_post_response(p, current_user, db)
            for p in posts
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/posts")
async def create_post(
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=2000),
    category: Optional[str] = Form(None, max_length=50),
    diagram_type: str = Form(...),
    spec: str = Form(...),
    thumbnail: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a community post. Multipart form with thumbnail file."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("community_create", identifier, max_requests=30, window_seconds=60)

    _validate_diagram_type(diagram_type)
    _validate_category(category)
    post_id, spec_obj = prepare_post_id_and_spec(spec)

    post = await save_post_and_thumbnail(
        post_id, spec_obj, thumbnail, title, description, category, diagram_type, current_user.id, db
    )

    logger.info("[Community] User %s created post %s", current_user.id, post_id)
    invalidate_all()

    return {
        "message": "Post created successfully",
        "post": _format_post_response(post, current_user, db),
    }


@router.get("/posts/{post_id}")
def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single post. Login required."""
    _validate_post_id(post_id)

    post = (
        db.query(CommunityPost)
        .options(
            joinedload(CommunityPost.author).joinedload(User.organization)
        )
        .filter(CommunityPost.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    spec_obj = None
    if post.spec:
        if isinstance(post.spec, dict):
            spec_obj = post.spec
        else:
            try:
                spec_obj = json.loads(post.spec)
            except (json.JSONDecodeError, TypeError):
                logger.warning("[Community] Corrupted spec for post %s", post_id)
    resp = _format_post_response(post, current_user, db)
    resp["spec"] = spec_obj

    # Lazy migration: ensure JSON file exists for older posts
    spec_json_path = COMMUNITY_THUMBNAIL_DIR / f"{post_id}.json"
    if spec_obj and not spec_json_path.exists():
        save_spec_json(post_id, spec_obj)

    return resp


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments on a post. Login required."""
    _validate_post_id(post_id)
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    query = (
        db.query(CommunityPostComment)
        .options(joinedload(CommunityPostComment.user))
        .filter(CommunityPostComment.post_id == post_id)
        .order_by(CommunityPostComment.created_at.asc())
    )
    total = query.count()
    comments = query.offset((page - 1) * page_size).limit(page_size).all()

    def _format_comment(c: CommunityPostComment) -> dict:
        return {
            "id": c.id,
            "content": c.content,
            "author": {
                "id": c.user_id,
                "name": c.user.name or "Anonymous",
                "avatar": c.user.avatar or "👤",
            },
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "can_delete": _can_delete_comment(c, current_user),
        }

    return {
        "comments": [_format_comment(c) for c in comments],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/posts/{post_id}/likes")
def list_likes(
    post_id: str,
    limit: int = Query(5, ge=1, le=20, description="Max names to return"),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List users who liked a post. Login required."""
    _validate_post_id(post_id)
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    likes = (
        db.query(CommunityPostLike)
        .options(joinedload(CommunityPostLike.user))
        .filter(CommunityPostLike.post_id == post_id)
        .order_by(CommunityPostLike.created_at.asc())
        .limit(limit)
        .all()
    )
    total = (
        db.query(CommunityPostLike).filter(CommunityPostLike.post_id == post_id).count()
    )
    names = [like.user.name or "Anonymous" for like in likes if like.user]

    return {"names": names, "total": total}


@router.post("/posts/{post_id}/comments")
async def create_comment(
    request: Request,
    post_id: str,
    content: str = Form(..., min_length=1, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a post."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "community_comment", identifier, max_requests=60, window_seconds=60
    )

    _validate_post_id(post_id)
    post = await asyncio.to_thread(
        lambda: db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = CommunityPostComment(
        post_id=post_id,
        user_id=current_user.id,
        content=content.strip(),
    )

    def _sync_save_comment():
        db.add(comment)
        db.execute(
            update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(comments_count=CommunityPost.comments_count + 1)
        )
        db.commit()
        db.refresh(comment)

    try:
        await asyncio.to_thread(_sync_save_comment)
    except Exception as exc:
        await asyncio.to_thread(db.rollback)
        logger.error("[Community] Failed to add comment on post %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add comment",
        ) from exc

    invalidate_post(post_id)
    invalidate_all()

    return {
        "message": "Comment added",
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "author": {
                "id": current_user.id,
                "name": current_user.name or "Anonymous",
                "avatar": current_user.avatar or "👤",
            },
            "created_at": comment.created_at.isoformat() if comment.created_at else "",
        },
    }


@router.delete("/posts/{post_id}/comments/{comment_id}")
async def delete_comment(
    request: Request,
    post_id: str,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a comment. Author, org manager (same org as commenter), or admin."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "community_comment_delete", identifier, max_requests=60, window_seconds=60
    )

    _validate_post_id(post_id)
    post = await asyncio.to_thread(
        lambda: db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = await asyncio.to_thread(
        lambda: (
            db.query(CommunityPostComment)
            .options(joinedload(CommunityPostComment.user))
            .filter(
                CommunityPostComment.id == comment_id,
                CommunityPostComment.post_id == post_id,
            )
            .first()
        )
    )
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    if not _can_delete_comment(comment, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        ) from None

    def _sync_delete_comment():
        db.delete(comment)
        db.execute(
            update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(
                comments_count=func.greatest(0, CommunityPost.comments_count - 1)
            )
        )
        db.commit()

    try:
        await asyncio.to_thread(_sync_delete_comment)
    except Exception as exc:
        await asyncio.to_thread(db.rollback)
        logger.error(
            "[Community] Failed to delete comment %s on post %s: %s",
            comment_id,
            post_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment",
        ) from exc

    invalidate_post(post_id)
    invalidate_all()

    logger.info(
        "User %s deleted comment %s on community post %s",
        current_user.id,
        comment_id,
        post_id,
    )
    return {"message": "Comment deleted"}


@router.put("/posts/{post_id}")
async def update_post(
    request: Request,
    post_id: str,
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form("", max_length=2000),
    category: Optional[str] = Form(None, max_length=50),
    diagram_type: str = Form(...),
    spec: str = Form(...),
    thumbnail: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a post. Author, org manager (same org), or admin."""
    _validate_post_id(post_id)
    post = await asyncio.to_thread(
        lambda: (
            db.query(CommunityPost)
            .options(
                joinedload(CommunityPost.author).joinedload(User.organization)
            )
            .filter(CommunityPost.id == post_id)
            .first()
        )
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if not _can_edit_post(post, current_user):
        edit_err = (
            "You can only edit your own posts, or posts from users in your "
            "organization (managers), or any post (admin)"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=edit_err)

    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit("community_update", identifier, max_requests=30, window_seconds=60)

    _validate_diagram_type(diagram_type)
    _validate_category(category)
    spec_obj = validate_and_parse_spec(spec)
    save_spec_json(post_id, spec_obj)

    post.title = title.strip()
    post.description = description.strip() or None
    post.category = category
    post.diagram_type = diagram_type
    post.spec = spec_obj
    post.thumbnail_path = await resolve_update_thumbnail_path(post, post_id, thumbnail)

    await asyncio.to_thread(commit_post_update, db, post)

    logger.info("[Community] User %s updated post %s", current_user.id, post_id)
    invalidate_post(post_id)
    invalidate_all()

    return {
        "message": "Post updated successfully",
        "post": _format_post_response(post, current_user, db),
    }


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a post. Author, org manager (same org), or admin."""
    _validate_post_id(post_id)
    post = (
        db.query(CommunityPost)
        .options(
            joinedload(CommunityPost.author).joinedload(User.organization)
        )
        .filter(CommunityPost.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if not _can_edit_post(post, current_user):
        delete_err = (
            "You can only delete your own posts, or posts from users in your "
            "organization (managers), or any post (admin)"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=delete_err)

    try:
        db.query(CommunityPostComment).filter(CommunityPostComment.post_id == post_id).delete()
        db.query(CommunityPostLike).filter(CommunityPostLike.post_id == post_id).delete()
        delete_thumbnail(post_id)
        delete_spec_json(post_id)
        db.delete(post)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("[Community] Failed to delete post %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete post",
        ) from exc

    logger.info("[Community] User %s deleted post %s", current_user.id, post_id)
    invalidate_post(post_id)
    invalidate_all()

    return {"message": "Post deleted successfully"}


@router.post("/posts/{post_id}/like")
async def toggle_like(
    request: Request,
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle like on a post."""
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "community_like", identifier, max_requests=120, window_seconds=60
    )

    _validate_post_id(post_id)
    post = await asyncio.to_thread(
        lambda: db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    existing = await asyncio.to_thread(
        lambda: (
            db.query(CommunityPostLike)
            .filter(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == current_user.id,
            )
            .first()
        )
    )

    def _sync_toggle():
        if existing:
            db.delete(existing)
            db.execute(
                update(CommunityPost)
                .where(CommunityPost.id == post_id)
                .values(likes_count=func.greatest(CommunityPost.likes_count - 1, 0))
            )
            return False
        db.add(CommunityPostLike(post_id=post_id, user_id=current_user.id))
        db.execute(
            update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(likes_count=CommunityPost.likes_count + 1)
        )
        return True

    is_liked = await asyncio.to_thread(_sync_toggle)

    def _sync_commit_refresh():
        db.commit()
        db.refresh(post)

    try:
        await asyncio.to_thread(_sync_commit_refresh)
    except IntegrityError:
        def _sync_handle_integrity():
            db.rollback()
            db.refresh(post)
            return (
                db.query(CommunityPostLike)
                .filter(
                    CommunityPostLike.post_id == post_id,
                    CommunityPostLike.user_id == current_user.id,
                )
                .first()
            )

        existing_after = await asyncio.to_thread(_sync_handle_integrity)
        return {
            "is_liked": existing_after is not None,
            "likes_count": post.likes_count,
        }
    except Exception as exc:
        await asyncio.to_thread(db.rollback)
        logger.error("[Community] Failed to toggle like on post %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle like",
        ) from exc

    invalidate_post(post_id)
    invalidate_all()

    return {"is_liked": is_liked, "likes_count": post.likes_count}
