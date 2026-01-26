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
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

from config.database import SessionLocal
from models.domain.auth import UpdateNotification, UpdateNotificationDismissed

logger = logging.getLogger(__name__)


class UpdateNotifier:
    """
    Manages update notifications for the application.

    Stores notification state in database database for persistence.
    Uses immediate writes for multi-worker compatibility.
    """

    def __init__(self):
        """Initialize the UpdateNotifier."""
        logger.info("UpdateNotifier initialized (database storage)")

    def _get_db(self) -> Session:
        """Get a database session."""
        return SessionLocal()

    def _ensure_notification_exists(self, db: Session) -> UpdateNotification:
        """Ensure a notification record exists in the database (race-condition safe)."""
        notification = db.query(UpdateNotification).filter(UpdateNotification.id == 1).first()
        if not notification:
            try:
                notification = UpdateNotification(
                    id=1,
                    enabled=False,
                    version="",
                    title="",
                    message=""
                )
                db.add(notification)
                db.commit()
                db.refresh(notification)
            except Exception:
                # Race condition: another request created it first
                db.rollback()
                notification = db.query(UpdateNotification).filter(UpdateNotification.id == 1).first()
        return notification

    def get_notification(self) -> Dict:
        """
        Get the current notification configuration.

        Returns:
            Dict containing notification state and content
        """
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)
            return {
                "enabled": notification.enabled,
                "version": notification.version or "",
                "title": notification.title or "",
                "message": notification.message or "",
                "updated_at": notification.updated_at.isoformat() if notification.updated_at else None
            }
        finally:
            db.close()

    def set_notification(
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
        **kwargs
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
        _ = (title_en, message_en, show_changelog, changelog_items, changelog_items_en, kwargs)
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)
            old_version = notification.version or ""

            # Update fields
            notification.enabled = enabled
            notification.version = version
            notification.title = title
            notification.message = message
            notification.updated_at = datetime.utcnow()

            db.commit()

            # If version changed, clean up old dismissed records (not for current version)
            # This prevents table clutter while keeping current version dismissals if any
            if version and version != old_version:
                # Delete dismissed records for OLD versions only
                deleted = db.query(UpdateNotificationDismissed).filter(
                    UpdateNotificationDismissed.version != version
                ).delete(synchronize_session=False)
                db.commit()
                logger.info(
                    "Version changed from %s to %s, cleaned up %s old dismissed records",
                    old_version, version, deleted
                )

            logger.info("Update notification set: enabled=%s, version=%s", enabled, version)

            return {
                "enabled": notification.enabled,
                "version": notification.version or "",
                "title": notification.title or "",
                "message": notification.message or "",
                "updated_at": notification.updated_at.isoformat() if notification.updated_at else None
            }
        except Exception as e:
            db.rollback()
            logger.error("Failed to set notification: %s", e)
            raise
        finally:
            db.close()

    def should_show_notification(self, user_id: int) -> bool:
        """
        Check if notification should be shown to a specific user.

        Args:
            user_id: User's database ID

        Returns:
            True if notification should be shown, False otherwise
        """
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)

            # Check if notification is enabled
            if not notification.enabled:
                return False

            version = notification.version or ""
            if not version:
                return False

            # Check if user has dismissed this version
            dismissed = db.query(UpdateNotificationDismissed).filter(
                UpdateNotificationDismissed.user_id == int(user_id),
                UpdateNotificationDismissed.version == version
            ).first()

            return dismissed is None
        finally:
            db.close()

    def get_notification_for_user(self, user_id: int) -> Optional[Dict]:
        """
        Get notification content for a user if they should see it.

        Args:
            user_id: User's database ID

        Returns:
            Notification content if should show, None otherwise
        """
        if not self.should_show_notification(user_id):
            return None

        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)

            return {
                "version": notification.version or "",
                "title": notification.title or "",
                "title_en": "",  # For API compatibility
                "message": notification.message or "",
                "message_en": "",  # For API compatibility
                "show_changelog": False,
                "changelog_items": [],
                "changelog_items_en": []
            }
        finally:
            db.close()

    def dismiss_notification(self, user_id: int) -> bool:
        """
        Mark notification as dismissed for a user.

        Writes immediately to database for multi-worker compatibility.
        Uses unique constraint to prevent duplicates.

        Args:
            user_id: User's database ID

        Returns:
            True if successful
        """
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)
            version = notification.version or ""

            if not version:
                return True

            # Check if already dismissed (avoid duplicate insert attempt)
            existing = db.query(UpdateNotificationDismissed).filter(
                UpdateNotificationDismissed.user_id == int(user_id),
                UpdateNotificationDismissed.version == version
            ).first()

            if not existing:
                try:
                    dismissed = UpdateNotificationDismissed(
                        user_id=int(user_id),
                        version=version,
                        dismissed_at=datetime.utcnow()
                    )
                    db.add(dismissed)
                    db.commit()
                    logger.debug("User %s dismissed notification for version %s", user_id, version)
                except Exception:
                    # Race condition or duplicate - that's fine
                    db.rollback()

            return True
        except Exception as e:
            db.rollback()
            logger.error("Failed to dismiss notification: %s", e)
            return False
        finally:
            db.close()

    def disable_notification(self) -> Dict:
        """
        Disable the current notification.

        Returns:
            Updated notification configuration
        """
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)
            notification.enabled = False
            notification.updated_at = datetime.utcnow()

            db.commit()

            logger.info("Update notification disabled")

            return {
                "enabled": notification.enabled,
                "version": notification.version or "",
                "title": notification.title or "",
                "message": notification.message or "",
                "updated_at": notification.updated_at.isoformat() if notification.updated_at else None
            }
        except Exception as e:
            db.rollback()
            logger.error("Failed to disable notification: %s", e)
            raise
        finally:
            db.close()

    def clear_dismissed(self) -> bool:
        """
        Clear all dismissed states (show notification to all users again).

        Returns:
            True if successful
        """
        db = self._get_db()
        try:
            deleted = db.query(UpdateNotificationDismissed).delete()
            db.commit()

            logger.info("Cleared %s dismissed states", deleted)
            return True
        except Exception as e:
            db.rollback()
            logger.error("Failed to clear dismissed: %s", e)
            return False
        finally:
            db.close()

    def get_dismissed_count(self) -> int:
        """
        Get the number of users who have dismissed the notification.

        Returns:
            Count of dismissed users for current version
        """
        db = self._get_db()
        try:
            notification = self._ensure_notification_exists(db)
            version = notification.version or ""

            if not version:
                return 0

            return db.query(UpdateNotificationDismissed).filter(
                UpdateNotificationDismissed.version == version
            ).count()
        finally:
            db.close()

    def shutdown(self):
        """Graceful shutdown (no-op since we write immediately)."""
        logger.info("UpdateNotifier shutdown complete")


# Global singleton instance
update_notifier = UpdateNotifier()
