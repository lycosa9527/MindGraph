"""
Unified Library Import Script

Command-line script to import PDFs and extract covers for the library.

This script provides a unified interface for:
1. Importing PDFs from storage/library/ into the database
2. Extracting cover images from PDFs
3. Both operations combined

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import argparse
import importlib
import io
import logging
import sys
import traceback
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect as sqlalchemy_inspect

# Add project root to path before importing project modules
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set up logging first
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import project modules after modifying sys.path
# config.database imports library models, ensuring they're registered with Base.metadata
_config_db_module = importlib.import_module('config.database')
_pdf_importer_module = importlib.import_module('services.library.pdf_importer')
_pdf_cover_module = importlib.import_module('services.library.pdf_cover_extractor')
_library_module = importlib.import_module('services.library')

SessionLocal = _config_db_module.SessionLocal
import_pdfs_from_folder = _pdf_importer_module.import_pdfs_from_folder
extract_all_covers = _pdf_cover_module.extract_all_covers
check_cover_extraction_available = _pdf_cover_module.check_cover_extraction_available
LibraryService = _library_module.LibraryService


def import_pdfs(
    extract_covers: bool = True,
    dpi: int = 200,
    library_dir: Optional[Path] = None,
    covers_dir: Optional[Path] = None
) -> None:
    """
    Import PDFs from library directory into database.

    Args:
        extract_covers: If True, extract covers for PDFs that don't have them (default: True)
        dpi: DPI for cover extraction
        library_dir: Custom library directory (uses default if None)
        covers_dir: Custom covers directory (uses default if None)
    """
    db = SessionLocal()
    try:
        # Check if library_documents table exists
        inspector = sqlalchemy_inspect(db.bind)
        existing_tables = inspector.get_table_names()

        if "library_documents" not in existing_tables:
            print("\n" + "=" * 80)
            print("ERROR: Library tables do not exist in the database!")
            print("=" * 80)
            print("\nPlease run database migrations first:")
            print("  python scripts/db/run_migrations.py")
            print("\nThis will create the required library tables:")
            print("  - library_documents")
            print("  - library_danmaku")
            print("  - library_danmaku_likes")
            print("  - library_danmaku_replies")
            print("  - library_bookmarks")
            print("=" * 80)
            sys.exit(1)

        print("Importing PDFs from storage/library/...")
        print()

        imported_count, skipped_count = import_pdfs_from_folder(
            db=db,
            library_dir=library_dir,
            covers_dir=covers_dir,
            extract_covers=extract_covers,
            dpi=dpi
        )

        print("=" * 80)
        print(f"Import complete: {imported_count} imported, {skipped_count} skipped")

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        if "library_documents" in error_msg and "does not exist" in error_msg:
            print("\n" + "=" * 80)
            print("ERROR: Library tables do not exist in the database!")
            print("=" * 80)
            print("\nPlease run database migrations first:")
            print("  python scripts/db/run_migrations.py")
            print("=" * 80)
        else:
            print(f"\nError importing PDFs: {e}")
            traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def extract_covers_only(
    dpi: int = 200,
    library_dir: Optional[Path] = None,
    covers_dir: Optional[Path] = None
) -> None:
    """
    Extract covers for all PDFs in library directory.

    Args:
        dpi: DPI for cover extraction
        library_dir: Custom library directory (uses default if None)
        covers_dir: Custom covers directory (uses default if None)
    """
    # Check if cover extraction is available
    is_available, error_msg = check_cover_extraction_available()
    if not is_available:
        print(f"Error: {error_msg}")
        sys.exit(1)

    # Use LibraryService to get default paths if not provided
    if library_dir is None or covers_dir is None:
        db = SessionLocal()
        try:
            service = LibraryService(db)
            if library_dir is None:
                library_dir = service.storage_dir
            if covers_dir is None:
                covers_dir = service.covers_dir
        finally:
            db.close()

    print(f"Extracting covers from {library_dir}...")
    print()

    success_count, total_count = extract_all_covers(
        library_dir=library_dir,
        covers_dir=covers_dir,
        dpi=dpi
    )

    print("=" * 80)
    print(f"Extraction complete: {success_count}/{total_count} covers extracted")


def main() -> None:
    """Main entry point for command-line script."""
    parser = argparse.ArgumentParser(
        description='Import PDFs and extract covers for library',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import PDFs and extract covers (default behavior)
  python scripts/library_import.py import

  # Import PDFs without extracting covers
  python scripts/library_import.py import --no-extract-covers

  # Import with custom DPI for cover extraction
  python scripts/library_import.py import --dpi 300

  # Extract covers only
  python scripts/library_import.py extract-covers

  # Extract covers with custom DPI
  python scripts/library_import.py extract-covers --dpi 300

  # Import with custom directories
  python scripts/library_import.py import --library-dir /path/to/pdfs --covers-dir /path/to/covers
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Import command
    import_parser = subparsers.add_parser(
        'import',
        help='Import PDFs into database (extracts covers by default)'
    )
    import_parser.add_argument(
        '--no-extract-covers',
        action='store_false',
        dest='extract_covers',
        help='Skip cover extraction (covers are extracted by default)'
    )
    import_parser.add_argument(
        '--dpi',
        type=int,
        default=200,
        help='DPI for cover extraction (default: 200)'
    )
    import_parser.add_argument(
        '--library-dir',
        type=Path,
        help='Custom library directory (default: storage/library)'
    )
    import_parser.add_argument(
        '--covers-dir',
        type=Path,
        help='Custom covers directory (default: storage/library/covers)'
    )

    # Extract covers command
    extract_parser = subparsers.add_parser(
        'extract-covers',
        help='Extract cover images from PDFs'
    )
    extract_parser.add_argument(
        '--dpi',
        type=int,
        default=200,
        help='DPI for cover extraction (default: 200)'
    )
    extract_parser.add_argument(
        '--library-dir',
        type=Path,
        help='Custom library directory (default: storage/library)'
    )
    extract_parser.add_argument(
        '--covers-dir',
        type=Path,
        help='Custom covers directory (default: storage/library/covers)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == 'import':
            import_pdfs(
                extract_covers=getattr(args, 'extract_covers', True),
                dpi=args.dpi,
                library_dir=args.library_dir,
                covers_dir=args.covers_dir
            )
        elif args.command == 'extract-covers':
            extract_covers_only(
                dpi=args.dpi,
                library_dir=args.library_dir,
                covers_dir=args.covers_dir
            )
        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
