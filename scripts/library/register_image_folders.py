"""
Register image folders as library documents.

Scans storage/library/ for image folders and creates/updates LibraryDocument records.
Image folders should be placed directly under storage/library/ and contain page images.

By default, runs in preview mode (dry-run). Use --live flag to actually register books.

Usage:
    python scripts/library/register_image_folders.py              # Preview only (default)
    python scripts/library/register_image_folders.py --live       # Actually register books
"""
import argparse
import importlib.util
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

# Add project root to path before importing project modules
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

# Dynamic imports to avoid Ruff E402 warning
_config_database = importlib.import_module('config.database')
get_db = _config_database.get_db

_models_domain_auth = importlib.import_module('models.domain.auth')
User = _models_domain_auth.User

_models_domain_library = importlib.import_module('models.domain.library')
LibraryDocument = _models_domain_library.LibraryDocument

_services_library = importlib.import_module('services.library')
LibraryService = _services_library.LibraryService

_services_library_image_path_resolver = importlib.import_module('services.library.image_path_resolver')
count_pages = _services_library_image_path_resolver.count_pages
detect_image_pattern = _services_library_image_path_resolver.detect_image_pattern

_services_library_library_path_utils = importlib.import_module('services.library.library_path_utils')
normalize_library_path = _services_library_library_path_utils.normalize_library_path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def register_image_folders(library_dir: Path, db, dry_run: bool = False) -> tuple[int, int]:
    """
    Scan library directory for image folders and register them.

    Uses LibraryService to register folders, which includes automatic cover processing.

    Args:
        library_dir: Library directory path
        db: Database session
        dry_run: If True, only show what would be registered

    Returns:
        Tuple of (registered_count, updated_count)
    """
    if not library_dir.exists():
        logger.error("Library directory not found: %s", library_dir)
        return (0, 0)

    # Get admin user for uploader, fallback to specific user or first user
    admin_user = db.query(User).filter(User.role == 'admin').first()
    if not admin_user:
        # Try to find user by phone number (17801353751)
        admin_user = db.query(User).filter(User.phone == '17801353751').first()
        if admin_user:
            logger.info(
                "No admin user found, using user by phone (ID: %s, Phone: %s, Role: %s) as uploader",
                admin_user.id,
                admin_user.phone,
                admin_user.role
            )
        else:
            # Fallback: try to get any user
            admin_user = db.query(User).first()
            if admin_user:
                logger.warning(
                    "No admin user found, using first user (ID: %s, Phone: %s, Role: %s) as uploader",
                    admin_user.id,
                    admin_user.phone,
                    admin_user.role
                )
            else:
                # List all users to help debug
                all_users = db.query(User).all()
                logger.error("No users found in database.")
                if all_users:
                    logger.info("Found %d user(s) in database:", len(all_users))
                    for u in all_users:
                        logger.info("  - ID: %s, Phone: %s, Role: %s, Name: %s", u.id, u.phone, u.role, u.name)
                else:
                    logger.error(
                        "Please create a user first (via registration or demo mode login). "
                        "Or set a user's role to 'admin' in the database."
                    )
                return (0, 0)

    # Create service instance
    service = LibraryService(db, user_id=admin_user.id)

    # Find all directories (excluding covers)
    folders = [d for d in library_dir.iterdir() if d.is_dir() and d.name != 'covers']

    registered_count = 0
    updated_count = 0

    for folder_path in folders:
        folder_name = folder_path.name

        # Check if folder contains images
        # First, check what files are actually in the folder
        all_files = list(folder_path.iterdir())
        image_files = [f for f in all_files if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')]

        if not image_files:
            logger.info("Skipping %s: No image files found (found %d files total)", folder_name, len(all_files))
            if all_files:
                sample_files = [f.name for f in all_files[:5]]
                logger.debug("  Sample files: %s", ', '.join(sample_files))
            continue

        logger.debug("Found %d image files in %s", len(image_files), folder_name)

        page_count = count_pages(folder_path)
        if page_count == 0:
            logger.warning(
                "Skipping %s: Found %d image files but could not count pages (pattern detection may have failed)",
                folder_name,
                len(image_files)
            )
            # Show sample filenames to help debug
            sample_names = [f.name for f in image_files[:5]]
            logger.debug("  Sample image filenames: %s", ', '.join(sample_names))
            continue

        pattern_info = detect_image_pattern(folder_path)
        if not pattern_info:
            logger.warning(
                "Skipping %s: Could not detect image pattern (found %d images)",
                folder_name,
                len(image_files)
            )
            sample_names = [f.name for f in image_files[:5]]
            logger.debug("  Sample image filenames: %s", ', '.join(sample_names))
            continue

        # Check if document already exists (for dry-run reporting)
        pages_dir_path = normalize_library_path(folder_path, library_dir, Path.cwd())
        existing_doc = db.query(LibraryDocument).filter(
            LibraryDocument.pages_dir_path == pages_dir_path
        ).first()

        if existing_doc:
            # Update existing document
            if dry_run:
                logger.info("Would update: %s (ID: %s, Pages: %d)", folder_name, existing_doc.id, page_count)
            else:
                # Use service to update (which will process cover if needed)
                service.register_book_folder(folder_path=folder_path)
                logger.info("Updated: %s (ID: %s, Pages: %d)", folder_name, existing_doc.id, page_count)
            updated_count += 1
        else:
            # Create new document
            if dry_run:
                logger.info("Would register: %s (Pages: %d)", folder_name, page_count)
            else:
                # Use service to register (which will process cover automatically)
                new_doc = service.register_book_folder(folder_path=folder_path)
                logger.info("Registered: %s (ID: %s, Pages: %d)", folder_name, new_doc.id, page_count)
            registered_count += 1

    return (registered_count, updated_count)


def main():
    """
    Main entry point for the script.

    Parses command line arguments and registers image folders as library documents.
    """
    parser = argparse.ArgumentParser(
        description="Register image folders as library documents (default: preview mode)"
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually register books (default is preview/dry-run mode)'
    )
    parser.add_argument(
        '--library-dir',
        type=str,
        help='Library directory path (default: storage/library)'
    )

    args = parser.parse_args()

    # Default to dry-run mode (safe default)
    dry_run = not args.live

    try:
        logger.info("=" * 80)
        if dry_run:
            logger.info("REGISTER IMAGE FOLDERS (PREVIEW MODE)")
            logger.info("Use --live flag to actually register books")
        else:
            logger.info("REGISTER IMAGE FOLDERS (LIVE MODE)")
        logger.info("=" * 80)
        logger.info("")

        # Get library directory (resolve relative to project root)
        if args.library_dir:
            library_dir = Path(args.library_dir).resolve()
        else:
            library_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "storage/library")
            library_dir = (_project_root / library_dir_env).resolve()

        logger.info("Library directory: %s", library_dir)
        logger.info("")

        if not library_dir.exists():
            logger.error("Library directory not found: %s", library_dir)
            return 1

        # Get database session
        db_gen = get_db()
        db: Session = next(db_gen)

        try:
            registered, updated = register_image_folders(library_dir, db, dry_run=dry_run)

            logger.info("")
            logger.info("=" * 80)
            if dry_run:
                logger.info("PREVIEW COMPLETE")
                logger.info("Run with --live flag to actually register these books")
            else:
                logger.info("REGISTRATION COMPLETE")
            logger.info("=" * 80)
            logger.info("Registered: %d", registered)
            logger.info("Updated: %d", updated)
            logger.info("Total: %d", registered + updated)

            return 0

        finally:
            db.close()

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
