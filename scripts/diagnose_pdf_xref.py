"""
Diagnose PDF xref structure to find why PDF.js downloads entire file.

Checks:
1. Is PDF actually linearized?
2. Where is the xref table located?
3. Are there multiple xref tables (incremental updates)?
4. Are there object streams that PDF.js needs to read?
5. What is the actual structure PDF.js will encounter?

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def find_all_startxref(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Find all startxref markers in PDF (for incremental updates).
    
    Returns:
        List of dicts with startxref info, ordered from latest to oldest
    """
    results = []
    file_size = pdf_path.stat().st_size
    
    with open(pdf_path, 'rb') as f:
        # Read last 32KB to find all startxref markers
        read_size = min(32768, file_size)
        f.seek(max(0, file_size - read_size))
        tail = f.read()
        
        # Find all startxref positions
        pos = 0
        while True:
            pos = tail.find(b'startxref', pos)
            if pos == -1:
                break
            
            # Calculate actual file offset
            file_offset = file_size - read_size + pos
            
            # Read the startxref section
            startxref_section = tail[pos:pos + 200].decode('latin-1', errors='ignore')
            startxref_match = re.search(r'startxref\s+(\d+)', startxref_section)
            
            if startxref_match:
                xref_offset = int(startxref_match.group(1))
                results.append({
                    'startxref_offset': file_offset,
                    'xref_offset': xref_offset,
                    'position_ratio': xref_offset / file_size if file_size > 0 else 0
                })
            
            pos += 9
    
    # Sort by startxref offset (latest first)
    results.sort(key=lambda x: x['startxref_offset'], reverse=True)
    return results


def read_trailer_dict(pdf_path: Path, trailer_offset: int) -> Dict[str, Any]:
    """
    Read trailer dictionary at given offset.
    
    Returns:
        Dict with trailer information
    """
    result = {
        'has_prev': False,
        'prev_xref_offset': None,
        'is_linearized': False,
        'has_xref_stream': False,
        'xref_stream_offset': None
    }
    
    with open(pdf_path, 'rb') as f:
        # Read around trailer
        f.seek(max(0, trailer_offset - 500))
        trailer_data = f.read(2000)
        trailer_text = trailer_data.decode('latin-1', errors='ignore')
        
        # Check for /Prev (previous xref)
        prev_match = re.search(r'/Prev\s+(\d+)', trailer_text)
        if prev_match:
            result['has_prev'] = True
            result['prev_xref_offset'] = int(prev_match.group(1))
        
        # Check for /Linearized
        result['is_linearized'] = '/Linearized' in trailer_text
        
        # Check for /XRefStm (xref stream)
        xref_stm_match = re.search(r'/XRefStm\s+(\d+)', trailer_text)
        if xref_stm_match:
            result['has_xref_stream'] = True
            result['xref_stream_offset'] = int(xref_stm_match.group(1))
    
    return result


def check_linearization_dict(pdf_path: Path) -> Dict[str, Any]:
    """
    Check if PDF has linearization dictionary at the beginning.
    
    Returns:
        Dict with linearization info
    """
    result = {
        'has_linearization_dict': False,
        'linearization_dict_offset': None,
        'file_length': None,
        'first_page_offset': None
    }
    
    file_size = pdf_path.stat().st_size
    
    # Read first 8KB to find linearization dictionary
    with open(pdf_path, 'rb') as f:
        head = f.read(min(8192, file_size))
        head_text = head.decode('latin-1', errors='ignore')
        
        # Look for /Linearized marker
        if '/Linearized' in head_text:
            result['has_linearization_dict'] = True
            
            # Try to find the linearization dictionary object
            # Format: obj\n<< /Linearized 1 /L <file_size> /O <first_page_offset> ... >>
            linearized_match = re.search(r'/Linearized\s+(\d+)', head_text)
            if linearized_match:
                # Look for /L (file length) and /O (first page offset)
                l_match = re.search(r'/L\s+(\d+)', head_text)
                o_match = re.search(r'/O\s+(\d+)', head_text)
                
                if l_match:
                    result['file_length'] = int(l_match.group(1))
                if o_match:
                    result['first_page_offset'] = int(o_match.group(1))
    
    return result


