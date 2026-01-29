"""
Library PDF Import Script

Consolidated script for importing PDFs into the library with automatic
xref detection and optimization.

Features:
- Scans storage/library/ for PDF files
- Checks xref table location for each PDF
- If xref is at beginning: Import directly (already optimized)
- If xref is at end: Linearize first, then import
- Extracts cover images automatically
- Creates database records

Usage:
    python scripts/library_import.py                    # Import all PDFs
    python scripts/library_import.py --analyze-only    # Just analyze, don't import
    python scripts/library_import.py --no-optimize     # Import without optimization
    python scripts/library_import.py --backup          # Create backups before optimizing

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import argparse
import logging
import os
import sys
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

# Add project root to path (must be before project imports)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Import project modules dynamically to satisfy linter
_config_db = import_module('config.database')
_models_library = import_module('models.domain.library')
_pdf_optimizer = import_module('services.library.pdf_optimizer')
_pdf_importer = import_module('services.library.pdf_importer')
_pdf_utils = import_module('services.library.pdf_utils')
_pdf_cover_extractor = import_module('services.library.pdf_cover_extractor')
_library_service = import_module('services.library')

# Assign to module-level names for easier access
SessionLocal = _config_db.SessionLocal
LibraryDocument = _models_library.LibraryDocument
analyze_pdf_structure = _pdf_optimizer.analyze_pdf_structure
check_qpdf_available = _pdf_optimizer.check_qpdf_available
optimize_pdf = _pdf_optimizer.optimize_pdf
should_optimize_pdf = _pdf_optimizer.should_optimize_pdf
auto_import_new_pdfs = _pdf_importer.auto_import_new_pdfs
optimize_existing_library_pdfs = _pdf_importer.optimize_existing_library_pdfs
validate_pdf_file = _pdf_utils.validate_pdf_file
optimize_oversized_covers = _pdf_cover_extractor.optimize_oversized_covers
regenerate_all_covers = _pdf_cover_extractor.regenerate_all_covers
extract_missing_covers_from_database = _pdf_cover_extractor.extract_missing_covers_from_database
verify_all_covers_in_database = _pdf_cover_extractor.verify_all_covers_in_database
check_cover_extraction_available = _pdf_cover_extractor.check_cover_extraction_available
LibraryService = _library_service.LibraryService

# Define project_root using Path after imports
project_root = Path(_project_root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_library_dir() -> Path:
    """Get the library storage directory."""
    storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
    
    # If absolute path, use it directly
    if os.path.isabs(storage_dir_env):
        return Path(storage_dir_env).resolve()
    
    # For relative paths, always resolve relative to project root
    # This ensures the script works regardless of current working directory
    if storage_dir_env.startswith('./'):
        # Remove leading './' and resolve relative to project root
        relative_path = storage_dir_env[2:]  # Remove './'
        storage_dir = (project_root / relative_path).resolve()
    else:
        # Resolve relative to project root
        storage_dir = (project_root / storage_dir_env).resolve()
    
    return storage_dir


def analyze_pdfs(library_dir: Path) -> list:
    """
    Analyze all PDFs in the library directory.

    Returns:
        List of analysis results
    """
    pdf_files = list(library_dir.glob("*.pdf"))

    if not pdf_files:
        logger.info("No PDF files found in %s", library_dir)
        return []

    logger.info("=" * 70)
    logger.info("PDF STRUCTURE ANALYSIS")
    logger.info("=" * 70)
    logger.info("Found %s PDF file(s) in %s", len(pdf_files), library_dir)
    logger.info("")

    # Check qpdf availability
    qpdf_available = check_qpdf_available()
    if qpdf_available:
        logger.info("qpdf: Available (recommended for optimization)")
    else:
        logger.info("qpdf: Not available (will use PyPDF2 if needed)")
    logger.info("")

    results = []

    for pdf_path in sorted(pdf_files):
        # Validate PDF
        is_valid, error_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            logger.warning("INVALID: %s - %s", pdf_path.name, error_msg)
            continue

        # Analyze structure
        info = analyze_pdf_structure(pdf_path)
        file_size_mb = round(pdf_path.stat().st_size / 1024 / 1024, 2)

        result = {
            'path': pdf_path,
            'name': pdf_path.name,
            'size_mb': file_size_mb,
            'info': info
        }
        results.append(result)

        # Display analysis
        if info.is_linearized:
            status = "OPTIMIZED"
            xref_status = "xref at beginning"
            action = "Ready for import"
        elif info.xref_location == 'beginning':
            status = "OPTIMIZED"
            xref_status = "xref at beginning"
            action = "Ready for import"
        else:
            status = "NEEDS OPTIMIZATION"
            xref_status = f"xref at {info.xref_location}"
            action = "Will linearize before import"

        logger.info("-" * 70)
        logger.info("File: %s", pdf_path.name)
        logger.info("  Size: %.2f MB", file_size_mb)
        logger.info("  Status: %s", status)
        logger.info("  XRef: %s (%s KB)", xref_status, info.xref_size_kb)
        logger.info("  Linearized: %s", "Yes" if info.is_linearized else "No")
        logger.info("  Action: %s", action)

        if info.analysis_error:
            logger.warning("  Warning: %s", info.analysis_error)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    optimized = sum(
        1 for r in results
        if r['info'].is_linearized or r['info'].xref_location == 'beginning'
    )
    needs_opt = len(results) - optimized

    logger.info("Total PDFs: %s", len(results))
    logger.info("Already optimized: %s", optimized)
    logger.info("Need optimization: %s", needs_opt)

    if needs_opt > 0:
        logger.info("")
        logger.info("PDFs needing optimization will be linearized during import.")
        logger.info("This moves the xref table to the beginning for faster loading.")

    return results


def import_pdfs(
    library_dir: Path,
    auto_optimize: bool = True,
    backup: bool = False,
    extract_covers: bool = True,
    dpi: int = 96
) -> tuple:
    """
    Import PDFs from library directory into database.

    Also optimizes existing PDFs that are already in the database but need
    optimization (xref at end).

    Args:
        library_dir: Directory containing PDFs
        auto_optimize: If True, linearize PDFs with xref at end
        backup: If True, create backup before optimizing
        extract_covers: If True, extract cover images
        dpi: DPI for cover extraction

    Returns:
        Tuple of (imported_count, skipped_count)
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("IMPORTING PDFs")
    logger.info("=" * 70)
    logger.info("")

    # Log cover extraction settings
    if extract_covers:
        logger.info("Cover extraction: ENABLED (DPI: %s)", dpi)
        # Check if cover extraction is available
        is_available, error_msg = check_cover_extraction_available()
        if is_available:
            logger.info("  Cover extraction tools: Available")
        else:
            logger.warning("  Cover extraction tools: NOT AVAILABLE - %s", error_msg)
            logger.warning("  Covers will not be extracted. Install dependencies to enable.")
    else:
        logger.info("Cover extraction: DISABLED (use --no-covers to disable)")
    logger.info("")

    db = SessionLocal()
    try:
        # Use correctly resolved library_dir to construct covers_dir
        # This ensures paths are correct regardless of current working directory
        covers_dir = library_dir / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Covers directory: %s", covers_dir)
        logger.info("")

        # First, optimize any existing PDFs in the database that need it
        if auto_optimize:
            logger.info("Step 1: Optimizing existing PDFs in database...")
            optimized, _, opt_errors = optimize_existing_library_pdfs(
                db,
                library_dir=library_dir,
                backup=backup
            )
            if optimized > 0:
                logger.info("  Optimized %s existing PDF(s)", optimized)
            if opt_errors > 0:
                logger.warning("  Failed to optimize %s PDF(s)", opt_errors)
            logger.info("")

        # Extract missing covers for existing PDFs (before importing new ones)
        if extract_covers:
            is_available, _ = check_cover_extraction_available()
            if is_available:
                logger.info("Step 2: Extracting missing covers for existing PDFs...")
                extracted, skipped_covers, cover_errors = extract_missing_covers_from_database(
                    db,
                    library_dir=library_dir,
                    covers_dir=covers_dir,
                    dpi=dpi
                )
                if extracted > 0:
                    logger.info("  Extracted %s missing cover(s)", extracted)
                if skipped_covers > 0:
                    logger.info("  Skipped %s (covers already exist)", skipped_covers)
                if cover_errors > 0:
                    logger.warning("  Failed to extract %s cover(s)", cover_errors)
                logger.info("")

        # Then import new PDFs (with cover extraction)
        logger.info("Step 3: Importing new PDFs...")
        if extract_covers:
            logger.info("  Cover images will be extracted for each new PDF")
        imported, skipped = auto_import_new_pdfs(
            db,
            library_dir=library_dir,
            extract_covers=extract_covers,
            dpi=dpi,
            auto_optimize=auto_optimize,
            optimize_backup=backup
        )

        # Verify all covers after extraction/import
        if extract_covers:
            logger.info("")
            logger.info("Step 4: Verifying cover images...")
            valid_count, missing_count, invalid_count, invalid_details = verify_all_covers_in_database(
                db,
                library_dir=library_dir,
                covers_dir=covers_dir
            )
            logger.info("")
            logger.info("Cover verification summary:")
            logger.info("  Valid covers: %s", valid_count)
            logger.info("  Missing covers: %s", missing_count)
            logger.info("  Invalid covers: %s", invalid_count)
            if invalid_count > 0:
                logger.warning("")
                logger.warning("⚠️  Some covers are invalid and may need to be regenerated")
                logger.warning("   Run with --regenerate-covers to fix invalid covers")

        return imported, skipped
    finally:
        db.close()


