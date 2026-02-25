"""
User Activity Log Model
======================

Persists login and other user activity events for days-active computation.
Used for teacher usage analytics (distinct days with activity).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index

from models.domain.auth import Base


class UserActivityLog(Base):
    """
    User activity log for login and other events.

    Each row represents one activity event (e.g. login).
    Used to compute distinct days active for teacher usage classification.
    """
    __tablename__ = "user_activity_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activity_type = Column(String(50), nullable=False, default="login")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_user_activity_log_user_date", "user_id", "created_at"),
    )
