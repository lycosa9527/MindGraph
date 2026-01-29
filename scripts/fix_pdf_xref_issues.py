"""
Fix PDF xref issues that cause PDF.js to download entire file.

This script:
1. Diagnoses all PDFs in the library
2. Identifies PDFs with incremental updates or non-linearized structure
3. Re-linearizes problematic PDFs
4. Verifies the fix worked

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.library.pdf_optimizer import (
    analyze_pdf_structure,
    optimize_pdf,
    check_qpdf_available
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def diagnose_and_fix_pdf(pdf_path: Path, force_relinearize: bool = False) -> Tuple[bool, str]:
    """
    Diagnose a PDF and fix if needed.
    
    Args:
        pdf_path: Path to PDF file
        force_relinearize: If True, re-linearize even if appears optimized
        
    Returns:
        (success: bool, message: str)
    """
    # Analyze PDF structure
    info = analyze_pdf_structure(pdf_path)
    
    if info.analysis_error:
        return False, f"Analysis failed: {info.analysis_error}"
    
    # Check for issues
    issues = []
    if info.has_incremental_updates:
        issues.append("has incremental updates (/Prev)")
    if not info.is_linearized:
        issues.append("not linearized")
    if info.xref_location == 'end':
        issues.append(f"xref at {info.xref_location}")
    elif info.xref_location != 'beginning' and info.xref_location != 'unknown':
        issues.append(f"xref at {info.xref_location}")
    
    if not issues and not force_relinearize:
        return True, "PDF is already optimized"
    
    # Fix the PDF
    issue_str = ", ".join(issues)
    logger.info("  Fixing: %s", issue_str)
    
    success, error, stats = optimize_pdf(
        pdf_path,
        backup=True,
        prefer_qpdf=True
    )
    
    if not success:
        return False, f"Optimization failed: {error}"
    
    if not stats.get('was_optimized'):
        return True, "No optimization needed (already optimized)"
    
    # Verify the fix
    verify_info = analyze_pdf_structure(pdf_path)
    if verify_info.analysis_error:
        return False, f"Verification failed: {verify_info.analysis_error}"
    
    remaining_issues = []
    if verify_info.has_incremental_updates:
        remaining_issues.append("still has incremental updates")
    if not verify_info.is_linearized:
        remaining_issues.append("still not linearized")
    if verify_info.xref_location != 'beginning' and verify_info.xref_location != 'unknown':
        remaining_issues.append(f"xref still at {verify_info.xref_location}")
    
    if remaining_issues:
        return False, f"Fix incomplete: {', '.join(remaining_issues)}"
    
    return True, f"Fixed successfully (size: {stats['original_size']:,} -> {stats['new_size']:,} bytes)"


def fix_all_pdfs(library_dir: Path, force_relinearize: bool = False) -> None:
    """
    Fix all PDFs in the library that have xref issues.
    
    Args:
        library_dir: Directory containing PDFs
        force_relinearize: If True, re-linearize all PDFs
    """
    if not library_dir.exists():
        logger.error("Library directory not found: %s", library_dir)
        return
    
    # Find all PDF files
    pdf_files = list(library_dir.glob("*.pdf"))
    if not pdf_files:
        logger.info("No PDF files found in %s", library_dir)
        return
    
    logger.info("=" * 80)
    logger.info("FIXING PDF XREF ISSUES")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Found %d PDF file(s) in %s", len(pdf_files), library_dir)
    logger.info("")
    
    # Check for qpdf
    if not check_qpdf_available():
        logger.error("qpdf is not available!")
        logger.error("Please install qpdf: https://qpdf.sourceforge.io/")
        logger.error("")
        logger.error("On Windows: Download from https://qpdf.sourceforge.io/")
        logger.error("On macOS: brew install qpdf")
        logger.error("On Linux: apt-get install qpdf or yum install qpdf")
        return
    
    logger.info("✅ qpdf is available")
    logger.info("")
    
    # Process each PDF
    fixed_count = 0
    already_ok_count = 0
    failed_count = 0
    failed_files: List[Tuple[str, str]] = []
    
    for pdf_path in sorted(pdf_files):
        logger.info("Processing: %s", pdf_path.name)
        
        success, message = diagnose_and_fix_pdf(pdf_path, force_relinearize)
        
        if success:
            if "already optimized" in message.lower():
                already_ok_count += 1
                logger.info("  ✅ %s", message)
            else:
                fixed_count += 1
                logger.info("  ✅ %s", message)
        else:
            failed_count += 1
            failed_files.append((pdf_path.name, message))
            logger.error("  ❌ %s", message)
        
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info("  Fixed: %d", fixed_count)
    logger.info("  Already OK: %d", already_ok_count)
    logger.info("  Failed: %d", failed_count)
    logger.info("")
    
    if failed_files:
        logger.info("Failed files:")
        for filename, error in failed_files:
            logger.info("  • %s: %s", filename, error)
        logger.info("")
    
    if fixed_count > 0:
        logger.info("✅ Successfully fixed %d PDF(s)", fixed_count)
        logger.info("   PDF.js should now be able to load them efficiently!")
    elif already_ok_count == len(pdf_files):
        logger.info("✅ All PDFs are already optimized!")
    else:
        logger.warning("⚠️  Some PDFs could not be fixed. Check errors above.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Fix PDF xref issues that cause PDF.js to download entire file"
    )
    parser.add_argument(
        '--library-dir',
        type=Path,
        default=None,
        help='Path to library directory (default: storage/library)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-linearization of all PDFs'
    )
    
    args = parser.parse_args()
    
    # Determine library directory
    if args.library_dir:
        library_dir = args.library_dir.resolve()
    else:
        # Try environment variable
        storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
        library_dir = Path(storage_dir_env).resolve()
        
        # Try relative to script
        if not library_dir.exists():
            library_dir = project_root / 'storage' / 'library'
    
    fix_all_pdfs(library_dir, force_relinearize=args.force)


if __name__ == '__main__':
    main()