def analyze_xref_chain(pdf_path: Path) -> Dict[str, Any]:
    """
    Analyze complete xref chain to see what PDF.js will encounter.
    
    Returns:
        Dict with complete xref chain analysis
    """
    file_size = pdf_path.stat().st_size
    result = {
        'file_size': file_size,
        'file_size_mb': round(file_size / 1024 / 1024, 2),
        'is_linearized': False,
        'xref_chain': [],
        'total_xref_tables': 0,
        'main_xref_location': 'unknown',
        'main_xref_offset': None,
        'main_xref_size_bytes': 0,
        'main_xref_size_kb': 0,
        'needs_full_scan': False
    }
    
    # Check for linearization dictionary
    lin_info = check_linearization_dict(pdf_path)
    result['is_linearized'] = lin_info['has_linearization_dict']
    
    # Find all startxref markers
    startxref_list = find_all_startxref(pdf_path)
    result['total_xref_tables'] = len(startxref_list)
    
    if not startxref_list:
        result['needs_full_scan'] = True
        return result
    
    # Analyze each xref table
    for i, startxref_info in enumerate(startxref_list):
        xref_offset = startxref_info['xref_offset']
        position_ratio = startxref_info['position_ratio']
        
        # Find trailer for this xref
        # Trailer is before startxref
        with open(pdf_path, 'rb') as f:
            # Read around startxref to find trailer
            read_start = max(0, startxref_info['startxref_offset'] - 2000)
            f.seek(read_start)
            trailer_data = f.read(3000)
            trailer_text = trailer_data.decode('latin-1', errors='ignore')
            
            # Find trailer dictionary
            trailer_dict = {}
            trailer_match = re.search(r'trailer\s*<<(.*?)>>', trailer_text, re.DOTALL)
            if trailer_match:
                trailer_content = trailer_match.group(1)
                trailer_dict = read_trailer_dict(pdf_path, read_start + trailer_match.start())
            
            # Calculate xref table size
            trailer_pos = trailer_text.rfind('trailer')
            if trailer_pos != -1:
                # Estimate xref size (from xref_offset to trailer)
                trailer_abs_offset = read_start + trailer_pos
                xref_size = trailer_abs_offset - xref_offset
            else:
                xref_size = 0
        
        xref_info = {
            'index': i + 1,
            'xref_offset': xref_offset,
            'xref_offset_mb': round(xref_offset / 1024 / 1024, 2),
            'position_ratio': position_ratio,
            'position': 'beginning' if position_ratio < 0.1 else ('end' if position_ratio > 0.9 else 'middle'),
            'xref_size_bytes': xref_size,
            'xref_size_kb': round(xref_size / 1024, 2),
            'has_prev': trailer_dict.get('has_prev', False),
            'prev_xref_offset': trailer_dict.get('prev_xref_offset')
        }
        
        result['xref_chain'].append(xref_info)
        
        # Main xref is the first one (latest)
        if i == 0:
            result['main_xref_location'] = xref_info['position']
            result['main_xref_offset'] = xref_offset
            result['main_xref_size_bytes'] = xref_size
            result['main_xref_size_kb'] = xref_info['xref_size_kb']
    
    # Determine if PDF.js needs to scan
    if result['total_xref_tables'] > 1:
        result['needs_full_scan'] = True
    elif result['main_xref_location'] == 'end' and not result['is_linearized']:
        result['needs_full_scan'] = True
    elif result['main_xref_location'] != 'beginning' and not result['is_linearized']:
        result['needs_full_scan'] = True
    
    return result


