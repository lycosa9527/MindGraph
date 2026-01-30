"""
Image Path Resolution Service for Library.

Handles resolving page image paths from folder paths and page numbers.
Supports various image naming patterns (page_001.jpg, 001.jpg, page1.jpg, etc.).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}


def is_image_file(file_path: Path) -> bool:
    """Check if file is an image file."""
    return file_path.suffix in IMAGE_EXTENSIONS


def detect_image_pattern(folder_path: Path) -> Optional[dict]:
    """
    Detect the naming pattern used for images in a folder.

    Returns:
        Dict with pattern info: {
            'pattern': 'page_001', '001', 'page1', '1', etc.
            'has_prefix': bool,
            'prefix': str or None,
            'has_leading_zeros': bool,
            'extension': str
        }
        Or None if no images found
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return None

    # Find all image files
    image_files = [f for f in folder_path.iterdir() if f.is_file() and is_image_file(f)]

    if not image_files:
        return None

    # Try to detect pattern from first few images
    sample_files = sorted(image_files)[:10]

    # Try different patterns
    patterns_tried = []

    for img_file in sample_files:
        stem = img_file.stem
        ext = img_file.suffix

        # Pattern 1: page_001, page_002, etc.
        match = re.match(r'^page_(\d+)$', stem, re.IGNORECASE)
        if match:
            num = match.group(1)
            patterns_tried.append({
                'pattern': 'page_NNN',
                'has_prefix': True,
                'prefix': 'page_',
                'has_leading_zeros': len(num) > 1 and num[0] == '0',
                'extension': ext.lower(),
                'example': img_file.name
            })
            continue

        # Pattern 2: bookname_01, bookname_02, etc. (any prefix followed by underscore and number)
        # This must come before Pattern 3 (just numbers) to avoid false matches
        match = re.match(r'^(.+)_(\d+)$', stem)
        if match:
            prefix_part = match.group(1)
            num = match.group(2)
            # Only match if prefix_part is not empty and not just a number
            if prefix_part and not prefix_part.isdigit():
                patterns_tried.append({
                    'pattern': 'prefix_NN',
                    'has_prefix': True,
                    'prefix': prefix_part + '_',  # Include underscore in prefix
                    'has_leading_zeros': len(num) > 1 and num[0] == '0',
                    'extension': ext.lower(),
                    'example': img_file.name
                })
                continue

        # Pattern 3: 001, 002, etc. (just numbers)
        match = re.match(r'^(\d+)$', stem)
        if match:
            num = match.group(1)
            patterns_tried.append({
                'pattern': 'NNN',
                'has_prefix': False,
                'prefix': None,
                'has_leading_zeros': len(num) > 1 and num[0] == '0',
                'extension': ext.lower(),
                'example': img_file.name
            })
            continue

        # Pattern 4: page1, page2, etc. (no leading zeros)
        match = re.match(r'^page(\d+)$', stem, re.IGNORECASE)
        if match:
            num = match.group(1)
            patterns_tried.append({
                'pattern': 'pageN',
                'has_prefix': True,
                'prefix': 'page',
                'has_leading_zeros': False,
                'extension': ext.lower(),
                'example': img_file.name
            })
            continue

        # Pattern 5: 1, 2, etc. (no leading zeros, no prefix)
        match = re.match(r'^(\d+)$', stem)
        if match:
            num = match.group(1)
            patterns_tried.append({
                'pattern': 'N',
                'has_prefix': False,
                'prefix': None,
                'has_leading_zeros': False,
                'extension': ext.lower(),
                'example': img_file.name
            })
            continue

    if not patterns_tried:
        return None

    # Use most common pattern
    pattern_counts = {}
    for p in patterns_tried:
        key = (p['pattern'], p['has_leading_zeros'], p['extension'])
        pattern_counts[key] = pattern_counts.get(key, 0) + 1

    most_common = max(pattern_counts.items(), key=lambda x: x[1])
    most_common_pattern = most_common[0]

    # Find matching pattern dict
    for p in patterns_tried:
        if (p['pattern'], p['has_leading_zeros'], p['extension']) == most_common_pattern:
            return p

    return None


