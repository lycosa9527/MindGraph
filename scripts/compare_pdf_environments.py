"""
Compare PDF optimization status between environments.

Helps diagnose why PDFs work on WSL but not on Ubuntu by:
1. Checking qpdf availability and version
2. Analyzing PDF structure
3. Identifying differences

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import argparse
import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path before importing project modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import project modules dynamically to satisfy linter requirements
_pdf_optimizer_module = importlib.import_module('services.library.pdf_optimizer')
analyze_pdf_structure = _pdf_optimizer_module.analyze_pdf_structure
check_qpdf_available = _pdf_optimizer_module.check_qpdf_available

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def get_qpdf_version() -> Optional[str]:
    """Get qpdf version if available."""
    try:
        result = subprocess.run(
            ['qpdf', '--version'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            # qpdf version output format: "qpdf version X.Y.Z"
            version_line = result.stdout.strip().split('\n')[0]
            return version_line
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_environment() -> Dict[str, Any]:
    """Check environment configuration."""
    env_info = {
        'os': sys.platform,
        'python_version': sys.version,
        'qpdf_available': check_qpdf_available(),
        'qpdf_version': None,
        'library_storage_dir': os.getenv('LIBRARY_STORAGE_DIR', './storage/library'),
        'current_working_dir': str(Path.cwd()),
    }

    if env_info['qpdf_available']:
        env_info['qpdf_version'] = get_qpdf_version()

    return env_info


def analyze_pdf_collection(library_dir: Path) -> Dict[str, Any]:
    """Analyze all PDFs in library directory."""
    pdf_files = list(library_dir.glob("*.pdf"))

    if not pdf_files:
        return {
            'total': 0,
            'linearized': 0,
            'has_incremental_updates': 0,
            'xref_at_beginning': 0,
            'xref_at_end': 0,
            'needs_optimization': 0,
            'pdfs': []
        }

    results = {
        'total': len(pdf_files),
        'linearized': 0,
        'has_incremental_updates': 0,
        'xref_at_beginning': 0,
        'xref_at_end': 0,
        'xref_at_middle': 0,
        'needs_optimization': 0,
        'pdfs': []
    }

    for pdf_path in sorted(pdf_files):
        info = analyze_pdf_structure(pdf_path)

        pdf_info = {
            'filename': pdf_path.name,
            'file_size_mb': round(info.file_size / 1024 / 1024, 2),
            'is_linearized': info.is_linearized,
            'has_incremental_updates': info.has_incremental_updates,
            'xref_location': info.xref_location,
            'xref_offset_mb': round(info.xref_offset / 1024 / 1024, 2) if info.xref_offset else None,
            'needs_optimization': info.needs_optimization,
            'analysis_error': info.analysis_error
        }

        results['pdfs'].append(pdf_info)

        if info.is_linearized:
            results['linearized'] += 1
        if info.has_incremental_updates:
            results['has_incremental_updates'] += 1
        if info.xref_location == 'beginning':
            results['xref_at_beginning'] += 1
        elif info.xref_location == 'end':
            results['xref_at_end'] += 1
        elif 'middle' in info.xref_location:
            results['xref_at_middle'] += 1
        if info.needs_optimization:
            results['needs_optimization'] += 1

    return results


def print_environment_report(env_info: Dict[str, Any]) -> None:
    """Print environment information."""
    logger.info("=" * 80)
    logger.info("ENVIRONMENT INFORMATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Operating System: %s", env_info['os'])
    logger.info("Python Version: %s", env_info['python_version'].split('\n')[0])
    logger.info("")
    logger.info("qpdf Status:")
    if env_info['qpdf_available']:
        logger.info("  ✅ qpdf is AVAILABLE")
        if env_info['qpdf_version']:
            logger.info("  Version: %s", env_info['qpdf_version'])
    else:
        logger.info("  ❌ qpdf is NOT AVAILABLE")
        logger.info("  Install with:")
        logger.info("    Windows: Download from https://qpdf.sourceforge.io/")
        logger.info("    macOS: brew install qpdf")
        logger.info("    Linux: apt-get install qpdf or yum install qpdf")
    logger.info("")
    logger.info("Library Storage Directory: %s", env_info['library_storage_dir'])
    logger.info("Current Working Directory: %s", env_info['current_working_dir'])
    logger.info("")


def print_pdf_analysis_report(analysis: Dict[str, Any]) -> None:
    """Print PDF analysis results."""
    logger.info("=" * 80)
    logger.info("PDF COLLECTION ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    if analysis['total'] == 0:
        logger.info("No PDF files found in library directory")
        return

    logger.info("Total PDFs: %d", analysis['total'])
    logger.info("")
    logger.info("Optimization Status:")
    logger.info("  Linearized: %d (%.1f%%)",
                analysis['linearized'],
                (analysis['linearized'] / analysis['total'] * 100) if analysis['total'] > 0 else 0)
    logger.info("  Has Incremental Updates: %d (%.1f%%)",
                analysis['has_incremental_updates'],
                (analysis['has_incremental_updates'] / analysis['total'] * 100) if analysis['total'] > 0 else 0)
    logger.info("  Needs Optimization: %d (%.1f%%)",
                analysis['needs_optimization'],
                (analysis['needs_optimization'] / analysis['total'] * 100) if analysis['total'] > 0 else 0)
    logger.info("")
    logger.info("XRef Table Locations:")
    logger.info("  At Beginning: %d", analysis['xref_at_beginning'])
    logger.info("  At End: %d", analysis['xref_at_end'])
    logger.info("  In Middle: %d", analysis['xref_at_middle'])
    logger.info("")

    # Show problematic PDFs
    problematic = [p for p in analysis['pdfs'] if p['needs_optimization']]
    if problematic:
        logger.info("⚠️  PROBLEMATIC PDFs (need optimization):")
        for pdf in problematic:
            issues = []
            if pdf['has_incremental_updates']:
                issues.append("has incremental updates")
            if not pdf['is_linearized']:
                issues.append("not linearized")
            if pdf['xref_location'] != 'beginning':
                issues.append(f"xref at {pdf['xref_location']}")

            logger.info("  • %s (%s MB)", pdf['filename'], pdf['file_size_mb'])
            logger.info("    Issues: %s", ", ".join(issues))
        logger.info("")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare PDF optimization status between environments"
    )
    parser.add_argument(
        '--library-dir',
        type=Path,
        default=None,
        help='Path to library directory (default: storage/library)'
    )

    args = parser.parse_args()

    # Determine library directory
    if args.library_dir:
        library_dir = args.library_dir.resolve()
    else:
        storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
        library_dir = Path(storage_dir_env).resolve()

        if not library_dir.exists():
            library_dir = project_root / 'storage' / 'library'

    if not library_dir.exists():
        logger.error("Library directory not found: %s", library_dir)
        return

    # Check environment
    env_info = check_environment()
    print_environment_report(env_info)

    # Analyze PDFs
    analysis = analyze_pdf_collection(library_dir)
    print_pdf_analysis_report(analysis)

    # Recommendations
    logger.info("=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)
    logger.info("")

    if not env_info['qpdf_available']:
        logger.info("1. Install qpdf to enable PDF optimization")
        logger.info("")

    if analysis['needs_optimization'] > 0:
        logger.info("2. Fix problematic PDFs by running:")
        logger.info("   python scripts/fix_pdf_xref_issues.py --library-dir %s", library_dir)
        logger.info("")

    if analysis['has_incremental_updates'] > 0:
        logger.info("3. PDFs with incremental updates will cause PDF.js to download entire file")
        logger.info("   Re-linearize them to remove incremental updates")
        logger.info("")

    if analysis['needs_optimization'] == 0 and env_info['qpdf_available']:
        logger.info("✅ All PDFs appear to be optimized!")
        logger.info("   If PDF.js still downloads entire files, check:")
        logger.info("   - Browser cache (try hard refresh)")
        logger.info("   - Network tab in DevTools (check for Range requests)")
        logger.info("   - Server logs for Range request handling")
        logger.info("")


if __name__ == '__main__':
    main()
