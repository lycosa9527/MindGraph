"""
Update Notification Service
============================

Manages application update notifications shown to users after login.

Features:
- Enable/disable update notification display
- Configurable notification content (title, message, version)
- Tracks which users have seen the notification (in database)
- Batched writes for dismissed records (performance optimized)
- Persists notification state to database

Usage:
- Admin enables notification with version/message via API
- Users see a modal on login with blurred background
- Modal can be dismissed and won't show again for that version

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime
from typing import Dict, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from models.domain.auth import UpdateNotification, UpdateNotificationDismissed

logger = logging.getLogger(__name__)


class UpdateNotifier:
    """
    Manages update notifications for the application.

    Stores notification state in database for persistence.
    Uses immediate writes for multi-worker compatibility.
    """

    def __init__(self):
        """Initialize the UpdateNotifier."""
        logger.info("UpdateNotifier initialized (database storage)")

    async def _ensure_notification_exists(self, db: AsyncSession) -> UpdateNotification:
        """Ensure a notification record exists in the database (race-condition safe)."""
        result = await db.execute(select(UpdateNotification).where(UpdateNotification.id == 1))
        notification = result.scalar_one_or_none()
        if not notification:
            try:
                notification = UpdateNotification(id=1, enabled=False, version="", title="", message="")
                db.add(notification)
                await db.commit()
                await db.refresh(notification)
            except Exception:
                await db.rollback()
                result = await db.execute(select(UpdateNotification).where(UpdateNotification.id == 1))
                notification = result.scalar_one_or_none()
        return notification

    async def get_notification(self) -> Dict:
        """
        Get the current notification configuration.

        Returns:
            Dict containing notification state and content
        """
        async with AsyncSessionLocal() as db:
            notification = await self._ensure_notification_exists(db)
            return {
                "enabled": notification.enabled,
                "version": notification.version or "",
                "title": notification.title or "",
                "message": notification.message or "",
                "updated_at": notification.updated_at.isoformat() if notification.updated_at else None,
            }

    async def set_notification(
        self,
        enabled: bool,
        version: str = "",
        title: str = "",
        title_en: str = "",
        message: str = "",
        message_en: str = "",
        show_changelog: bool = False,
        changelog_items: Optional[list] = None,
        changelog_items_en: Optional[list] = None,
        **kwargs,
    ) -> Dict:
        """
        Set or update the notification configuration.

        Args:
            enabled: Whether to show the notification
            version: Version string for this update
            title: Notification title
            message: Notification message (supports HTML)

        Returns:
            Updated notification configuration
        """
        _ = (
            title_en,
            message_en,
            show_changelog,
            changelog_items,
            changelog_items_en,
            kwargs,
        )
        async with AsyncSessionLocal() as db:
            try:
                notification = await self._ensure_notification_exists(db)
                old_version = notification.version or ""

                notification.enabled = enabled
                notification.version = version
                notification.title = title
                notification.message = message
                notification.updated_at = datetime.now(UTC)

                await db.commit()

                if version and version != old_version:
                    result = await db.execute(
                        delete(UpdateNotificationDismissed).where(UpdateNotificationDismissed.version != version)
                    )
                    deleted = result.rowcount
                    await db.commit()
                    logger.info(
                        "Version changed from %s to %s, cleaned up %s old dismissed records",
                        old_version,
                        version,
                        deleted,
                    )

                logger.info("Update notification set: enabled=%s, version=%s", enabled, version)

                return {
                    "enabled": notification.enabled,
                    "version": notification.version or "",
                    "title": notification.title or "",
                    "message": notification.message or "",
                    "updated_at": notification.updated_at.isoformat() if notification.updated_at else None,
                }
            except Exception as exc:
                await db.rollback()
                logger.error("Failed to set notification: %s", exc)
                raise

    async def should_show_notification(self, user_id: int) -> bool:
        """
        Check if notification should be shown to a specific user.

        Args:
            user_id: User's database ID

        Returns:
            True if notification should be shown, False otherwise
        """
        async with AsyncSessionLocal() as db:
            notification = await self._ensure_notification_exists(db)

            if not notification.enabled:
                return False

            version = notification.version or ""
            if not version:
                return False

            result = await db.execute(
                select(UpdateNotificationDismissed).where(
                    UpdateNotificationDismissed.user_id == int(user_id),
                    UpdateNotificationDismissed.version == version,
                )
            )
            dismissed = result.scalar_one_or_none()

            return dismissed is None

    async def get_notification_for_user(self, user_id: int) -> Optional[Dict]:
        """
        Get notification content for a user if they should see it.

        Args:
            user_id: User's database ID

        Returns:
            Notification content if should show, None otherwise
        """
        if not await self.should_show_notification(user_id):
            return None

        async with AsyncSessionLocal() as db:
            notification = await self._ensure_notification_exists(db)

            return {
                "version": notification.version or "",
                "title": notification.title or "",
                "title_en": "",
                "message": notification.message or "",
                "message_en": "",
                "show_changelog": False,
                "changelog_items": [],
                "changelog_items_en": [],
            }

    async def dismiss_notification(self, user_id: int) -> bool:
        """
        Mark notification as dismissed for a user.

        Writes immediately to database for multi-worker compatibility.
        Uses unique constraint to prevent duplicates.

        Args:
            user_id: User's database ID

        Returns:
            True if successful
        """
        async with AsyncSessionLocal() as db:
            try:
                notification = await self._ensure_notification_exists(db)
                version = notification.version or ""

                if not version:
                    return True

                result = await db.execute(
                    select(UpdateNotificationDismissed).where(
                        UpdateNotificationDismissed.user_id == int(user_id),
                        UpdateNotificationDismissed.version == version,
                    )
                )
                existing = result.scalar_one_or_none()

                if not existing:
                    try:
                        dismissed = UpdateNotificationDismissed(
                            user_id=int(user_id),
                            version=version,
                            dismissed_at=datetime.now(UTC),
                        )
                        db.add(dismissed)
                        await db.commit()
                        logger.debug(
                            "User %s dismissed notification for version %s",
                            user_id,
                            version,
                        )
                    except Exception:
                        await db.rollback()

                return True
            except Exception as exc:
                await db.rollback()
                logger.error("Failed to dismiss notification: %s", exc)
                return False

    async def disable_notification(self) -> Dict:
        """
        Disable the current notification.

        Returns:
            Updated notification configuration
        """
        async with AsyncSessionLocal() as db:
            try:
                notification = await self._ensure_notification_exists(db)
                notification.enabled = False
                notification.updated_at = datetime.now(UTC)

                await db.commit()

                logger.info("Update notification disabled")

                return {
                    "enabled": notification.enabled,
                    "version": notification.version or "",
                    "title": notification.title or "",
                    "message": notification.message or "",
                    "updated_at": notification.updated_at.isoformat() if notification.updated_at else None,
                }
            except Exception as exc:
                await db.rollback()
                logger.error("Failed to disable notification: %s", exc)
                raise

    async def clear_dismissed(self) -> bool:
        """
        Clear all dismissed states (show notification to all users again).

        Returns:
            True if successful
        """
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(delete(UpdateNotificationDismissed))
                deleted = result.rowcount
                await db.commit()

                logger.info("Cleared %s dismissed states", deleted)
                return True
            except Exception as exc:
                await db.rollback()
                logger.error("Failed to clear dismissed: %s", exc)
                return False

    async def get_dismissed_count(self) -> int:
        """
        Get the number of users who have dismissed the notification.

        Returns:
            Count of dismissed users for current version
        """
        async with AsyncSessionLocal() as db:
            notification = await self._ensure_notification_exists(db)
            version = notification.version or ""

            if not version:
                return 0

            result = await db.execute(
                select(func.count(UpdateNotificationDismissed.id)).where(UpdateNotificationDismissed.version == version)
            )
            return result.scalar_one()

    def shutdown(self):
        """Graceful shutdown (no-op since we write immediately)."""
        logger.info("UpdateNotifier shutdown complete")


update_notifier = UpdateNotifier()
