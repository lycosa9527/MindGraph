"""
Analyze PDF files directly from storage/library/ directory.

Checks PDF structure and verifies lazy loading feasibility.
No database required - analyzes files directly.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from typing import Dict, Any, List

# Try to import PDF libraries
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("Warning: PyPDF2 not available. Install with: pip install PyPDF2")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def analyze_pdf_structure(pdf_path: Path) -> Dict[str, Any]:
    """
    Analyze PDF structure to determine lazy loading feasibility.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dict with analysis results
    """
    result = {
        'file_name': pdf_path.name,
        'file_path': str(pdf_path),
        'file_size': pdf_path.stat().st_size if pdf_path.exists() else 0,
        'file_size_mb': round(pdf_path.stat().st_size / 1024 / 1024, 2) if pdf_path.exists() else 0,
        'has_outline': False,
        'outline_count': 0,
        'page_count': 0,
        'is_linearized': False,
        'analysis_method': None,
        'error': None
    }
    
    if not pdf_path.exists():
        result['error'] = 'File not found'
        return result
    
    # Try PyPDF2 first
    if PYPDF2_AVAILABLE:
        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                result['page_count'] = len(pdf_reader.pages)
                result['analysis_method'] = 'PyPDF2'
                
                # Check for outline/bookmarks
                try:
                    outline = pdf_reader.outline
                    if outline:
                        result['has_outline'] = True
                        result['outline_count'] = len(outline)
                except:
                    pass
                
                # Check if PDF is linearized (optimized for web)
                try:
                    # Check trailer for linearization flag
                    if hasattr(pdf_reader, 'trailer'):
                        result['is_linearized'] = '/Linearized' in str(pdf_reader.trailer) if pdf_reader.trailer else False
                except:
                    pass
                
                return result
        except Exception as e:
            result['error'] = f'PyPDF2 error: {str(e)}'
    
    # Try pdfplumber as fallback
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                result['page_count'] = len(pdf.pages)
                result['analysis_method'] = 'pdfplumber'
                return result
        except Exception as e:
            result['error'] = f'pdfplumber error: {str(e)}'
    
    if not result['error']:
        result['error'] = 'No PDF library available'
    return result


def analyze_library_pdfs() -> None:
    """
    Analyze all PDFs in storage/library/ directory.
    """
    # Find storage/library directory
    storage_dir = Path('storage/library')
    if not storage_dir.exists():
        # Try absolute path
        storage_dir = Path(__file__).parent.parent / 'storage' / 'library'
    
    if not storage_dir.exists():
        logger.error(f"Library directory not found: {storage_dir}")
        logger.info("Please ensure PDFs are in storage/library/ directory")
        return
    
    # Find all PDF files
    pdf_files = list(storage_dir.glob("*.pdf"))
    
    if not pdf_files:
        logger.info(f"No PDF files found in {storage_dir}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF file(s) in {storage_dir}")
    logger.info("=" * 80)
    
    total_size = 0
    total_pages = 0
    pdfs_with_outline = 0
    pdfs_without_outline = 0
    
    analyses: List[Dict[str, Any]] = []
    
    for pdf_path in sorted(pdf_files):
        analysis = analyze_pdf_structure(pdf_path)
        analyses.append(analysis)
        
        if analysis['error']:
            logger.warning(f"⚠️  {analysis['file_name']}: {analysis['error']}")
            continue
        
        total_size += analysis['file_size']
        total_pages += analysis['page_count']
        
        if analysis['has_outline']:
            pdfs_with_outline += 1
        else:
            pdfs_without_outline += 1
    
    # Print summary
    logger.info("=" * 80)
    logger.info("PDF LAZY LOADING ANALYSIS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total PDFs analyzed: {len([a for a in analyses if not a.get('error')])}")
    logger.info(f"Total size: {round(total_size / 1024 / 1024, 2)} MB")
    logger.info(f"Total pages: {total_pages}")
    if analyses and not all(a.get('error') for a in analyses):
        valid_analyses = [a for a in analyses if not a.get('error')]
        logger.info(f"Average size per PDF: {round(total_size / len(valid_analyses) / 1024 / 1024, 2)} MB")
        logger.info(f"Average pages per PDF: {round(total_pages / len(valid_analyses), 1)}")
    logger.info(f"PDFs with outline/bookmarks: {pdfs_with_outline}")
    logger.info(f"PDFs without outline/bookmarks: {pdfs_without_outline}")
    logger.info("")
    
    # Print detailed analysis for each PDF
    logger.info("DETAILED ANALYSIS:")
    logger.info("-" * 80)
    for analysis in analyses:
        if analysis.get('error'):
            continue
            
        logger.info(f"📄 {analysis['file_name']}")
        logger.info(f"   Size: {analysis['file_size_mb']} MB ({analysis['file_size']:,} bytes)")
        logger.info(f"   Pages: {analysis['page_count']}")
        logger.info(f"   Has Outline: {analysis['has_outline']} ({analysis['outline_count']} entries)")
        logger.info(f"   Analysis Method: {analysis['analysis_method']}")
        
        # Lazy loading assessment
        if analysis['file_size'] > 5 * 1024 * 1024:  # > 5MB
            logger.info(f"   ⚠️  Large PDF - lazy loading is CRITICAL for performance")
        elif analysis['file_size'] > 1 * 1024 * 1024:  # > 1MB
            logger.info(f"   ✓ Medium PDF - lazy loading will improve performance")
        else:
            logger.info(f"   ✓ Small PDF - lazy loading still beneficial")
        
        if analysis['page_count'] > 50:
            logger.info(f"   ⚠️  Many pages ({analysis['page_count']}) - lazy loading prevents loading all pages")
        
        if not analysis['has_outline']:
            logger.info(f"   ℹ️  No outline/bookmarks (normal for scanned PDFs)")
        
        logger.info("")
    
    # Lazy loading verification
    logger.info("=" * 80)
    logger.info("LAZY LOADING VERIFICATION:")
    logger.info("=" * 80)
    logger.info("✓ PDF.js lazy loading works by:")
    logger.info("  1. Loading PDF metadata first (~5-50 KB)")
    logger.info("  2. Using HTTP Range Requests to fetch pages on-demand")
    logger.info("  3. Only downloading page data when user navigates")
    logger.info("")
    logger.info("Expected behavior:")
    logger.info("  - Initial load: ~5-50 KB (metadata only)")
    logger.info("  - Page navigation: ~200-500 KB per page (on-demand)")
    logger.info("  - Total downloaded: Only pages viewed, not entire PDF")
    logger.info("")
    logger.info("To verify lazy loading in browser:")
    logger.info("  1. Open browser DevTools → Network tab")
    logger.info("  2. Filter by 'PDF' or 'file'")
    logger.info("  3. Open a PDF in the viewer")
    logger.info("  4. Check initial request size (should be small, ~5-50 KB)")
    logger.info("  5. Navigate to different pages")
    logger.info("  6. Verify Range requests (Status: 206 Partial Content)")
    logger.info("  7. Check 'Range' header in request: 'bytes=XXXXX-YYYYY'")
    logger.info("  8. Total bytes downloaded should be << PDF file size")


if __name__ == "__main__":
    analyze_library_pdfs()
