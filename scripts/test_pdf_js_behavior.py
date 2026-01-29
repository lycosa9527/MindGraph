"""
Test what PDF.js will actually encounter when loading a PDF.

Checks:
1. Linearization dictionary presence and location
2. Xref table location and size
3. Object streams that PDF.js might need to read
4. Whether PDF structure allows efficient lazy loading

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_linearization_dict(pdf_path: Path) -> Dict[str, Any]:
    """
    Check for linearization dictionary at the beginning of PDF.

    PDF.js looks for this to determine if PDF is linearized.
    """
    result = {
        'has_linearization_dict': False,
        'linearization_dict_offset': None,
        'file_length': None,
        'first_page_offset': None,
        'hint_table_offset': None
    }

    file_size = pdf_path.stat().st_size

    # Read first 32KB to find linearization dictionary
    with open(pdf_path, 'rb') as f:
        head = f.read(min(32768, file_size))
        head_text = head.decode('latin-1', errors='ignore')

        # Look for /Linearized marker
        if '/Linearized' in head_text:
            result['has_linearization_dict'] = True

            # Try to find the linearization dictionary object
            # Format: obj\n<< /Linearized 1 /L <file_size> /O <first_page_offset> /E <hint_table_offset> ... >>
            lin_match = re.search(r'/Linearized\s+(\d+)', head_text)
            if lin_match:
                # Look for /L (file length)
                l_match = re.search(r'/L\s+(\d+)', head_text)
                if l_match:
                    result['file_length'] = int(l_match.group(1))

                # Look for /O (first page offset)
                o_match = re.search(r'/O\s+(\d+)', head_text)
                if o_match:
                    result['first_page_offset'] = int(o_match.group(1))

                # Look for /E (hint table offset)
                e_match = re.search(r'/E\s+(\d+)', head_text)
                if e_match:
                    result['hint_table_offset'] = int(e_match.group(1))

    return result


def find_xref_and_trailer(pdf_path: Path) -> Dict[str, Any]:
    """Find xref table and trailer information."""
    file_size = pdf_path.stat().st_size
    result = {
        'xref_offset': None,
        'xref_size_bytes': 0,
        'trailer_offset': None,
        'has_prev': False,
        'prev_xref_offset': None,
        'is_linearized_in_trailer': False
    }

    # Read last 16KB for trailer and startxref
    with open(pdf_path, 'rb') as f:
        read_size = min(16384, file_size)
        f.seek(max(0, file_size - read_size))
        tail = f.read()
        tail_text = tail.decode('latin-1', errors='ignore')

        # Find startxref
        startxref_pos = tail.rfind(b'startxref')
        if startxref_pos != -1:
            startxref_section = tail_text[startxref_pos:startxref_pos + 200]
            startxref_match = re.search(r'startxref\s+(\d+)', startxref_section)
            if startxref_match:
                result['xref_offset'] = int(startxref_match.group(1))

        # Find trailer
        trailer_pos = tail.rfind(b'trailer')
        if trailer_pos != -1:
            trailer_offset = file_size - read_size + trailer_pos
            result['trailer_offset'] = trailer_offset

            # Read trailer section
            trailer_section = tail_text[trailer_pos:]

            # Check for /Prev
            if '/Prev' in trailer_section:
                result['has_prev'] = True
                prev_match = re.search(r'/Prev\s+(\d+)', trailer_section)
                if prev_match:
                    result['prev_xref_offset'] = int(prev_match.group(1))

            # Check for /Linearized in trailer
            if '/Linearized' in trailer_section:
                result['is_linearized_in_trailer'] = True

    # Calculate xref size
    if result['xref_offset'] and result['trailer_offset']:
        result['xref_size_bytes'] = result['trailer_offset'] - result['xref_offset']

    return result


def check_object_streams(pdf_path: Path) -> Dict[str, Any]:
    """
    Check for object streams that PDF.js might need to read.

    Object streams contain compressed objects that PDF.js needs to decompress.
    If these are scattered throughout the file, PDF.js might download more data.
    """
    result = {
        'has_object_streams': False,
        'object_stream_count': 0,
        'object_stream_offsets': []
    }

    file_size = pdf_path.stat().st_size

    # Read entire file in chunks to find object streams
    # Object streams are marked with /Type /ObjStm
    chunk_size = 1024 * 1024  # 1MB chunks
    with open(pdf_path, 'rb') as f:
        offset = 0
        while offset < file_size:
            f.seek(offset)
            chunk = f.read(min(chunk_size, file_size - offset))
            chunk_text = chunk.decode('latin-1', errors='ignore')

            # Look for /Type /ObjStm
            if '/Type' in chunk_text and '/ObjStm' in chunk_text:
                # Find object stream objects
                objstm_pattern = r'(\d+)\s+\d+\s+obj.*?/Type\s+/ObjStm'
                matches = re.finditer(objstm_pattern, chunk_text, re.DOTALL)
                for match in matches:
                    result['has_object_streams'] = True
                    result['object_stream_count'] += 1
                    # Estimate offset (rough)
                    stream_offset = offset + match.start()
                    result['object_stream_offsets'].append(stream_offset)

            offset += chunk_size

    return result


def analyze_pdf_for_pdfjs(pdf_path: Path) -> Dict[str, Any]:
    """Complete analysis of what PDF.js will encounter."""
    file_size = pdf_path.stat().st_size

    lin_info = check_linearization_dict(pdf_path)
    xref_info = find_xref_and_trailer(pdf_path)
    objstm_info = check_object_streams(pdf_path)

    result = {
        'filename': pdf_path.name,
        'file_size': file_size,
        'file_size_mb': round(file_size / 1024 / 1024, 2),
        'linearization': lin_info,
        'xref': xref_info,
        'object_streams': objstm_info,
        'pdfjs_will_download': 'unknown'
    }

    # Determine what PDF.js will download
    if lin_info['has_linearization_dict']:
        # Linearized PDF - PDF.js should only download xref + linearization dict
        if xref_info['xref_offset']:
            xref_pos_ratio = xref_info['xref_offset'] / file_size if file_size > 0 else 0
            if xref_pos_ratio < 0.1:  # Xref at beginning
                if xref_info['has_prev']:
                    result['pdfjs_will_download'] = 'full_file'
                    result['reason'] = 'Linearized but has /Prev (incremental updates)'
                else:
                    estimated_download = xref_info['xref_size_bytes'] + 50000
                    download_kb = round(estimated_download/1024, 1)
                    result['pdfjs_will_download'] = (
                        f'{estimated_download} bytes (~{download_kb} KB)'
                    )
                    result['reason'] = 'Linearized, xref at beginning, no incremental updates'
            else:
                result['pdfjs_will_download'] = 'full_file'
                result['reason'] = 'Linearized but xref not at beginning'
        else:
            result['pdfjs_will_download'] = 'unknown'
            result['reason'] = 'Cannot find xref offset'
    else:
        # Not linearized - PDF.js will scan from end
        if xref_info['xref_offset']:
            bytes_from_end = file_size - xref_info['xref_offset']
            bytes_mb = round(bytes_from_end/1024/1024, 2)
            result['pdfjs_will_download'] = f'{bytes_from_end} bytes (~{bytes_mb} MB)'
            result['reason'] = 'Not linearized, xref at end'
        else:
            result['pdfjs_will_download'] = 'full_file'
            result['reason'] = 'Cannot find xref, PDF.js will scan entire file'

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze PDF structure from PDF.js perspective"
    )
    parser.add_argument(
        'pdf_path',
        type=Path,
        help='Path to PDF file to analyze'
    )

    args = parser.parse_args()

    if not args.pdf_path.exists():
        logger.error("PDF file not found: %s", args.pdf_path)
        return

    logger.info("=" * 80)
    logger.info("PDF.JS BEHAVIOR ANALYSIS")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Analyzing: %s", args.pdf_path.name)
    logger.info("")

    analysis = analyze_pdf_for_pdfjs(args.pdf_path)

    logger.info("File Size: %s MB (%s bytes)", analysis['file_size_mb'], analysis['file_size'])
    logger.info("")

    logger.info("Linearization Dictionary:")
    lin = analysis['linearization']
    if lin['has_linearization_dict']:
        logger.info("  ✅ Found at beginning of file")
        if lin['file_length']:
            logger.info("  File Length: %s bytes", lin['file_length'])
        if lin['first_page_offset']:
            logger.info("  First Page Offset: %s bytes", lin['first_page_offset'])
        if lin['hint_table_offset']:
            logger.info("  Hint Table Offset: %s bytes", lin['hint_table_offset'])
    else:
        logger.info("  ❌ NOT FOUND - PDF.js will treat as non-linearized")
    logger.info("")

    logger.info("XRef Table:")
    xref = analysis['xref']
    if xref['xref_offset']:
        xref_pos_ratio = xref['xref_offset'] / analysis['file_size'] if analysis['file_size'] > 0 else 0
        logger.info("  Offset: %s bytes (%.1f%% into file)", xref['xref_offset'], xref_pos_ratio * 100)
        logger.info("  Size: %s bytes (~%s KB)", xref['xref_size_bytes'], round(xref['xref_size_bytes']/1024, 1))
        if xref['has_prev']:
            logger.info("  ⚠️  Has /Prev: %s bytes (incremental updates!)", xref['prev_xref_offset'])
        else:
            logger.info("  ✅ No /Prev (no incremental updates)")
        if xref['is_linearized_in_trailer']:
            logger.info("  ✅ Marked as linearized in trailer")
    else:
        logger.info("  ❌ NOT FOUND")
    logger.info("")

    logger.info("Object Streams:")
    objstm = analysis['object_streams']
    if objstm['has_object_streams']:
        logger.info("  ⚠️  Found %d object stream(s)", objstm['object_stream_count'])
        logger.info("  Object streams may require PDF.js to read additional data")
    else:
        logger.info("  ✅ No object streams found")
    logger.info("")

    logger.info("=" * 80)
    logger.info("PDF.JS PREDICTED BEHAVIOR")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Expected Download: %s", analysis['pdfjs_will_download'])
    logger.info("Reason: %s", analysis.get('reason', 'Unknown'))
    logger.info("")

    if 'full_file' in str(analysis['pdfjs_will_download']):
        logger.info("⚠️  WARNING: PDF.js will likely download the entire file!")
        logger.info("   This will cause slow loading and high bandwidth usage.")
        logger.info("")
        logger.info("Recommendations:")
        if xref['has_prev']:
            logger.info("   1. Re-linearize PDF to remove incremental updates:")
            logger.info("      python scripts/fix_pdf_xref_issues.py --library-dir storage/library")
        if not lin['has_linearization_dict']:
            logger.info("   2. Linearize PDF to add linearization dictionary:")
            logger.info("      python scripts/fix_pdf_xref_issues.py --library-dir storage/library")
    else:
        logger.info("✅ PDF.js should download efficiently!")
        logger.info("   Expected initial download: %s", analysis['pdfjs_will_download'])


if __name__ == '__main__':
    main()
