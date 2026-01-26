"""
Dashboard Activity Model
========================

Stores activity history for the public dashboard.
Activities are persisted to database for history retention across page refreshes.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Index

from models.domain.auth import Base


class DashboardActivity(Base):
    """
    Dashboard activity history model.

    Stores user activities displayed in the public dashboard activity panel.
    Activities persist across page refreshes and are kept for historical analysis.
    """
    __tablename__ = "dashboard_activities"

    id = Column(Integer, primary_key=True, index=True)

    # Activity details
    user_id = Column(Integer, nullable=True, index=True)  # User ID (can be null for anonymous)
    user_name = Column(String(100), nullable=True)  # Masked/anonymized username
    action = Column(String(50), nullable=False)  # e.g., "generated", "created"
    diagram_type = Column(String(50), nullable=False)  # e.g., "bubble_map", "mind_map"
    topic = Column(String(500), nullable=True)  # Optional topic/subject

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Index for efficient queries (most recent first)
    __table_args__ = (
        Index('idx_dashboard_activities_created_at', 'created_at'),
    )

