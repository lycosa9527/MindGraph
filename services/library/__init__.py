"""
Library Service Module

Services for library PDF management and danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .library_service import LibraryService
from .pdf_importer import import_pdfs_from_folder
from .pdf_cover_extractor import (
    extract_pdf_cover,
    extract_all_covers,
    check_cover_extraction_available
)

__all__ = [
    "LibraryService",
    "import_pdfs_from_folder",
    "extract_pdf_cover",
    "extract_all_covers",
    "check_cover_extraction_available"
]
