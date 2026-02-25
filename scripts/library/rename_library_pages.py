"""
Rename library page files to sequential numbering while keeping book name.

Renames page image files in specific library folders to sequential pattern:
{bookname}_001.jpg, {bookname}_002.jpg, etc.

Only processes two specific books:
- 思维发展型课堂的理论与实践第一辑
- 思维发展型课堂的理论与实践第二辑

By default, runs in preview mode (dry-run). Use --live flag to actually rename files.

Usage:
    python scripts/library/rename_library_pages.py              # Preview only (default)
    python scripts/library/rename_library_pages.py --live       # Actually rename files
"""
import argparse
import importlib.util
import logging
import sys
from pathlib import Path

# Add project root to path before importing project modules
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

# Dynamic import to avoid Ruff E402 warning
_image_path_resolver = importlib.import_module('services.library.image_path_resolver')
detect_image_pattern = _image_path_resolver.detect_image_pattern
list_page_images = _image_path_resolver.list_page_images
IMAGE_EXTENSIONS = _image_path_resolver.IMAGE_EXTENSIONS

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def rename_library_pages(folder_path: Path, book_name: str, dry_run: bool = True) -> tuple[int, int]:
    """
    Rename page files in a library folder to sequential numbering while keeping book name.

    Args:
        folder_path: Path to folder containing page images
        book_name: Book name to use as prefix in filenames
        dry_run: If True, only show what would be renamed

    Returns:
        Tuple of (renamed_count, skipped_count)
    """
    if not folder_path.exists() or not folder_path.is_dir():
        logger.error("Folder does not exist: %s", folder_path)
        return (0, 0)

    # Find all image files
    image_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix in IMAGE_EXTENSIONS]

    if not image_files:
        logger.error("No image files found in folder: %s", folder_path)
        return (0, 0)

    # Detect current naming pattern
    pattern_info = detect_image_pattern(folder_path)
    if not pattern_info:
        logger.error("Could not detect image pattern in folder: %s", folder_path)
        logger.info("Sample files: %s", ', '.join([f.name for f in image_files[:5]]))
        return (0, 0)

    logger.info("Detected pattern: %s", pattern_info.get('pattern', 'unknown'))
    logger.info("Current prefix: %s, Extension: %s", pattern_info.get('prefix', ''), pattern_info.get('extension', ''))

    # List all pages with their current page numbers
    pages = list_page_images(folder_path)
    if not pages:
        logger.error("Could not extract page numbers from files")
        return (0, 0)

    logger.info("Found %d page images", len(pages))

    # Sort by page number
    pages.sort(key=lambda x: x[0])

    # Determine target naming pattern: {bookname}_001.jpg
    target_prefix = f"{book_name}_"
    target_extension = pattern_info.get('extension', '.jpg')

    # Determine padding based on total number of pages (for sequential numbering)
    total_pages = len(pages)
    padding = len(str(total_pages))

    logger.info("Target pattern: %s{number}%s", target_prefix, target_extension)
    logger.info("Total pages: %d, Padding: %d digits", total_pages, padding)

    renamed_count = 0
    skipped_count = 0

    logger.info("")
    logger.info("Renaming plan:")
    logger.info("-" * 80)

    # Create mapping of original page numbers to sequential page numbers
    # Renumber pages sequentially starting from 1
    rename_plan = []
    for sequential_num, (original_page_num, image_path) in enumerate(pages, start=1):
        # Construct target filename: {bookname}_001.jpg, {bookname}_002.jpg, etc.
        page_str = str(sequential_num).zfill(padding)
        target_filename = f"{target_prefix}{page_str}{target_extension}"
        target_path = folder_path / target_filename

        # Check if rename is needed
        if image_path.name == target_filename:
            logger.debug("  SKIP: %s (already correct)", image_path.name)
            skipped_count += 1
            continue

        rename_plan.append((original_page_num, sequential_num, image_path, target_filename, target_path))

    if not dry_run:
        # For live mode, use two-phase rename to avoid conflicts:
        # Phase 1: Rename all files to temporary names
        # Phase 2: Rename from temporary names to final names
        temp_files = []
        for original_page_num, sequential_num, image_path, target_filename, target_path in rename_plan:
            # Create temporary filename
            temp_filename = f"{image_path.stem}.tmp{image_path.suffix}"
            temp_path = folder_path / temp_filename

            # Check if temp filename conflicts
            if temp_path.exists():
                temp_filename = f"{image_path.stem}_{original_page_num}.tmp{image_path.suffix}"
                temp_path = folder_path / temp_filename

            try:
                image_path.rename(temp_path)
                temp_files.append((temp_path, target_path, original_page_num, sequential_num, image_path.name))
            except Exception as e:
                logger.error("  ERROR renaming %s to temp: %s", image_path.name, e)
                skipped_count += 1
                continue

        # Phase 2: Rename from temp to final
        for temp_path, target_path, original_page_num, sequential_num, original_name in temp_files:
            try:
                temp_path.rename(target_path)
                logger.info(
                    "  RENAMED: %s -> %s (was page %d, now page %d)",
                    original_name, target_path.name, original_page_num, sequential_num
                )
                renamed_count += 1
            except Exception as e:
                logger.error("  ERROR renaming temp %s to %s: %s", temp_path.name, target_path.name, e)
                skipped_count += 1
                continue
    else:
        # Dry-run mode: just show what would happen
        for original_page_num, sequential_num, image_path, target_filename, target_path in rename_plan:
            logger.info(
                "  RENAME: %s -> %s (was page %d, now page %d)",
                image_path.name, target_filename, original_page_num, sequential_num
            )
            renamed_count += 1

    logger.info("-" * 80)
    logger.info("Summary: %d files would be renamed, %d skipped", renamed_count, skipped_count)

    return (renamed_count, skipped_count)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Rename library page files to sequential numbering (specific books only)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually rename files (default is dry-run/preview mode)"
    )

    args = parser.parse_args()

    # Define the two specific books to process
    target_books = [
        "思维发展型课堂的理论与实践第一辑",
        "思维发展型课堂的理论与实践第二辑"
    ]

    # Resolve storage directory relative to project root
    storage_dir = _project_root / "storage" / "library"

    if not storage_dir.exists():
        logger.error("Storage directory not found: %s", storage_dir)
        sys.exit(1)

    dry_run = not args.live

    if dry_run:
        logger.info("=" * 80)
        logger.info("DRY-RUN MODE: No files will be renamed")
        logger.info("Use --live flag to actually rename files")
        logger.info("=" * 80)
        logger.info("")

    total_renamed = 0
    total_skipped = 0

    for book_name in target_books:
        folder_path = storage_dir / book_name

        if not folder_path.exists():
            logger.warning("Book folder not found: %s (skipping)", book_name)
            continue

        logger.info("")
        logger.info("=" * 80)
        logger.info("Processing: %s", book_name)
        logger.info("=" * 80)

        renamed, skipped = rename_library_pages(folder_path, book_name, dry_run=dry_run)
        total_renamed += renamed
        total_skipped += skipped

    logger.info("")
    logger.info("=" * 80)
    logger.info("OVERALL SUMMARY")
    logger.info("=" * 80)
    logger.info("Total files renamed: %d", total_renamed)
    logger.info("Total files skipped: %d", total_skipped)

    if dry_run:
        logger.info("")
        logger.info("=" * 80)
        logger.info("This was a dry-run. Use --live flag to actually rename files.")
        logger.info("=" * 80)

    if total_renamed == 0 and total_skipped > 0:
        logger.warning("No files were renamed. All files may already be correctly named.")
        sys.exit(0)
    elif total_renamed == 0:
        logger.error("No files were renamed.")
        sys.exit(1)
    else:
        logger.info("Successfully processed %d files across all books", total_renamed)
        sys.exit(0)


if __name__ == "__main__":
    main()
