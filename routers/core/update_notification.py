from pathlib import Path
from typing import List, Optional
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel

from models.domain.auth import User
from services.utils.update_notifier import update_notifier
from utils.auth import get_current_user, is_admin

"""
Update Notification Router
===========================

API endpoints for managing and displaying update notifications.

Endpoints:
- GET /api/update-notification - Get notification for current user
- POST /api/update-notification/dismiss - Dismiss notification
- GET /api/admin/update-notification - Get notification config (admin)
- PUT /api/admin/update-notification - Set notification config (admin)
- DELETE /api/admin/update-notification - Disable notification (admin)
- POST /api/admin/update-notification/upload-image - Upload image (admin)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




logger = logging.getLogger(__name__)

router = APIRouter(tags=["Update Notification"])

# Announcement images folder
ANNOUNCEMENT_IMAGES_DIR = Path("static/announcement_images")
ANNOUNCEMENT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NotificationResponse(BaseModel):
    """Response model for notification content."""
    version: str
    title: str
    title_en: str
    message: str
    message_en: str
    show_changelog: bool
    changelog_items: List[str]
    changelog_items_en: List[str]


class NotificationConfigResponse(BaseModel):
    """Response model for full notification configuration (admin)."""
    enabled: bool
    version: str
    title: str
    title_en: str
    message: str
    message_en: str
    show_changelog: bool
    changelog_items: List[str]
    changelog_items_en: List[str]
    updated_at: Optional[str]
    dismissed_count: int


class NotificationSetRequest(BaseModel):
    """Request model for setting notification (admin)."""
    enabled: bool
    version: str = ""
    title: str = ""
    title_en: str = ""  # Kept for API compatibility
    message: str = ""
    message_en: str = ""  # Kept for API compatibility
    show_changelog: bool = False  # Kept for API compatibility
    changelog_items: List[str] = []  # Kept for API compatibility
    changelog_items_en: List[str] = []  # Kept for API compatibility


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@router.get("/api/update-notification")
async def get_update_notification(
    current_user: User = Depends(get_current_user)
):
    """
    Get update notification for current user.

    Returns notification content if user should see it,
    or null if notification is disabled or already dismissed.
    """
    try:
        notification = update_notifier.get_notification_for_user(current_user.id)

        if notification is None:
            return {"notification": None}

        return {"notification": notification}

    except Exception as e:
        logger.error("Failed to get notification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification"
        )


@router.post("/api/update-notification/dismiss")
async def dismiss_update_notification(
    current_user: User = Depends(get_current_user)
):
    """
    Dismiss the update notification for current user.

    User won't see the notification again for the current version.
    """
    try:
        success = update_notifier.dismiss_notification(current_user.id)

        if success:
            return {"message": "Notification dismissed"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dismiss notification"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to dismiss notification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss notification"
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/api/admin/update-notification")
async def get_notification_config(
    current_user: User = Depends(get_current_user)
):
    """
    Get full notification configuration (ADMIN ONLY).

    Returns current notification settings including dismissed count.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        notification = update_notifier.get_notification()
        dismissed_count = update_notifier.get_dismissed_count()

        return {
            "enabled": notification.get("enabled", False),
            "version": notification.get("version", ""),
            "title": notification.get("title", ""),
            "title_en": notification.get("title_en", ""),
            "message": notification.get("message", ""),
            "message_en": notification.get("message_en", ""),
            "show_changelog": notification.get("show_changelog", False),
            "changelog_items": notification.get("changelog_items", []),
            "changelog_items_en": notification.get("changelog_items_en", []),
            "updated_at": notification.get("updated_at"),
            "dismissed_count": dismissed_count
        }

    except Exception as e:
        logger.error("Failed to get notification config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification config"
        )


@router.put("/api/admin/update-notification")
async def set_notification_config(
    request: NotificationSetRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Set or update notification configuration (ADMIN ONLY).

    When version changes, all users will see the notification again.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        notification = update_notifier.set_notification(
            enabled=request.enabled,
            version=request.version,
            title=request.title,
            title_en=request.title_en,
            message=request.message,
            message_en=request.message_en,
            show_changelog=request.show_changelog,
            changelog_items=request.changelog_items,
            changelog_items_en=request.changelog_items_en
        )

        logger.info("Admin %s updated notification: enabled=%s", current_user.phone, request.enabled)

        return {
            "message": "Notification updated successfully",
            "notification": notification
        }

    except Exception as e:
        logger.error("Failed to set notification config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set notification config"
        )


@router.delete("/api/admin/update-notification")
async def disable_notification(
    current_user: User = Depends(get_current_user)
):
    """
    Disable the update notification (ADMIN ONLY).

    Quick way to turn off notification without changing content.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        notification = update_notifier.disable_notification()

        logger.info("Admin %s disabled update notification", current_user.phone)

        return {
            "message": "Notification disabled",
            "notification": notification
        }

    except Exception as e:
        logger.error("Failed to disable notification: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable notification"
        )


@router.post("/api/admin/update-notification/reset-dismissed")
async def reset_dismissed(
    current_user: User = Depends(get_current_user)
):
    """
    Reset all dismissed states (ADMIN ONLY).

    All users will see the notification again, even if they dismissed it.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        success = update_notifier.clear_dismissed()

        if success:
            logger.info("Admin %s reset all dismissed states", current_user.phone)
            return {"message": "All dismissed states cleared"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset dismissed states"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset dismissed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset dismissed states"
        )


@router.post("/api/admin/update-notification/upload-image")
async def upload_announcement_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload an image for the announcement (ADMIN ONLY).

    Supports PNG, JPG, GIF images up to 5MB.
    Returns the URL to embed in the announcement.
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 PNG, JPG, GIF, WebP 图片格式"
        )

    # Validate file size (5MB max)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片大小不能超过 5MB"
        )

    try:
        # Generate unique filename
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        filename = f"announcement_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = ANNOUNCEMENT_IMAGES_DIR / filename

        # Save file
        with open(filepath, "wb") as f:
            f.write(contents)

        # Return URL path
        image_url = f"/static/announcement_images/{filename}"

        logger.info("Admin %s uploaded announcement image: %s", current_user.phone, filename)

        return {
            "url": image_url,
            "filename": filename
        }

    except Exception as e:
        logger.error("Failed to upload image: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图片上传失败"
        )

