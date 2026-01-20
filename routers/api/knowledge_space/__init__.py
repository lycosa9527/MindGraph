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
documents = importlib.import_module('routers.api.knowledge_space.documents')
queries = importlib.import_module('routers.api.knowledge_space.queries')
metadata = importlib.import_module('routers.api.knowledge_space.metadata')
relationships = importlib.import_module('routers.api.knowledge_space.relationships')
evaluation = importlib.import_module('routers.api.knowledge_space.evaluation')
chunk_test_execution = importlib.import_module('routers.api.knowledge_space.chunk_test_execution')
chunk_test_documents = importlib.import_module('routers.api.knowledge_space.chunk_test_documents')
chunk_test_evaluation = importlib.import_module('routers.api.knowledge_space.chunk_test_evaluation')
chunk_test_utils = importlib.import_module('routers.api.knowledge_space.chunk_test_utils')
debug = importlib.import_module('routers.api.knowledge_space.debug')


router = APIRouter(prefix="/knowledge-space", tags=["knowledge-space"])

# Include all sub-routers
router.include_router(documents.router)
router.include_router(queries.router)
router.include_router(metadata.router)
router.include_router(relationships.router)
router.include_router(evaluation.router)
router.include_router(chunk_test_execution.router)
router.include_router(chunk_test_documents.router)
router.include_router(chunk_test_evaluation.router)
router.include_router(chunk_test_utils.router)
router.include_router(debug.router)