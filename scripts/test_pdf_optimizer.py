"""
Test PDF Optimizer Module

Quick test script to verify PDF optimizer functionality.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import importlib.util
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import project modules after path setup
_pdf_optimizer_module = importlib.import_module("services.library.pdf_optimizer")
analyze_pdf_structure = _pdf_optimizer_module.analyze_pdf_structure
should_optimize_pdf = _pdf_optimizer_module.should_optimize_pdf
check_qpdf_available = _pdf_optimizer_module.check_qpdf_available


def test_pdf_analysis(pdf_path: Path) -> None:
    """Test PDF structure analysis."""
    print(f"\n{'='*80}")
    print(f"Analyzing: {pdf_path.name}")
    print('='*80)

    info = analyze_pdf_structure(pdf_path)

    if info.analysis_error:
        print(f"❌ Error: {info.analysis_error}")
        return

    print(f"File Size: {info.file_size:,} bytes ({info.file_size / 1024 / 1024:.2f} MB)")
    print(f"Linearized: {'✅ YES' if info.is_linearized else '❌ NO'}")
    print(f"XRef Location: {info.xref_location}")
    print(f"XRef Offset: {info.xref_offset:,} bytes" if info.xref_offset else "XRef Offset: Not found")
    print(f"XRef Size: {info.xref_size_kb} KB ({info.xref_size_bytes:,} bytes)")
    print(f"Needs Optimization: {'✅ YES' if info.needs_optimization else '❌ NO'}")

    should_opt, reason, _ = should_optimize_pdf(pdf_path)
    if should_opt:
        print(f"\n💡 Optimization Recommended: {reason}")
    else:
        print(f"\n✅ No optimization needed: {reason or 'PDF is already optimized'}")


def main() -> None:
    """Main test function."""
    # Find storage/library directory
    storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
    storage_dir = Path(storage_dir_env).resolve()

    if not storage_dir.exists():
        storage_dir = Path(__file__).parent.parent / 'storage' / 'library'

    if not storage_dir.exists():
        print(f"Error: Library directory not found: {storage_dir}")
        return

    # Find PDF files
    pdf_files = list(storage_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {storage_dir}")
        return

    print(f"Found {len(pdf_files)} PDF file(s)")

    # Check tool availability
    qpdf_available = check_qpdf_available()
    print(f"\nqpdf available: {'✅ YES' if qpdf_available else '❌ NO'}")

    pypdf2_spec = importlib.util.find_spec("PyPDF2")
    pypdf2_available = pypdf2_spec is not None
    print(f"PyPDF2 available: {'✅ YES' if pypdf2_available else '❌ NO'}")

    # Analyze each PDF
    for pdf_path in sorted(pdf_files)[:3]:  # Test first 3 PDFs
        test_pdf_analysis(pdf_path)

    print(f"\n{'='*80}")
    print("Test Complete")
    print('='*80)
    print("\nTo optimize PDFs, use:")
    print("  python scripts/library_import.py import --optimize-pdfs")


if __name__ == "__main__":
    main()