def optimize_existing_pdfs(
    library_dir: Path,
    backup: bool = True
) -> tuple:
    """
    Optimize existing PDFs in library and update database records.

    This function:
    1. Gets all documents from database
    2. Checks if each PDF needs optimization (xref at end)
    3. Linearizes PDFs that need it
    4. Updates file_size in database after optimization

    Args:
        library_dir: Directory containing PDFs
        backup: If True, create backup before optimizing

    Returns:
        Tuple of (optimized_count, skipped_count, error_count)
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("OPTIMIZING EXISTING LIBRARY PDFs")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This will optimize PDFs already in the database and update file sizes.")
    logger.info("")

    db = SessionLocal()
    try:
        optimized, skipped, errors = optimize_existing_library_pdfs(
            db,
            library_dir=library_dir,
            backup=backup
        )
        return (optimized, skipped, errors)
    finally:
        db.close()


def optimize_pdf_files_only(
    library_dir: Path,
    backup: bool = True
) -> tuple:
    """
    Optimize PDF files without touching the database.

    Use this when you don't have PostgreSQL running or just want to
    linearize files without updating database records.

    Args:
        library_dir: Directory containing PDFs
        backup: If True, create backup before optimizing

    Returns:
        Tuple of (optimized_count, skipped_count, error_count)
    """
    pdf_files = list(library_dir.glob("*.pdf"))

    if not pdf_files:
        logger.info("No PDF files found in %s", library_dir)
        return (0, 0, 0)

    logger.info("")
    logger.info("=" * 70)
    logger.info("OPTIMIZING PDF FILES (no database)")
    logger.info("=" * 70)
    logger.info("")

    qpdf_available = check_qpdf_available()
    if not qpdf_available:
        try:
            if find_spec("PyPDF2") is None:
                raise ImportError("PyPDF2 not found")
            logger.info("Using PyPDF2 for optimization (qpdf not available)")
        except ImportError:
            logger.error("Neither qpdf nor PyPDF2 available. Cannot optimize.")
            return (0, len(pdf_files), 0)
    else:
        logger.info("Using qpdf for optimization")

    optimized = 0
    skipped = 0
    errors = 0

    for pdf_path in sorted(pdf_files):
        pdf_name = pdf_path.name

        # Validate PDF
        is_valid, error_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            logger.warning("Skipping invalid PDF: %s - %s", pdf_name, error_msg)
            skipped += 1
            continue

        # Check if optimization needed
        should_opt, reason, info = should_optimize_pdf(pdf_path)

        if not should_opt:
            logger.debug(
                "Skipping %s: already optimized (xref at %s)",
                pdf_name,
                info.xref_location
            )
            skipped += 1
            continue

        # Optimize
        logger.info("Optimizing: %s (%s)", pdf_name, reason)
        success, error, stats = optimize_pdf(
            pdf_path,
            backup=backup,
            prefer_qpdf=qpdf_available
        )

        if success:
            if stats['was_optimized']:
                optimized += 1
                logger.info(
                    "  Success: %s -> %s bytes (%+s, method: %s)",
                    f"{stats['original_size']:,}",
                    f"{stats['new_size']:,}",
                    f"{stats['size_change']:,}",
                    stats['method']
                )
            else:
                skipped += 1
                logger.debug("  No optimization needed")
        else:
            errors += 1
            logger.error("  Failed: %s", error)

    # Summary
    logger.info("")
    logger.info("Optimization complete (files only, no database update):")
    logger.info("  Optimized: %s", optimized)
    logger.info("  Skipped: %s", skipped)
    logger.info("  Errors: %s", errors)

    return (optimized, skipped, errors)


def verify_all_pdfs_optimized(library_dir: Path, check_db_size: bool = False) -> tuple:
    """
    Verify that all PDFs in the library have xref at the beginning.

    Optionally checks that database file_size matches actual file size.

    Args:
        library_dir: Directory containing PDFs
        check_db_size: If True, also verify database file_size matches (requires DB)

    Returns:
        Tuple of (total_count, optimized_count, failed_list, size_mismatch_list)
        failed_list contains tuples of (filename, xref_location)
        size_mismatch_list contains tuples of (filename, db_size, actual_size)
    """
    pdf_files = list(library_dir.glob("*.pdf"))

    if not pdf_files:
        return (0, 0, [], [])

    logger.info("")
    logger.info("=" * 70)
    logger.info("VERIFICATION: Checking all PDFs have xref at beginning")
    logger.info("=" * 70)
    logger.info("")

    optimized_count = 0
    failed_list = []
    size_mismatch_list = []

    # Get database records if checking size
    db_size_map = {}
    if check_db_size:
        try:
            db = SessionLocal()
            try:
                documents = db.query(LibraryDocument).filter(
                    LibraryDocument.is_active
                ).all()
                for doc in documents:
                    # Extract filename from path
                    doc_filename = Path(doc.file_path).name
                    db_size_map[doc_filename] = doc.file_size
            finally:
                db.close()
        except Exception as e:
            logger.warning("Could not check database sizes: %s", e)
            check_db_size = False

    for pdf_path in sorted(pdf_files):
        pdf_name = pdf_path.name

        # Validate PDF
        is_valid, _ = validate_pdf_file(pdf_path)
        if not is_valid:
            continue

        # Analyze structure
        info = analyze_pdf_structure(pdf_path)

        if info.analysis_error:
            failed_list.append((pdf_name, f"error: {info.analysis_error}"))
            continue

        # Check if optimized (xref at beginning OR linearized)
        is_optimized = info.is_linearized or info.xref_location == 'beginning'

        if is_optimized:
            optimized_count += 1
            logger.debug("  ✓ %s - xref at %s", pdf_name, info.xref_location)
        else:
            failed_list.append((pdf_name, info.xref_location))
            logger.warning("  ✗ %s - xref at %s (NOT OPTIMIZED)", pdf_name, info.xref_location)

        # Check file size matches database
        if check_db_size and pdf_name in db_size_map:
            try:
                actual_size = pdf_path.stat().st_size
                db_size = db_size_map[pdf_name]
                if actual_size != db_size:
                    size_mismatch_list.append((pdf_name, db_size, actual_size))
                    logger.warning(
                        "  ⚠ %s - size mismatch: DB=%s, actual=%s",
                        pdf_name,
                        f"{db_size:,}",
                        f"{actual_size:,}"
                    )
            except OSError:
                pass

    # Summary
    total = len(pdf_files)
    logger.info("")
    logger.info("Verification Results:")
    logger.info("  Total PDFs: %s", total)
    logger.info("  Optimized (xref at front): %s", optimized_count)
    logger.info("  Not optimized: %s", len(failed_list))
    if check_db_size:
        logger.info("  Size mismatches: %s", len(size_mismatch_list))

    if failed_list:
        logger.info("")
        logger.warning("The following PDFs still need optimization:")
        for name, location in failed_list:
            logger.warning("  - %s (xref at %s)", name, location)
        logger.info("")
        logger.info("Run with --optimize-only to fix these PDFs.")

    if size_mismatch_list:
        logger.info("")
        logger.warning("The following PDFs have file size mismatches in database:")
        for name, db_size, actual_size in size_mismatch_list:
            logger.warning("  - %s (DB: %s, actual: %s)", name, f"{db_size:,}", f"{actual_size:,}")
        logger.info("")
        logger.info("Run with --optimize-only to update database sizes.")

    if not failed_list and not size_mismatch_list:
        logger.info("")
        logger.info("✓ All PDFs are optimized! Ready for efficient lazy loading.")

    return (total, optimized_count, failed_list, size_mismatch_list)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Library PDF Import - Analyze, optimize, and import PDFs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/library_import.py                    # Analyze and import all PDFs
  python scripts/library_import.py --analyze-only    # Just analyze, don't import
  python scripts/library_import.py --no-optimize     # Import without optimization
  python scripts/library_import.py --optimize-only   # Just optimize existing PDFs
  python scripts/library_import.py --backup          # Create backups before optimizing
        """
    )

    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only analyze PDFs, do not import or optimize'
    )

    parser.add_argument(
        '--optimize-only',
        action='store_true',
        help='Only optimize existing PDFs, do not import'
    )

    parser.add_argument(
        '--files-only',
        action='store_true',
        help='Only process files, do not connect to database (use with --optimize-only)'
    )

    parser.add_argument(
        '--no-optimize',
        action='store_true',
        help='Import PDFs without optimizing (not recommended)'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup before optimizing PDFs'
    )

    parser.add_argument(
        '--no-covers',
        action='store_true',
        help='Do not extract cover images'
    )

    parser.add_argument(
        '--regenerate-covers',
        action='store_true',
        help='Regenerate ALL cover images with optimized settings (JPEG, smaller size)'
    )

    parser.add_argument(
        '--optimize-covers',
        action='store_true',
        help='Only regenerate covers that are too large (>100 KB by default)'
    )

    parser.add_argument(
        '--max-cover-size',
        type=int,
        default=100,
        help='Max cover size in KB for --optimize-covers (default: 100)'
    )

    parser.add_argument(
        '--dpi',
        type=int,
        default=96,
        help='DPI for cover extraction (default: 96 for web thumbnails)'
    )

    parser.add_argument(
        '--cover-width',
        type=int,
        default=400,
        help='Max cover width in pixels (default: 400)'
    )

    parser.add_argument(
        '--cover-quality',
        type=int,
        default=80,
        help='JPEG quality 1-100 (default: 80)'
    )

    parser.add_argument(
        '--library-dir',
        type=str,
        default=None,
        help='Library directory path (default: from LIBRARY_STORAGE_DIR env)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompts (auto-confirm all actions)'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get library directory
    if args.library_dir:
        library_dir = Path(args.library_dir).resolve()
    else:
        library_dir = get_library_dir()

    if not library_dir.exists():
        logger.error("Library directory not found: %s", library_dir)
        logger.info("Please create the directory or set LIBRARY_STORAGE_DIR env variable")
        sys.exit(1)

    logger.info("Library directory: %s", library_dir)

    # Always analyze first
    results = analyze_pdfs(library_dir)

    if not results:
        logger.info("No valid PDFs found to process")
        sys.exit(0)

    if args.analyze_only:
        logger.info("")
        logger.info("Analysis complete. Use without --analyze-only to import PDFs.")
        sys.exit(0)

    # Handle optimize-covers mode (smart - only regenerate oversized covers)
    if args.optimize_covers:
        logger.info("")
        logger.info("=" * 70)
        logger.info("OPTIMIZE OVERSIZED COVERS")
        logger.info("=" * 70)
        logger.info("")

        # Get covers directory
        db = SessionLocal()
        try:
            service = LibraryService(db)
            covers_dir = service.covers_dir
        finally:
            db.close()

        # Check existing covers
        existing_covers = list(covers_dir.glob("*_cover.*")) if covers_dir.exists() else []
        oversized = [c for c in existing_covers if c.stat().st_size / 1024 > args.max_cover_size]

        logger.info("Existing covers: %s", len(existing_covers))
        logger.info("Oversized (> %s KB): %s", args.max_cover_size, len(oversized))
        logger.info("")

        if not oversized:
            logger.info("All covers are already optimized! Nothing to do.")
            sys.exit(0)

        logger.info("Oversized covers to regenerate:")
        for cover in sorted(oversized):
            size_kb = cover.stat().st_size / 1024
            logger.info("  - %s (%.1f KB)", cover.name, size_kb)
        logger.info("")
        logger.info("New settings: JPEG, DPI=%s, width=%spx, quality=%s%%",
                    args.dpi, args.cover_width, args.cover_quality)
        logger.info("")

        if not args.yes:
            try:
                response = input(f"Regenerate {len(oversized)} oversized cover(s)? [y/N]: ").strip().lower()
                if response not in ('y', 'yes'):
                    logger.info("Cancelled by user.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                logger.info("")
                logger.info("Cancelled.")
                sys.exit(0)

        regenerated, skipped, total = optimize_oversized_covers(
            library_dir=library_dir,
            covers_dir=covers_dir,
            max_size_kb=args.max_cover_size,
            dpi=args.dpi,
            max_width=args.cover_width,
            image_format="JPEG",
            quality=args.cover_quality
        )

        sys.exit(0)

    # Handle regenerate-covers mode (force all)
    if args.regenerate_covers:
        from services.library.pdf_cover_extractor import regenerate_covers_from_database

        logger.info("")
        logger.info("=" * 70)
        logger.info("REGENERATE ALL COVERS")
        logger.info("=" * 70)
        logger.info("")
        logger.info("This will regenerate ALL cover images with optimized settings:")
        logger.info("  - Format: JPEG (much smaller than PNG)")
        logger.info("  - DPI: %s (screen resolution)", args.dpi)
        logger.info("  - Max Width: %spx", args.cover_width)
        logger.info("  - Quality: %s%%", args.cover_quality)
        logger.info("  - Naming: {document_id}_cover.jpg (matches database)")
        logger.info("")

        # Get document count from database
        db = SessionLocal()
        try:
            doc_count = db.query(LibraryDocument).filter(LibraryDocument.is_active).count()
            logger.info("Documents in database: %s", doc_count)
        finally:
            db.close()

        logger.info("")

        if not args.yes:
            try:
                response = input("Proceed with regenerating ALL covers? [y/N]: ").strip().lower()
                if response not in ('y', 'yes'):
                    logger.info("Cancelled by user.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                logger.info("")
                logger.info("Cancelled.")
                sys.exit(0)

        # Regenerate covers using database
        db = SessionLocal()
        try:
            service = LibraryService(db)
            covers_dir = service.covers_dir

            regenerated, _, errors = regenerate_covers_from_database(
                db=db,
                library_dir=library_dir,
                covers_dir=covers_dir,
                dpi=args.dpi,
                max_width=args.cover_width,
                image_format="JPEG",
                quality=args.cover_quality
            )
        finally:
            db.close()

        logger.info("")
        logger.info("=" * 70)
        logger.info("REGENERATION COMPLETE")
        logger.info("=" * 70)
        logger.info("Covers regenerated: %s", regenerated)
        if errors > 0:
            logger.warning("Errors: %s", errors)

        # Show size comparison
        new_covers = list(covers_dir.glob("*_cover.jpg"))
        if new_covers:
            total_size = sum(c.stat().st_size for c in new_covers)
            avg_size = total_size / len(new_covers) / 1024
            logger.info("Average cover size: %.1f KB", avg_size)

        sys.exit(0)

    # Count PDFs needing optimization
    needs_optimization = [
        r for r in results
        if not r['info'].is_linearized and r['info'].xref_location != 'beginning'
    ]
    already_optimized = len(results) - len(needs_optimization)

    if args.optimize_only:
        # Show what will be done and ask for confirmation
        logger.info("")
        logger.info("=" * 70)
        logger.info("OPTIMIZATION PLAN")
        logger.info("=" * 70)
        logger.info("")

        if args.files_only:
            logger.info("Mode: FILES ONLY (no database connection)")
        else:
            logger.info("Mode: Full (will update database file_size)")
        logger.info("")

        logger.info("PDFs detected: %s", len(results))
        logger.info("  - Already optimized: %s", already_optimized)
        logger.info("  - Need optimization: %s", len(needs_optimization))
        logger.info("")

        if len(needs_optimization) == 0:
            logger.info("All PDFs are already optimized. Nothing to do.")
            sys.exit(0)

        logger.info("PDFs to linearize:")
        for r in needs_optimization:
            logger.info("  - %s (%.2f MB, xref at %s)",
                        r['name'], r['size_mb'], r['info'].xref_location)
        logger.info("")

        if args.backup:
            logger.info("Backups will be created (.pdf.backup)")
        else:
            logger.info("No backups will be created (use --backup to enable)")
        logger.info("")

        if not args.yes:
            try:
                response = input(
                    f"Proceed with linearizing {len(needs_optimization)} PDF(s)? [y/N]: "
                ).strip().lower()
                if response not in ('y', 'yes'):
                    logger.info("Cancelled by user.")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                logger.info("")
                logger.info("Cancelled.")
                sys.exit(0)

        # Use files-only mode if requested (no database needed)
        if args.files_only:
            optimized, _, errors = optimize_pdf_files_only(
                library_dir,
                backup=args.backup
            )
        else:
            optimized, _, errors = optimize_existing_pdfs(
                library_dir,
                backup=args.backup
            )

        # Verification step
        if optimized > 0 or errors == 0:
            # Use check_db_size=True only if not in files-only mode
            check_db = not args.files_only
            total, verified_count, failed, size_mismatches = verify_all_pdfs_optimized(
                library_dir, check_db_size=check_db
            )
            if failed:
                logger.error("")
                logger.error("VERIFICATION FAILED: %s PDF(s) still not optimized!", len(failed))
                sys.exit(1)

        sys.exit(0 if errors == 0 else 1)

    # Check if files_only is used without optimize_only (doesn't make sense for import)
    if args.files_only:
        logger.error("--files-only can only be used with --optimize-only")
        logger.error("Import mode requires database connection to create records.")
        logger.info("")
        logger.info("Usage examples:")
        logger.info("  Optimize files only (no DB): python scripts/library_import.py --optimize-only --files-only")
        logger.info("  Full import (needs DB):      python scripts/library_import.py")
        sys.exit(1)

    # Import mode - check which PDFs are already in database
    db = SessionLocal()
    try:
        existing_docs = db.query(LibraryDocument).filter(
            LibraryDocument.is_active
        ).all()
        existing_filenames = {Path(doc.file_path).name for doc in existing_docs}
    finally:
        db.close()

    # Categorize PDFs
    new_pdfs = [r for r in results if r['name'] not in existing_filenames]
    existing_pdfs = [r for r in results if r['name'] in existing_filenames]
    existing_need_opt = [r for r in existing_pdfs if r['info'].needs_optimization]
    new_need_opt = [r for r in new_pdfs if r['info'].needs_optimization]

    # Show import plan
    logger.info("")
    logger.info("=" * 70)
    logger.info("IMPORT PLAN")
    logger.info("=" * 70)
    logger.info("")
    logger.info("PDFs detected: %s", len(results))
    logger.info("  - New (will be imported): %s", len(new_pdfs))
    logger.info("  - Already in database: %s", len(existing_pdfs))
    logger.info("")
    logger.info("Optimization status:")
    logger.info("  - Already optimized: %s", already_optimized)
    logger.info("  - Need optimization: %s", len(needs_optimization))
    if existing_need_opt:
        logger.info("    - Existing PDFs needing optimization: %s", len(existing_need_opt))
    if new_need_opt:
        logger.info("    - New PDFs needing optimization: %s", len(new_need_opt))
    logger.info("")

    if not args.no_optimize and len(needs_optimization) > 0:
        logger.info("The following PDFs will be linearized:")
        for r in needs_optimization:
            status = "(existing)" if r['name'] in existing_filenames else "(new)"
            logger.info("  - %s (%.2f MB) %s", r['name'], r['size_mb'], status)
        logger.info("")

    logger.info("Actions to perform:")
    step_num = 1
    logger.info("  %d. Validate PDFs", step_num)
    step_num += 1
    
    if not args.no_optimize and len(existing_need_opt) > 0:
        logger.info("  %d. Optimize %s existing PDF(s) in database", step_num, len(existing_need_opt))
        step_num += 1
    
    if not args.no_optimize and len(new_need_opt) > 0:
        logger.info("  %d. Linearize %s new PDF(s) during import", step_num, len(new_need_opt))
        step_num += 1
    
    # Always show cover extraction step (it's enabled by default)
    if not args.no_covers:
        logger.info("  %d. Extract cover images for all PDFs (DPI: %s)", step_num, args.dpi)
        step_num += 1
    else:
        logger.info("  %d. Extract cover images: SKIPPED (--no-covers flag used)", step_num)
        step_num += 1
    
    if len(new_pdfs) > 0:
        logger.info("  %d. Create %s database record(s)", step_num, len(new_pdfs))
    logger.info("")

    if not args.yes:
        try:
            response = input("Proceed with import? [y/N]: ").strip().lower()
            if response not in ('y', 'yes'):
                logger.info("Cancelled by user.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            logger.info("")
            logger.info("Cancelled.")
            sys.exit(0)

    # Import PDFs
    imported, skipped = import_pdfs(
        library_dir,
        auto_optimize=not args.no_optimize,
        backup=args.backup,
        extract_covers=not args.no_covers,
        dpi=args.dpi
    )

    # Verification step (check DB sizes since we have database access)
    total, verified_count, failed, size_mismatches = verify_all_pdfs_optimized(
        library_dir, check_db_size=True
    )

    # Cover verification
    cover_valid_count = 0
    cover_missing_count = 0
    cover_invalid_count = 0
    if not args.no_covers:
        db = SessionLocal()
        try:
            # Use correctly resolved library_dir to construct covers_dir
            covers_dir = library_dir / "covers"
            cover_valid_count, cover_missing_count, cover_invalid_count, _ = verify_all_covers_in_database(
                db,
                library_dir=library_dir,
                covers_dir=covers_dir
            )
        except Exception as e:
            logger.warning("Failed to verify covers: %s", e)
        finally:
            db.close()

    logger.info("")
    logger.info("=" * 70)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 70)
    logger.info("PDFs imported: %s", imported)
    logger.info("PDFs skipped: %s", skipped)
    logger.info("")
    logger.info("PDF Verification:")
    logger.info("  Total PDFs in library: %s", total)
    logger.info("  Optimized (xref at front): %s", verified_count)
    logger.info("  Not optimized: %s", len(failed))
    logger.info("  Size mismatches: %s", len(size_mismatches))
    if not args.no_covers:
        logger.info("")
        logger.info("Cover Verification:")
        logger.info("  Valid covers: %s", cover_valid_count)
        logger.info("  Missing covers: %s", cover_missing_count)
        logger.info("  Invalid covers: %s", cover_invalid_count)

    if failed:
        logger.error("")
        logger.error("WARNING: %s PDF(s) still have xref at end!", len(failed))
        logger.error("These PDFs will have slower initial load times.")
        logger.error("Run with --optimize-only to fix them.")
    elif size_mismatches:
        logger.warning("")
        logger.warning("WARNING: %s PDF(s) have file size mismatch in database.", len(size_mismatches))
        logger.warning("Run with --optimize-only to update database.")
    else:
        logger.info("")
        logger.info("✓ All PDFs verified! Ready for efficient lazy loading.")
        logger.info("  Optimized PDFs have xref at beginning -> fast initial load")


if __name__ == "__main__":
    main()
