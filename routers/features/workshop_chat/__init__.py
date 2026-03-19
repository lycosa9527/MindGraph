"""
Workshop Chat REST Router Package
====================================

Domain-split router structure inspired by Zulip's ``zerver/views/`` pattern.

Sub-modules mirror the service layer:

- ``channels``         Channel CRUD, join/leave, member listing, org members
- ``topics``           Topic lifecycle (study cases)
- ``messages``         Channel and topic messages, edit/delete
- ``direct_messages``  DM conversations and messaging

Shared concerns:

- ``schemas``          Pydantic request/response models
- ``dependencies``     Reusable access-control helpers (Zulip-style)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from routers.features.workshop_chat.channels import router as channels_router
from routers.features.workshop_chat.topics import router as topics_router
from routers.features.workshop_chat.messages import router as messages_router
from routers.features.workshop_chat.direct_messages import router as dm_router
from routers.features.workshop_chat.reactions import router as reactions_router
from routers.features.workshop_chat.files import router as files_router

router = APIRouter(prefix="/api/chat", tags=["Workshop Chat"])

router.include_router(channels_router)
router.include_router(topics_router)
router.include_router(messages_router)
router.include_router(dm_router)
router.include_router(reactions_router)
router.include_router(files_router)
