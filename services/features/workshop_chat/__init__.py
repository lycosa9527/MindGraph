"""
Workshop Chat Service Package
===============================

Domain-split service structure inspired by Zulip's ``zerver/actions/`` pattern.

Each sub-module owns one domain slice:

- ``channel_service``  Channel CRUD and membership
- ``topic_service``    Topic lifecycle (study cases)
- ``message_service``  Channel and topic messages
- ``dm_service``       Direct messages

Service instances are created at module level and re-exported here so
callers can import from a single location::

    from services.features.workshop_chat import channel_service, dm_service

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.features.workshop_chat.channel_service import channel_service
from services.features.workshop_chat.topic_service import topic_service
from services.features.workshop_chat.message_service import message_service
from services.features.workshop_chat.dm_service import dm_service
from services.features.workshop_chat.reaction_service import reaction_service
from services.features.workshop_chat.star_service import star_service
from services.features.workshop_chat.file_service import file_service

__all__ = [
    "channel_service",
    "topic_service",
    "message_service",
    "dm_service",
    "reaction_service",
    "star_service",
    "file_service",
]