def list_page_images(folder_path: Path) -> List[Tuple[int, Path]]:
    """
    List all page images in a folder, sorted by page number.

    Returns:
        List of tuples: (page_number, image_path)
        Page numbers are 1-indexed
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return []

    # Detect pattern
    pattern_info = detect_image_pattern(folder_path)
    if not pattern_info:
        return []

    # Find all image files
    image_files = [f for f in folder_path.iterdir() if f.is_file() and is_image_file(f)]

    # Extract page numbers
    pages = []
    for img_file in image_files:
        page_num = extract_page_number(img_file, pattern_info)
        if page_num is not None:
            pages.append((page_num, img_file))

    # Sort by page number
    pages.sort(key=lambda x: x[0])

    return pages


def extract_page_number(image_path: Path, pattern_info: Optional[dict] = None) -> Optional[int]:
    """
    Extract page number from image filename.

    Args:
        image_path: Path to image file
        pattern_info: Pattern info from detect_image_pattern (optional, will detect if not provided)

    Returns:
        Page number (1-indexed) or None if cannot extract
    """
    if pattern_info is None:
        pattern_info = detect_image_pattern(image_path.parent)
        if not pattern_info:
            return None

    stem = image_path.stem
    prefix = pattern_info.get('prefix', '')

    # Remove prefix if present
    if prefix and stem.lower().startswith(prefix.lower()):
        # Handle both 'page_' and 'page' prefixes
        if prefix.endswith('_'):
            num_str = stem[len(prefix):]
        else:
            # Try with underscore separator
            if stem.lower().startswith(prefix.lower() + '_'):
                num_str = stem[len(prefix) + 1:]
            else:
                num_str = stem[len(prefix):]
    else:
        num_str = stem

    # Extract number
    match = re.match(r'^(\d+)$', num_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    return None


def resolve_page_image(folder_path: Path, page_number: int, pattern_info: Optional[dict] = None) -> Optional[Path]:
    """
    Resolve page image path for a specific page number.

    Args:
        folder_path: Path to folder containing page images
        page_number: Page number (1-indexed)
        pattern_info: Pattern info from detect_image_pattern (optional, will detect if not provided)

    Returns:
        Path to image file, or None if not found
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return None

    if pattern_info is None:
        pattern_info = detect_image_pattern(folder_path)
        if not pattern_info:
            return None

    prefix = pattern_info.get('prefix', '')
    has_leading_zeros = pattern_info.get('has_leading_zeros', False)
    extension = pattern_info.get('extension', '.jpg')

    # Construct filename based on pattern
    if has_leading_zeros:
        # Determine zero padding from existing files
        all_images = list_page_images(folder_path)
        if all_images:
            max_page = max(p[0] for p in all_images) if all_images else page_number
            padding = len(str(max_page))
            page_str = str(page_number).zfill(padding)
        else:
            page_str = str(page_number).zfill(3)  # Default to 3 digits
    else:
        page_str = str(page_number)

    # Construct filename
    if prefix:
        if prefix.endswith('_'):
            filename = f"{prefix}{page_str}{extension}"
        else:
            # Try with underscore separator first
            filename = f"{prefix}_{page_str}{extension}"
            if not (folder_path / filename).exists():
                filename = f"{prefix}{page_str}{extension}"
    else:
        filename = f"{page_str}{extension}"

    image_path = folder_path / filename

    if image_path.exists():
        return image_path

    # Try alternative extensions
    for ext in IMAGE_EXTENSIONS:
        alt_path = image_path.with_suffix(ext)
        if alt_path.exists():
            return alt_path

    # Fallback: search all images and find by page number
    all_images = list_page_images(folder_path)
    for page_num, img_path in all_images:
        if page_num == page_number:
            return img_path

    return None


def count_pages(folder_path: Path) -> int:
    """
    Count total number of pages in a folder.

    Args:
        folder_path: Path to folder containing page images

    Returns:
        Total number of pages (0 if folder doesn't exist or has no images)
    """
    pages = list_page_images(folder_path)
    return len(pages)
