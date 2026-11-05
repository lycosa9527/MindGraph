"""
Knowledge Space API Router
===========================

Main router that combines all Knowledge Space sub-routers.

Author: lycosa9527
Made by: MindSpring Team

API endpoints for Personal Knowledge Space feature.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import importlib

from fastapi import APIRouter

# Import sub-routers from the knowledge_space package
# Using importlib to avoid naming conflict
documents = importlib.import_module("routers.api.knowledge_space.documents")
packages = importlib.import_module("routers.api.knowledge_space.packages")
settings = importlib.import_module("routers.api.knowledge_space.settings")
chat_handoff = importlib.import_module("routers.api.knowledge_space.chat_handoff")


router = APIRouter(prefix="/knowledge-space", tags=["knowledge-space"])

# Include all sub-routers (Document Summary mounts separately at /api/doc-summary).
router.include_router(documents.router)
router.include_router(packages.router)
router.include_router(settings.router)
router.include_router(chat_handoff.router)
