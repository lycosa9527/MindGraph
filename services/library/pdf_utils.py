"""
PDF Utility Functions for Library

Provides PDF validation and path normalization utilities.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# PDF magic bytes signature
PDF_MAGIC_BYTES = b'%PDF'


def validate_pdf_file(pdf_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file is actually a PDF by checking magic bytes.

    Args:
        pdf_path: Path to the file to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file is a valid PDF, False otherwise
        - error_message: Error message if validation failed, None if valid
    """
    if not pdf_path.exists():
        return False, f"File does not exist: {pdf_path}"

    if not pdf_path.is_file():
        return False, f"Path is not a file: {pdf_path}"

    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(len(PDF_MAGIC_BYTES))

        if not header:
            return False, f"File is empty: {pdf_path}"

        if header.startswith(PDF_MAGIC_BYTES):
            return True, None

        return False, f"File does not have PDF magic bytes (found: {header[:10]})"

    except PermissionError:
        return False, f"Permission denied reading file: {pdf_path}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def normalize_library_path(file_path: Path, storage_dir: Path, project_root: Optional[Path] = None) -> str:
    """
    Normalize library file path to consistent relative format.

    Stores paths as relative paths from project root in format: storage/library/filename.pdf
    Works across WSL/Ubuntu/Windows by normalizing separators and using relative paths.

    Args:
        file_path: Path to the PDF file (can be absolute or relative)
        storage_dir: Storage directory (e.g., storage/library)
        project_root: Project root directory (default: current working directory)

    Returns:
        Normalized relative path string (e.g., "storage/library/filename.pdf")
    """
    if project_root is None:
        project_root = Path.cwd()

    # Resolve both paths to absolute
    file_path_resolved = file_path.resolve()
    storage_dir_resolved = storage_dir.resolve()
    project_root_resolved = project_root.resolve()

    # If file is in storage_dir, use relative path from project root
    try:
        if file_path_resolved.is_relative_to(storage_dir_resolved):
            # File is in storage_dir, get relative path from storage_dir
            relative_from_storage = file_path_resolved.relative_to(storage_dir_resolved)
            # Construct path: storage/library/filename.pdf
            normalized = storage_dir_resolved.relative_to(project_root_resolved) / relative_from_storage
            # Convert to string and normalize separators (always use /)
            return str(normalized).replace('\\', '/')
    except ValueError:
        pass

    # If file is relative to project root, use that
    try:
        if file_path_resolved.is_relative_to(project_root_resolved):
            normalized = file_path_resolved.relative_to(project_root_resolved)
            return str(normalized).replace('\\', '/')
    except ValueError:
        pass

    # Fallback: if file is just a filename, assume it's in storage_dir
    if not file_path_resolved.is_absolute() and '/' not in str(file_path) and '\\' not in str(file_path):
        normalized = storage_dir_resolved.relative_to(project_root_resolved) / file_path.name
        return str(normalized).replace('\\', '/')

    # Last resort: use filename only (will be resolved later)
    return file_path.name


def resolve_library_path(stored_path: str, storage_dir: Path, project_root: Optional[Path] = None) -> Optional[Path]:
    """
    Resolve a stored library path back to an actual file path.

    Handles multiple path formats:
    - Relative paths: storage/library/filename.pdf
    - Filename only: filename.pdf
    - Absolute paths (legacy)

    Args:
        stored_path: Path stored in database
        storage_dir: Storage directory
        project_root: Project root directory (default: current working directory)

    Returns:
        Resolved Path object, or None if not found
    """
    if project_root is None:
        project_root = Path.cwd()

    stored_path_obj = Path(stored_path)

    # Strategy 1: If stored path is relative and contains 'storage/library', resolve from project root
    if not stored_path_obj.is_absolute() and 'storage/library' in stored_path.replace('\\', '/'):
        try:
            resolved = project_root / stored_path.replace('\\', '/')
            if resolved.exists():
                return resolved.resolve()
        except Exception:
            pass

    # Strategy 2: If stored path is just filename, try storage_dir + filename
    if '/' not in stored_path and '\\' not in stored_path:
        try:
            resolved = storage_dir / stored_path
            if resolved.exists():
                return resolved.resolve()
        except Exception:
            pass

    # Strategy 3: Try as absolute path (legacy)
    if stored_path_obj.is_absolute():
        try:
            if stored_path_obj.exists():
                return stored_path_obj.resolve()
        except Exception:
            pass

    # Strategy 4: Try relative to current working directory
    try:
        resolved = Path.cwd() / stored_path.replace('\\', '/')
        if resolved.exists():
            return resolved.resolve()
    except Exception:
        pass

    return None
