"""
Library Service for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Service layer for library document management and danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from sqlalchemy.orm import Session

from services.library.library_document_mixin import LibraryDocumentMixin
from services.library.library_danmaku_mixin import LibraryDanmakuMixin
from services.library.library_bookmark_mixin import LibraryBookmarkMixin
from services.library.library_page_mixin import LibraryPageMixin


logger = logging.getLogger(__name__)


class LibraryService(
    LibraryDocumentMixin,
    LibraryDanmakuMixin,
    LibraryBookmarkMixin,
    LibraryPageMixin
):
    """
    Library management service.

    Handles document management and danmaku operations.
    Documents are image-based (pages exported as images).
    """

    # In-memory cache for available pages (per document)
    # Key: document_id, Value: (page_numbers_list, cache_timestamp)
    # Limited to 100 documents to prevent unbounded memory growth
    _available_pages_cache: Dict[int, Tuple[List[int], float]] = {}
    _cache_ttl = 300.0  # 5 minutes cache TTL
    _max_cache_size = 100  # Maximum number of documents to cache

    def __init__(self, db: Session, user_id: Optional[int] = None):
        """
        Initialize service.

        Args:
            db: Database session
            user_id: User ID (optional, for user-scoped operations)
        """
        self.db = db
        self.user_id = user_id

        # Configuration
        storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
        self.storage_dir = Path(storage_dir_env).resolve()
        self.covers_dir = self.storage_dir / "covers"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = int(os.getenv("LIBRARY_MAX_FILE_SIZE", "104857600"))  # 100MB default
        self.cover_max_width = int(os.getenv("LIBRARY_COVER_MAX_WIDTH", "400"))  # Max width
        # Max height for cover images (matches original)
        self.cover_max_height = int(os.getenv("LIBRARY_COVER_MAX_HEIGHT", "580"))