def diagnose_pdf(pdf_path: Path) -> None:
    """
    Diagnose a single PDF file.
    """
    logger.info("=" * 80)
    logger.info(f"Diagnosing: {pdf_path.name}")
    logger.info("=" * 80)
    
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        return
    
    analysis = analyze_xref_chain(pdf_path)
    
    logger.info("")
    logger.info("📊 FILE INFORMATION:")
    logger.info(f"   Size: {analysis['file_size']:,} bytes ({analysis['file_size_mb']} MB)")
    logger.info("")
    
    logger.info("🔍 LINEARIZATION STATUS:")
    if analysis['is_linearized']:
        logger.info("   ✅ PDF is LINEARIZED (has /Linearized dictionary)")
    else:
        logger.info("   ❌ PDF is NOT LINEARIZED")
    logger.info("")
    
    logger.info("📋 XREF TABLE ANALYSIS:")
    logger.info(f"   Total xref tables found: {analysis['total_xref_tables']}")
    
    if analysis['total_xref_tables'] == 0:
        logger.error("   ⚠️  NO XREF TABLES FOUND - PDF may be corrupted!")
        return
    
    for i, xref_info in enumerate(analysis['xref_chain']):
        logger.info("")
        logger.info(f"   XRef Table #{xref_info['index']} (latest first):")
        logger.info(f"      Offset: {xref_info['xref_offset']:,} bytes ({xref_info['xref_offset_mb']} MB)")
        logger.info(f"      Location: {xref_info['position']} ({xref_info['position_ratio']*100:.1f}% into file)")
        logger.info(f"      Size: {xref_info['xref_size_bytes']:,} bytes ({xref_info['xref_size_kb']} KB)")
        
        if xref_info['has_prev']:
            logger.info(f"      ⚠️  Has /Prev pointing to previous xref at offset {xref_info['prev_xref_offset']}")
            logger.info(f"      ⚠️  This means PDF has INCREMENTAL UPDATES")
            logger.info(f"      ⚠️  PDF.js will need to follow the chain!")
    
    logger.info("")
    logger.info("🎯 PDF.JS BEHAVIOR PREDICTION:")
    
    if analysis['needs_full_scan']:
        logger.info("   ❌ PDF.js will need to SCAN THROUGH THE FILE")
        logger.info("   ❌ This causes full file download!")
        
        reasons = []
        if analysis['total_xref_tables'] > 1:
            reasons.append(f"Multiple xref tables ({analysis['total_xref_tables']})")
        if analysis['main_xref_location'] == 'end' and not analysis['is_linearized']:
            reasons.append("Main xref at end (non-linearized)")
        if analysis['main_xref_location'] == 'middle':
            reasons.append("Main xref in middle")
        
        logger.info("")
        logger.info("   Root causes:")
        for reason in reasons:
            logger.info(f"      • {reason}")
    else:
        logger.info("   ✅ PDF.js should be able to read xref quickly")
        logger.info(f"   ✅ Expected initial download: ~{analysis['main_xref_size_kb']} KB")
    
    logger.info("")
    logger.info("💡 RECOMMENDATIONS:")
    
    if not analysis['is_linearized']:
        logger.info("   1. Run qpdf --linearize to linearize the PDF")
        logger.info("      This will:")
        logger.info("        • Move xref table to beginning")
        logger.info("        • Remove incremental updates")
        logger.info("        • Enable efficient lazy loading")
    
    if analysis['total_xref_tables'] > 1:
        logger.info("   2. PDF has incremental updates - linearization will remove them")
    
    if analysis['main_xref_location'] != 'beginning':
        logger.info("   3. Xref table is not at beginning - linearization will fix this")
    
    logger.info("")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose PDF xref structure")
    parser.add_argument(
        'pdf_path',
        type=Path,
        help='Path to PDF file to diagnose'
    )
    
    args = parser.parse_args()
    
    diagnose_pdf(args.pdf_path)


if __name__ == '__main__':
    main()
