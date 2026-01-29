"""
Library Service Module

Services for library PDF management and danmaku operations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from .library_service import LibraryService
from .pdf_importer import (
    import_pdfs_from_folder,
    auto_import_new_pdfs,
    optimize_existing_library_pdfs
)
from .pdf_cover_extractor import (
    extract_pdf_cover,
    extract_all_covers,
    regenerate_all_covers,
    regenerate_covers_from_database,
    optimize_oversized_covers,
    check_cover_extraction_available
)
from .pdf_optimizer import (
    analyze_pdf_structure,
    should_optimize_pdf,
    optimize_pdf,
    check_qpdf_available,
    PDFStructureInfo
)
from .sync_validator import validate_library_sync, sync_library, SyncReport
from .auto_import_scheduler import start_library_auto_import_scheduler

__all__ = [
    "LibraryService",
    "import_pdfs_from_folder",
    "auto_import_new_pdfs",
    "optimize_existing_library_pdfs",
    "extract_pdf_cover",
    "extract_all_covers",
    "regenerate_all_covers",
    "regenerate_covers_from_database",
    "optimize_oversized_covers",
    "check_cover_extraction_available",
    "analyze_pdf_structure",
    "should_optimize_pdf",
    "optimize_pdf",
    "check_qpdf_available",
    "PDFStructureInfo",
    "validate_library_sync",
    "sync_library",
    "SyncReport",
    "start_library_auto_import_scheduler"
]
