"""Gewe Contact Database Model.

Stores WeChat contact information for caching and faster access.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Index

from .auth import Base


class GeweContact(Base):
    """
    WeChat contact storage model.

    Similar to xxxbot-pad's contacts_db but uses PostgreSQL.
    Stores contact information (friends, groups, official accounts) for caching.
    """
    __tablename__ = 'gewe_contacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(40), index=True, nullable=False, comment='Gewe app ID')
    wxid = Column(String(40), index=True, nullable=False, comment='Contact wxid (unique per app)')
    nickname = Column(String(200), nullable=True, comment='Contact nickname')
    remark = Column(String(200), nullable=True, comment='Contact remark')
    avatar = Column(Text, nullable=True, comment='Avatar URL')
    alias = Column(String(100), nullable=True, comment='WeChat alias')
    contact_type = Column(String(20), nullable=False, default='friend', comment='Type: friend, group, official')
    region = Column(String(100), nullable=True, comment='Region/location')
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='Last update timestamp')
    extra_data = Column(Text, nullable=True, comment='Additional data as JSON')

    # Composite unique constraint: same wxid can exist for different apps
    __table_args__ = (
        Index('idx_app_wxid', 'app_id', 'wxid', unique=True),
        Index('idx_app_type', 'app_id', 'contact_type'),
        Index('idx_app_nickname', 'app_id', 'nickname'),
    )
