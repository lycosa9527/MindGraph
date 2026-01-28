"""
Extract first page of PDFs as cover images for library.

Author: lycosa9527
Made by: MindSpring Team

Extracts the first page of each PDF in storage/library/ and saves as cover images.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import os
import sys
import io
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try PyMuPDF first (pure Python, no external dependencies)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Fallback to pdf2image (requires poppler)
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Error: Pillow not available. Install with: pip install Pillow")
    sys.exit(1)

if not PYMUPDF_AVAILABLE and not PDF2IMAGE_AVAILABLE:
    print("Error: No PDF rendering library available.")
    print("Install PyMuPDF (recommended): pip install PyMuPDF")
    print("Or install pdf2image + poppler:")
    print("  pip install pdf2image")
    print("  Windows: Download poppler from https://github.com/oschwartz10612/poppler-windows/releases")
    print("  macOS: brew install poppler")
    print("  Linux: apt-get install poppler-utils")
    sys.exit(1)


def extract_pdf_cover_pymupdf(pdf_path: Path, output_path: Path, dpi: int = 200) -> bool:
    """
    Extract first page of PDF as cover image using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            print(f"Warning: No pages found in {pdf_path.name}")
            doc.close()
            return False

        # Get first page
        page = doc[0]

        # Calculate zoom factor for desired DPI (default PDF is 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        cover_image = Image.open(io.BytesIO(img_data))

        # Resize if too large (max width 800px, maintain aspect ratio)
        max_width = 800
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save as PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        print(f"  ✓ Extracted cover: {output_path.name} ({cover_image.width}x{cover_image.height}px, {file_size_kb:.1f} KB)")

        doc.close()
        return True

    except Exception as e:
        print(f"  ✗ Error extracting cover from {pdf_path.name}: {e}")
        return False


def extract_pdf_cover_pdf2image(pdf_path: Path, output_path: Path, dpi: int = 200) -> bool:
    """
    Extract first page of PDF as cover image using pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert first page to image
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=1,
            last_page=1,
            fmt='png'
        )

        if not images:
            print(f"Warning: No pages found in {pdf_path.name}")
            return False

        # Get first page image
        cover_image = images[0]

        # Resize if too large (max width 800px, maintain aspect ratio)
        max_width = 800
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save as PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        print(f"  ✓ Extracted cover: {output_path.name} ({cover_image.width}x{cover_image.height}px, {file_size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"  ✗ Error extracting cover from {pdf_path.name}: {e}")
        return False


def extract_pdf_cover(pdf_path: Path, output_path: Path, dpi: int = 200) -> bool:
    """
    Extract first page of PDF as cover image.

    Uses PyMuPDF if available, falls back to pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    if not PIL_AVAILABLE:
        print(f"Error: Cannot extract cover for {pdf_path.name} - Pillow not available")
        return False

    if PYMUPDF_AVAILABLE:
        return extract_pdf_cover_pymupdf(pdf_path, output_path, dpi)
    elif PDF2IMAGE_AVAILABLE:
        return extract_pdf_cover_pdf2image(pdf_path, output_path, dpi)
    else:
        print(f"Error: Cannot extract cover for {pdf_path.name} - no PDF rendering library available")
        return False


def extract_all_covers(library_dir: Optional[Path] = None, covers_dir: Optional[Path] = None) -> None:
    """
    Extract covers for all PDFs in library directory.

    Args:
        library_dir: Directory containing PDFs (default: storage/library)
        covers_dir: Directory to save covers (default: storage/library/covers)
    """
    if library_dir is None:
        library_dir = project_root / "storage" / "library"
    if covers_dir is None:
        covers_dir = library_dir / "covers"

    if not library_dir.exists():
        print(f"Error: Library directory not found: {library_dir}")
        return

    # Find all PDF files
    pdf_files = list(library_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {library_dir}")
        return

    print(f"Found {len(pdf_files)} PDF file(s) in {library_dir}")
    print(f"Extracting covers to {covers_dir}\n")

    success_count = 0
    for pdf_path in pdf_files:
        # Generate cover filename: {pdf_name_without_ext}_cover.png
        pdf_name = pdf_path.stem
        cover_filename = f"{pdf_name}_cover.png"
        cover_path = covers_dir / cover_filename

        print(f"Processing: {pdf_path.name}")
        if extract_pdf_cover(pdf_path, cover_path):
            success_count += 1
        print()

    print(f"Completed: {success_count}/{len(pdf_files)} covers extracted successfully")

    if success_count < len(pdf_files):
        if not PYMUPDF_AVAILABLE and not PDF2IMAGE_AVAILABLE:
            print("\nTo extract covers, please install PyMuPDF (recommended):")
            print("  pip install PyMuPDF")
            print("\nOr install pdf2image + poppler:")
            print("  pip install pdf2image")
            print("  Windows: Download poppler from https://github.com/oschwartz10612/poppler-windows/releases")
            print("  macOS: brew install poppler")
            print("  Linux: apt-get install poppler-utils")


if __name__ == "__main__":
    extract_all_covers()
