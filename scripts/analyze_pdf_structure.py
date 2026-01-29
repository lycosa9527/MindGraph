"""
Analyze PDF structure to find root cause of large metadata downloads.

Checks:
1. PDF linearization status (linearized vs non-linearized)
2. XRef table location (beginning vs end of file)
3. XRef table size
4. Object stream locations
5. Why PDF.js downloads large amounts of data

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# Add project root to path before importing project modules
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

# Import project modules after path setup
_config_db_module = importlib.import_module('config.database')
get_db = _config_db_module.get_db

_library_module = importlib.import_module('services.library')
LibraryService = _library_module.LibraryService

_pdf_utils_module = importlib.import_module('services.library.pdf_utils')
resolve_library_path = _pdf_utils_module.resolve_library_path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def read_pdf_trailer(pdf_path: Path) -> Optional[Dict[str, Any]]:
    """
    Read PDF trailer to find xref location.

    Returns:
        Dict with trailer info including xref offset
    """
    try:
        with open(pdf_path, 'rb') as f:
            # Read last 1024 bytes (trailer is usually at end)
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            read_size = min(2048, file_size)  # Read last 2KB
            f.seek(max(0, file_size - read_size))
            tail = f.read()

            # Find trailer
            trailer_pos = tail.rfind(b'trailer')
            if trailer_pos == -1:
                return None

            trailer_section = tail[trailer_pos:].decode('latin-1', errors='ignore')

            # Find xref offset
            xref_offset = None
            if '/Prev' in trailer_section:
                # Has previous xref (non-linearized or incremental update)
                try:
                    prev_start = trailer_section.find('/Prev')
                    prev_end = trailer_section.find('\n', prev_start)
                    prev_line = trailer_section[prev_start:prev_end]
                    xref_offset = int(prev_line.split()[-1])
                except (ValueError, IndexError):
                    pass

            # Find root xref
            root_xref_start = trailer_section.find('/XRefStm')
            if root_xref_start == -1:
                root_xref_start = trailer_section.find('/XRef')

            # Check if linearized
            is_linearized = '/Linearized' in trailer_section

            return {
                'is_linearized': is_linearized,
                'xref_offset': xref_offset,
                'file_size': file_size,
                'trailer_at_end': True,
                'has_prev_xref': '/Prev' in trailer_section
            }
    except Exception as e:
        logger.error("Error reading PDF trailer: %s", e)
        return None


def analyze_pdf_structure_detailed(pdf_path: Path) -> Dict[str, Any]:
    """
    Detailed PDF structure analysis.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with detailed analysis results
    """
    result = {
        'file_name': pdf_path.name,
        'file_path': str(pdf_path),
        'file_size': pdf_path.stat().st_size if pdf_path.exists() else 0,
        'file_size_mb': round(pdf_path.stat().st_size / 1024 / 1024, 2) if pdf_path.exists() else 0,
        'is_linearized': False,
        'xref_location': 'unknown',
        'xref_size_estimate': 0,
        'needs_end_read': False,
        'analysis_error': None
    }

    if not pdf_path.exists():
        result['analysis_error'] = 'File not found'
        return result

    # Read PDF trailer to check structure
    trailer_info = read_pdf_trailer(pdf_path)
    if trailer_info:
        result['is_linearized'] = trailer_info.get('is_linearized', False)
        result['has_prev_xref'] = trailer_info.get('has_prev_xref', False)

        if result['is_linearized']:
            result['xref_location'] = 'beginning'
            result['needs_end_read'] = False
            result['xref_size_estimate'] = 'small (~5-50 KB)'
        else:
            result['xref_location'] = 'end'
            result['needs_end_read'] = True
            # For non-linearized PDFs, PDF.js must read from end
            # The xref table can be large, especially if PDF has many objects
            file_size_mb = result['file_size_mb']
            if file_size_mb > 50:
                result['xref_size_estimate'] = (
                    f'large (may need to read {file_size_mb * 0.1:.1f}-'
                    f'{file_size_mb * 0.3:.1f} MB from end)'
                )
            else:
                result['xref_size_estimate'] = (
                    f'medium (may need to read {file_size_mb * 0.2:.1f}-'
                    f'{file_size_mb * 0.5:.1f} MB from end)'
                )

    # Try PyPDF2 for additional info
    if PyPDF2 is None:
        result['analysis_error'] = 'PyPDF2 not available'
    else:
        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                result['page_count'] = len(pdf_reader.pages)

                # Check if PDF has object streams (can make xref larger)
                try:
                    if hasattr(pdf_reader, 'xref'):
                        xref = pdf_reader.xref
                        if xref:
                            result['xref_object_count'] = (
                                len(xref) if isinstance(xref, dict) else 0
                            )
                except (AttributeError, TypeError):
                    pass
        except Exception as e:
            result['analysis_error'] = f'PyPDF2 error: {e}'

    return result


def analyze_library_pdfs_detailed() -> None:
    """
    Analyze all PDFs in library to find root cause of large metadata downloads.
    """
    db: Session = next(get_db())
    service = LibraryService(db)

    # Get all documents
    result = service.get_documents(page=1, page_size=1000)
    documents = result['documents']

    if not documents:
        logger.info("No documents found in library")
        return

    logger.info("Found %d document(s) in library", len(documents))
    logger.info("=" * 80)
    logger.info("PDF STRUCTURE ANALYSIS - Finding Root Cause of Large Metadata Downloads")
    logger.info("=" * 80)
    logger.info("")

    analyses = []

    for doc_data in documents:
        doc_id = doc_data['id']
        title = doc_data['title']

        # Get full document to access file_path
        document = service.get_document(doc_id)
        if not document:
            continue

        # Resolve file path
        file_path = resolve_library_path(
            document.file_path,
            service.storage_dir,
            Path.cwd()
        )

        if not file_path or not file_path.exists():
            logger.warning(
                "PDF file not found for document %d: %s",
                doc_id,
                document.file_path
            )
            continue

        # Analyze PDF structure
        analysis = analyze_pdf_structure_detailed(file_path)
        analysis['document_id'] = doc_id
        analysis['title'] = title
        analyses.append(analysis)

    # Print detailed analysis
    logger.info("DETAILED PDF STRUCTURE ANALYSIS:")
    logger.info("-" * 80)

    for analysis in analyses:
        if analysis.get('analysis_error'):
            logger.warning(
                "⚠️  %s (ID: %d): %s",
                analysis['title'],
                analysis['document_id'],
                analysis['analysis_error']
            )
            continue

        logger.info("📄 %s (ID: %d)", analysis['title'], analysis['document_id'])
        logger.info("   File: %s", analysis['file_name'])
        file_size_str = f"{analysis['file_size']:,}"
        logger.info(
            "   Size: %s MB (%s bytes)",
            analysis['file_size_mb'],
            file_size_str
        )
        logger.info("   Pages: %s", analysis.get('page_count', 'unknown'))
        logger.info("")
        logger.info("   📊 PDF STRUCTURE:")
        linearized_status = '✅ YES' if analysis['is_linearized'] else '❌ NO'
        logger.info("      Linearized: %s", linearized_status)
        logger.info("      XRef Location: %s", analysis['xref_location'])
        needs_end_read_status = (
            '✅ YES' if analysis['needs_end_read'] else '❌ NO'
        )
        logger.info("      Needs End Read: %s", needs_end_read_status)
        logger.info("      XRef Size Estimate: %s", analysis['xref_size_estimate'])
        logger.info("")

        # Root cause analysis
        if not analysis['is_linearized']:
            logger.info("   🔍 ROOT CAUSE ANALYSIS:")
            logger.info("      ❌ PDF is NON-LINEARIZED")
            logger.info(
                "      ⚠️  XRef table is at END of file (%s MB file)",
                analysis['file_size_mb']
            )
            logger.info("      ⚠️  PDF.js MUST read from end to locate pages")
            logger.info(
                "      ⚠️  This requires downloading significant data "
                "from end of file"
            )
            logger.info(
                "      💡 Solution: Linearize PDF to move xref to beginning"
            )
            logger.info("")
        else:
            logger.info(
                "   ✅ PDF is LINEARIZED - xref at beginning, "
                "should load quickly"
            )
            logger.info("")

    # Summary and recommendations
    logger.info("=" * 80)
    logger.info("SUMMARY & RECOMMENDATIONS:")
    logger.info("=" * 80)

    linearized_count = sum(1 for a in analyses if a.get('is_linearized'))
    non_linearized_count = len(analyses) - linearized_count

    logger.info("Total PDFs analyzed: %d", len(analyses))
    logger.info("  ✅ Linearized PDFs: %d", linearized_count)
    logger.info("  ❌ Non-linearized PDFs: %d", non_linearized_count)
    logger.info("")

    if non_linearized_count > 0:
        logger.info("⚠️  ROOT CAUSE IDENTIFIED:")
        logger.info("   Non-linearized PDFs have xref table at END of file")
        logger.info("   PDF.js must read from end to locate pages")
        logger.info("   This causes large initial downloads (xref + object streams)")
        logger.info("")
        logger.info("💡 SOLUTIONS:")
        logger.info("   1. Linearize PDFs using tools like:")
        logger.info("      - qpdf --linearize input.pdf output.pdf")
        logger.info("      - pdftk input.pdf output output.pdf")
        logger.info("      - Ghostscript: gs -sDEVICE=pdfwrite -dPDFSETTINGS=/screen -o output.pdf input.pdf")
        logger.info("")
        logger.info("   2. Linearized PDFs have xref at BEGINNING (~5-50 KB)")
        logger.info("      This allows PDF.js to load structure quickly")
        logger.info("      Page content still loads lazily via Range requests")
        logger.info("")
        logger.info("   3. Current behavior is CORRECT for non-linearized PDFs")
        logger.info("      PDF.js cannot work without reading xref table")
        logger.info("      The large download is unavoidable for non-linearized PDFs")
        logger.info("")
    else:
        logger.info("✅ All PDFs are linearized - metadata downloads should be small")
        logger.info("   If you're still seeing large downloads, check Network tab")
        logger.info("   for actual Range requests vs full file downloads")


if __name__ == "__main__":
    analyze_library_pdfs_detailed()
