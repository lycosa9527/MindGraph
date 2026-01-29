"""
PDF Optimizer Module for Library

Analyzes PDF structure and optimizes PDFs for efficient lazy loading.
Checks xref table location and linearizes PDFs if needed.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

logger = logging.getLogger(__name__)


class PDFStructureInfo:
    """Information about PDF structure."""

    def __init__(self):
        self.is_linearized: bool = False
        self.xref_offset: Optional[int] = None
        self.xref_size_bytes: int = 0
        self.xref_size_kb: float = 0.0
        self.trailer_offset: Optional[int] = None
        self.file_size: int = 0
        self.xref_location: str = 'unknown'
        self.needs_optimization: bool = False
        self.analysis_error: Optional[str] = None


def analyze_pdf_structure(pdf_path: Path) -> PDFStructureInfo:
    """
    Analyze PDF structure to determine if optimization is needed.
    
    Checks:
    1. /Linearized marker at BEGINNING of file (linearized PDFs have this)
    2. xref table location (beginning = optimized, end = needs optimization)
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        PDFStructureInfo with analysis results
    """
    info = PDFStructureInfo()
    info.file_size = pdf_path.stat().st_size if pdf_path.exists() else 0

    if not pdf_path.exists():
        info.analysis_error = 'File not found'
        return info

    try:
        with open(pdf_path, 'rb') as f:
            file_size = info.file_size

            # Check for /Linearized at BEGINNING of file (first 4KB)
            # Linearized PDFs have a linearization dictionary near the start
            f.seek(0)
            head = f.read(min(4096, file_size))
            head_text = head.decode('latin-1', errors='ignore')
            info.is_linearized = '/Linearized' in head_text

            # Read end of file for xref location
            read_size = min(16384, file_size)
            f.seek(max(0, file_size - read_size))
            tail = f.read()

            # Find trailer
            trailer_pos_in_tail = tail.rfind(b'trailer')
            if trailer_pos_in_tail == -1:
                # Some PDFs use xref streams instead of traditional trailer
                # Check for startxref anyway
                pass
            else:
                trailer_offset = file_size - read_size + trailer_pos_in_tail
                info.trailer_offset = trailer_offset

            # Find startxref offset
            startxref_pos = tail.rfind(b'startxref')
            if startxref_pos != -1:
                startxref_section = tail[startxref_pos:startxref_pos + 100].decode('latin-1', errors='ignore')
                startxref_match = re.search(r'startxref\s+(\d+)', startxref_section)
                if startxref_match:
                    xref_offset = int(startxref_match.group(1))
                    info.xref_offset = xref_offset

                    # Calculate xref size (only if trailer found and offset is valid)
                    if info.trailer_offset and info.trailer_offset > xref_offset:
                        info.xref_size_bytes = info.trailer_offset - xref_offset
                        info.xref_size_kb = round(info.xref_size_bytes / 1024, 2)
                    else:
                        # Estimate based on remaining file size
                        info.xref_size_bytes = max(0, file_size - xref_offset)
                        info.xref_size_kb = round(info.xref_size_bytes / 1024, 2)

                    # Determine location based on xref offset
                    xref_position_ratio = xref_offset / file_size if file_size > 0 else 0
                    if xref_position_ratio < 0.1:
                        info.xref_location = 'beginning'
                        info.needs_optimization = False
                    elif xref_position_ratio > 0.9:
                        info.xref_location = 'end'
                        # Need optimization if xref at end AND not linearized
                        info.needs_optimization = not info.is_linearized
                    else:
                        info.xref_location = f'middle ({round(xref_position_ratio * 100, 1)}%)'
                        # Middle xref typically means incremental updates - needs optimization
                        info.needs_optimization = not info.is_linearized
    except Exception as e:
        info.analysis_error = str(e)
        logger.debug("Error analyzing PDF structure: %s", e, exc_info=True)

    return info


def check_qpdf_available() -> bool:
    """Check if qpdf is available."""
    try:
        result = subprocess.run(
            ['qpdf', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def linearize_pdf_with_qpdf(input_path: Path, output_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Linearize PDF using qpdf.
    
    qpdf exit codes:
    - 0: success
    - 2: errors (operation failed)
    - 3: warnings but operation succeeded
    
    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        
    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        result = subprocess.run(
            ['qpdf', '--linearize', str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False
        )

        # Exit code 0 = success, 3 = success with warnings
        if result.returncode in (0, 3):
            if result.returncode == 3:
                logger.warning(
                    "qpdf completed with warnings for %s: %s",
                    input_path.name,
                    (result.stderr or result.stdout or "").strip()[-200:]
                )
            return True, None
        else:
            return False, result.stderr or result.stdout
    except FileNotFoundError:
        return False, 'qpdf not found. Please install qpdf: https://qpdf.sourceforge.io/'
    except subprocess.TimeoutExpired:
        return False, 'qpdf timeout (took longer than 5 minutes)'
    except Exception as e:
        return False, str(e)


def linearize_pdf_with_pypdf(input_path: Path, output_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Linearize PDF using PyPDF2 (fallback if qpdf not available).
    
    Args:
        input_path: Input PDF path
        output_path: Output PDF path
        
    Returns:
        (success: bool, error_message: Optional[str])
    """
    if PyPDF2 is None:
        return False, 'PyPDF2 not available. Install with: pip install PyPDF2'

    try:
        with open(input_path, 'rb') as input_file:
            pdf_reader = PyPDF2.PdfReader(input_file)
            pdf_writer = PyPDF2.PdfWriter()

            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

            if pdf_reader.metadata:
                pdf_writer.add_metadata(pdf_reader.metadata)

            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)

            return True, None
    except Exception as e:
        return False, str(e)


