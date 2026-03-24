"""
Library Path Utility Functions

Provides path normalization and resolution utilities for library files.
Used for images, covers, and other library assets.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_library_path(file_path: Path, storage_dir: Path, project_root: Optional[Path] = None) -> str:
    """
    Normalize library file path to consistent relative format.

    Stores paths as relative paths from project root in format: storage/library/filename
    Works across WSL/Ubuntu/Windows by normalizing separators and using relative paths.

    Args:
        file_path: Path to the file (can be absolute or relative)
        storage_dir: Storage directory (e.g., storage/library)
        project_root: Project root directory (default: current working directory)

    Returns:
        Normalized relative path string (e.g., "storage/library/filename")
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
            # Construct path: storage/library/filename
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
    - Relative paths: storage/library/filename
    - Filename only: filename
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
        except Exception as exc:
            logger.debug("Library path resolve from project root failed: %s", exc)

    # Strategy 2: If stored path is just filename, try storage_dir + filename
    if '/' not in stored_path and '\\' not in stored_path:
        try:
            resolved = storage_dir / stored_path
            if resolved.exists():
                return resolved.resolve()
        except Exception as exc:
            logger.debug("Library path resolve from storage dir failed: %s", exc)

    # Strategy 3: Try as absolute path (legacy)
    if stored_path_obj.is_absolute():
        try:
            if stored_path_obj.exists():
                return stored_path_obj.resolve()
        except Exception as exc:
            logger.debug("Library absolute path resolve failed: %s", exc)

    # Strategy 4: Try relative to current working directory
    try:
        resolved = Path.cwd() / stored_path.replace('\\', '/')
        if resolved.exists():
            return resolved.resolve()
    except Exception as exc:
        logger.debug("Library path resolve from cwd failed: %s", exc)

    # Strategy 5: Extract folder name and try storage_dir + folder_name
    # Handles paths from DB import (e.g. different server paths)
    folder_name = extract_folder_name_from_pages_dir_path(stored_path)
    if folder_name:
        try:
            resolved = storage_dir / folder_name
            if resolved.exists() and resolved.is_dir():
                return resolved.resolve()
        except Exception as exc:
            logger.debug("Library folder name resolve failed: %s", exc)

    return None


def extract_folder_name_from_pages_dir_path(pages_dir_path: str) -> str:
    """
    Extract the folder name (last path component) from a pages_dir_path.

    E.g. "storage/library/MyBook" -> "MyBook"

    Args:
        pages_dir_path: Stored path like "storage/library/folder_name"

    Returns:
        Folder name (last component) or empty string
    """
    if not pages_dir_path:
        return ""
    normalized = pages_dir_path.replace("\\", "/").rstrip("/")
    parts = normalized.split("/")
    return parts[-1] if parts else ""
