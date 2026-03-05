"""
Register image folders as library documents.

Scans storage/library/ for image folders and creates/updates LibraryDocument records.
Image folders should be placed directly under storage/library/ and contain page images.

Interactive: scans, lists books for verification, then prompts to re-register.

Usage:
    python scripts/library/register_image_folders.py
"""
import importlib
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.orm import Session

# Add project root to path before importing project modules
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

_config_database = importlib.import_module('config.database')
get_db = _config_database.get_db

_models_domain_auth = importlib.import_module('models.domain.auth')
User = _models_domain_auth.User

_models_domain_library = importlib.import_module('models.domain.library')
LibraryDocument = _models_domain_library.LibraryDocument

_services_library = importlib.import_module('services.library')
LibraryService = _services_library.LibraryService

_services_library_image_path_resolver = importlib.import_module(
    'services.library.image_path_resolver'
)
count_pages = _services_library_image_path_resolver.count_pages
detect_image_pattern = _services_library_image_path_resolver.detect_image_pattern

_services_library_path_utils = importlib.import_module(
    'services.library.library_path_utils'
)
normalize_library_path = _services_library_path_utils.normalize_library_path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def _find_existing_doc_by_path(db: Session, pages_dir_path: str) -> LibraryDocument | None:
    """Find LibraryDocument by exact pages_dir_path match."""
    return db.query(LibraryDocument).filter(
        LibraryDocument.pages_dir_path == pages_dir_path,
        LibraryDocument.use_images.is_(True)
    ).first()


def _find_existing_doc_by_folder_name(db: Session, folder_name: str) -> LibraryDocument | None:
    """Find LibraryDocument by folder name (handles DB import with different paths)."""
    if not folder_name:
        return None
    pattern = f'%/{folder_name}'
    return db.query(LibraryDocument).filter(
        LibraryDocument.pages_dir_path.like(pattern),
        LibraryDocument.use_images.is_(True)
    ).first()


def _get_admin_user(db: Session) -> User | None:
    """Get admin user for uploader, with fallbacks."""
    admin_user = db.query(User).filter(User.role == 'admin').first()
    if admin_user:
        return admin_user
    admin_user = db.query(User).filter(User.phone == '17801353751').first()
    if admin_user:
        logger.info(
            "Using user by phone (ID: %s) as uploader",
            admin_user.id
        )
        return admin_user
    admin_user = db.query(User).first()
    if admin_user:
        logger.warning("Using first user (ID: %s) as uploader", admin_user.id)
        return admin_user
    logger.error("No users found in database. Create a user first.")
    return None


def scan_books(library_dir: Path, db: Session) -> list[dict]:
    """
    Scan library directory for valid book folders.

    Returns list of dicts: folder_name, folder_path, page_count, in_db, needs_repair
    """
    folders = [d for d in library_dir.iterdir() if d.is_dir() and d.name != 'covers']
    results = []

    for folder_path in folders:
        folder_name = folder_path.name
        all_files = list(folder_path.iterdir())
        image_files = [
            f for f in all_files
            if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')
        ]

        if not image_files:
            continue

        page_count = count_pages(folder_path)
        if page_count == 0:
            continue

        if not detect_image_pattern(folder_path):
            continue

        pages_dir_path = normalize_library_path(folder_path, library_dir, Path.cwd())
        doc_by_path = _find_existing_doc_by_path(db, pages_dir_path)
        doc_by_name = _find_existing_doc_by_folder_name(db, folder_name)

        doc = doc_by_path or doc_by_name
        in_db = doc is not None
        needs_repair = bool(doc_by_name and not doc_by_path)

        results.append({
            'folder_name': folder_name,
            'folder_path': folder_path,
            'page_count': page_count,
            'in_db': in_db,
            'needs_repair': needs_repair,
        })

    return results


def re_register_books(
    library_dir: Path, db: Session, books: list[dict]
) -> tuple[int, int, int]:
    """Re-register the given books. Returns (registered, updated, repaired)."""
    admin_user = _get_admin_user(db)
    if not admin_user:
        return (0, 0, 0)

    os.environ["LIBRARY_STORAGE_DIR"] = str(library_dir)
    service = LibraryService(db, user_id=admin_user.id)
    registered = 0
    updated = 0
    repaired = 0

    for book in books:
        folder_path = book['folder_path']
        folder_name = book['folder_name']
        page_count = book['page_count']
        had_existing = book.get('in_db', False)
        needs_repair = book.get('needs_repair', False)

        if needs_repair:
            existing_doc = _find_existing_doc_by_folder_name(db, folder_name)
            if existing_doc:
                correct_path = normalize_library_path(
                    folder_path, library_dir, Path.cwd()
                )
                existing_doc.pages_dir_path = correct_path
                db.commit()
                db.refresh(existing_doc)

        doc = service.register_book_folder(folder_path=folder_path)
        if had_existing:
            updated += 1
            if needs_repair:
                repaired += 1
            logger.info("Updated: %s (ID: %s, Pages: %d)", folder_name, doc.id, page_count)
        else:
            registered += 1
            logger.info("Registered: %s (ID: %s, Pages: %d)", folder_name, doc.id, page_count)

    return (registered, updated, repaired)


def main() -> int:
    """Interactive: scan, list, prompt, re-register."""
    try:
        library_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "storage/library")
        library_dir = (_project_root / library_dir_env).resolve()

        if not library_dir.exists():
            logger.error("Library directory not found: %s", library_dir)
            return 1

        logger.info("Library directory: %s", library_dir)
        logger.info("")

        db_gen = get_db()
        db: Session = next(db_gen)

        try:
            logger.info("Scanning for books...")
            books = scan_books(library_dir, db)

            if not books:
                logger.info("No valid book folders found.")
                return 0

            logger.info("")
            logger.info("Found %d book(s):", len(books))
            logger.info("-" * 60)
            for i, book in enumerate(books, 1):
                status = "in DB" if book['in_db'] else "not in DB"
                if book.get('needs_repair'):
                    status = "in DB (path needs repair)"
                logger.info(
                    "  %d. %s  [%d pages]  %s",
                    i, book['folder_name'], book['page_count'], status
                )
            logger.info("-" * 60)
            logger.info("")

            reply = input("Re-register all? [y/N]: ").strip().lower()
            if reply not in ('y', 'yes'):
                logger.info("Cancelled.")
                return 0

            logger.info("")
            registered, updated, repaired = re_register_books(library_dir, db, books)

            logger.info("")
            logger.info("Done. Registered: %d, Updated: %d%s",
                       registered, updated,
                       f" (repaired: {repaired})" if repaired else "")
            return 0

        finally:
            db.close()

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
