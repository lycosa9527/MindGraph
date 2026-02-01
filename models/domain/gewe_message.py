"""Gewe Message Database Model.

Stores WeChat messages received via Gewe API for history and analysis.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index

from .auth import Base


class GeweMessage(Base):
    """
    WeChat message storage model.

    Similar to xxxbot-pad's Message model, but uses PostgreSQL.
    Stores all incoming WeChat messages for history tracking and analysis.
    """
    __tablename__ = 'gewe_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(Integer, index=True, nullable=False, comment='Message unique ID (integer)')
    app_id = Column(String(40), index=True, nullable=False, comment='Gewe app ID')
    sender_wxid = Column(String(40), index=True, nullable=False, comment='Message sender wxid')
    from_wxid = Column(String(40), index=True, nullable=False, comment='Message source wxid (chat)')
    msg_type = Column(Integer, nullable=False, comment='Message type (integer code)')
    content = Column(Text, nullable=True, comment='Message content')
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False, comment='Message timestamp')
    is_group = Column(Boolean, default=False, nullable=False, comment='Whether it is a group message')

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_app_msg_id', 'app_id', 'msg_id'),
        Index('idx_app_from_timestamp', 'app_id', 'from_wxid', 'timestamp'),
        Index('idx_app_sender_timestamp', 'app_id', 'sender_wxid', 'timestamp'),
    )