def optimize_pdf(
    pdf_path: Path,
    backup: bool = True,
    prefer_qpdf: bool = True
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Optimize PDF for efficient lazy loading by linearizing if needed.
    
    Args:
        pdf_path: Path to PDF file
        backup: If True, create backup before optimizing
        prefer_qpdf: If True, prefer qpdf over PyPDF2
        
    Returns:
        (success: bool, error_message: Optional[str], stats: Dict)
        
    Stats dict contains:
        - was_optimized: bool
        - original_size: int
        - new_size: int
        - size_change: int
        - method: str ('qpdf', 'pypdf', or None)
    """
    stats = {
        'was_optimized': False,
        'original_size': 0,
        'new_size': 0,
        'size_change': 0,
        'method': None
    }

    # Check if file exists before accessing
    if not pdf_path.exists():
        return False, f"File not found: {pdf_path}", stats

    try:
        original_size = pdf_path.stat().st_size
        stats['original_size'] = original_size
        stats['new_size'] = original_size
    except OSError as e:
        return False, f"Cannot read file: {e}", stats

    # Analyze PDF structure
    info = analyze_pdf_structure(pdf_path)

    if info.analysis_error:
        return False, f"Analysis failed: {info.analysis_error}", stats

    # Check if optimization is needed
    if not info.needs_optimization:
        logger.debug("PDF %s does not need optimization (linearized or xref at beginning)", pdf_path.name)
        return True, None, stats

    logger.info("Optimizing PDF: %s (xref at %s)", pdf_path.name, info.xref_location)

    # Create backup if requested
    if backup:
        backup_path = pdf_path.with_suffix('.pdf.backup')
        if not backup_path.exists():
            try:
                logger.debug("Creating backup: %s", backup_path.name)
                shutil.copy2(pdf_path, backup_path)
            except OSError as e:
                return False, f"Failed to create backup: {e}", stats

    # Check for qpdf
    qpdf_available = check_qpdf_available() if prefer_qpdf else False

    # Create temporary output file
    temp_output = pdf_path.with_suffix('.pdf.optimized')

    # Linearize PDF
    if qpdf_available:
        logger.debug("Using qpdf to linearize %s", pdf_path.name)
        success, error = linearize_pdf_with_qpdf(pdf_path, temp_output)
        method = 'qpdf'
    else:
        logger.debug("Using PyPDF2 to linearize %s", pdf_path.name)
        success, error = linearize_pdf_with_pypdf(pdf_path, temp_output)
        method = 'pypdf'

    if success:
        # Verify temp file exists before reading size
        if not temp_output.exists():
            return False, "Optimization succeeded but output file not found", stats

        try:
            new_size = temp_output.stat().st_size
        except OSError as e:
            # Clean up if we can
            if temp_output.exists():
                temp_output.unlink()
            return False, f"Cannot read optimized file size: {e}", stats

        size_change = new_size - stats['original_size']

        # Replace original with optimized version
        try:
            shutil.move(str(temp_output), str(pdf_path))
        except OSError as e:
            # Clean up temp file on failure
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except OSError:
                    pass
            return False, f"Failed to replace original file: {e}", stats

        stats['was_optimized'] = True
        stats['new_size'] = new_size
        stats['size_change'] = size_change
        stats['method'] = method

        logger.info(
            "Successfully optimized %s: %s bytes -> %s bytes (%s bytes)",
            pdf_path.name,
            f"{stats['original_size']:,}",
            f"{new_size:,}",
            f"{size_change:+,}"
        )

        return True, None, stats
    else:
        # Clean up temp file
        if temp_output.exists():
            try:
                temp_output.unlink()
            except OSError:
                pass

        return False, error, stats


def should_optimize_pdf(pdf_path: Path) -> Tuple[bool, Optional[str], PDFStructureInfo]:
    """
    Check if PDF should be optimized without actually optimizing it.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        (should_optimize: bool, reason: Optional[str], structure_info: PDFStructureInfo)
    """
    info = analyze_pdf_structure(pdf_path)

    if info.analysis_error:
        return False, f"Analysis failed: {info.analysis_error}", info

    if not info.needs_optimization:
        return False, None, info

    reason = f"XRef table at {info.xref_location} ({info.xref_size_kb} KB)"
    if info.xref_location == 'end':
        reason += " - linearization will enable efficient lazy loading"

    return True, reason, info
