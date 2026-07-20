"""Document Summary HTTP API — mounted at ``/api/doc-summary``.

Split from ``/api/knowledge-space`` so the canvas Document Summary UI can talk
to short product paths while package/document persistence stays shared.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

from routers.api.knowledge_space import chat_handoff

from . import documents, packages, session

router = APIRouter(prefix="/doc-summary", tags=["doc-summary"])

# Session + ownership first so ``/{package_id}/access|md`` stay reserved.
router.include_router(session.router)
router.include_router(packages.router)
router.include_router(documents.router)
# Chat handoff is Document Summary / file-reader only; remount under short prefix.
router.include_router(chat_handoff.router)

__all__ = ["router"]
