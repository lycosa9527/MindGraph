"""Gewe Group Member Database Model.

Stores WeChat group member information for caching and faster access.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Index

from .auth import Base


class GeweGroupMember(Base):
    """
    WeChat group member storage model.

    Similar to xxxbot-pad's group_members_db but uses PostgreSQL.
    Stores group member information for caching.
    """
    __tablename__ = 'gewe_group_members'

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(40), index=True, nullable=False, comment='Gewe app ID')
    group_wxid = Column(String(40), index=True, nullable=False, comment='Group wxid')
    member_wxid = Column(String(40), index=True, nullable=False, comment='Member wxid')
    nickname = Column(String(200), nullable=True, comment='Member nickname')
    display_name = Column(String(200), nullable=True, comment='Display name in group')
    avatar = Column(Text, nullable=True, comment='Avatar URL')
    inviter_wxid = Column(String(40), nullable=True, comment='Who invited this member')
    join_time = Column(DateTime, nullable=True, comment='Join time')
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment='Last update timestamp')
    extra_data = Column(Text, nullable=True, comment='Additional data as JSON')

    # Composite unique constraint: same member can only exist once per group per app
    __table_args__ = (
        Index('idx_app_group_member', 'app_id', 'group_wxid', 'member_wxid', unique=True),
        Index('idx_app_group', 'app_id', 'group_wxid'),
        Index('idx_app_member', 'app_id', 'member_wxid'),
    )
