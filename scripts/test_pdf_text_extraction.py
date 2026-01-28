"""
Test script to check if PDFs have extractable text content.
This helps diagnose if the cursor issue is due to PDFs not having text layers.
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("Warning: PyMuPDF not installed. Install with: pip install pymupdf")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    print("Warning: pdfplumber not installed. Install with: pip install pdfplumber")

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
    print("Warning: PyPDF2 not installed. Install with: pip install PyPDF2")


def test_pdf_with_pdfplumber(pdf_path: Path):
    """Test PDF text extraction using pdfplumber."""
    if not HAS_PDFPLUMBER:
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_text = ""
            for _, page in enumerate(pdf.pages[:3]):  # Test first 3 pages
                text = page.extract_text()
                if text:
                    total_text += text
            return {
                "has_text": len(total_text.strip()) > 0,
                "text_length": len(total_text),
                "preview": total_text[:200] if total_text else None,
                "num_pages": len(pdf.pages)
            }
    except Exception as e:
        return {"error": str(e)}


def test_pdf_with_pymupdf(pdf_path: Path):
    """Test PDF text extraction using PyMuPDF (fitz) - most reliable."""
    if not HAS_PYMUPDF:
        return None

    try:
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        total_text = ""
        text_blocks_count = 0
        for _, page in enumerate(doc[:3]):  # Test first 3 pages
            text = page.get_text()
            blocks = page.get_text("blocks")
            if text and isinstance(text, str):
                total_text += text
            if blocks:
                text_blocks_count += len([b for b in blocks if len(b[4].strip()) > 0])

        doc.close()
        return {
            "has_text": len(total_text.strip()) > 0,
            "text_length": len(total_text),
            "text_blocks": text_blocks_count,
            "preview": total_text[:200] if total_text else None,
            "num_pages": num_pages
        }
    except Exception as e:
        return {"error": str(e)}


def test_pdf_with_pypdf2(pdf_path: Path):
    """Test PDF text extraction using PyPDF2."""
    if not HAS_PYPDF2:
        return None

    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            total_text = ""
            for _, page in enumerate(reader.pages[:3]):  # Test first 3 pages
                text = page.extract_text()
                if text:
                    total_text += text
            return {
                "has_text": len(total_text.strip()) > 0,
                "text_length": len(total_text),
                "preview": total_text[:200] if total_text else None,
                "num_pages": len(reader.pages)
            }
    except Exception as e:
        return {"error": str(e)}


def main():
    """Main entry point."""
    storage_dir = Path(project_root) / "storage" / "library"

    if not storage_dir.exists():
        print(f"Error: Storage directory not found: {storage_dir}")
        sys.exit(1)

    pdf_files = list(storage_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {storage_dir}")
        sys.exit(0)

    print(f"Found {len(pdf_files)} PDF file(s)")
    print("=" * 80)

    for pdf_path in pdf_files:
        print(f"\nTesting: {pdf_path.name}")
        print("-" * 80)

        # Test with PyMuPDF first (most reliable)
        if HAS_PYMUPDF:
            result = test_pdf_with_pymupdf(pdf_path)
            if result:
                if "error" in result:
                    print(f"PyMuPDF error: {result['error']}")
                else:
                    print(f"PyMuPDF - Has text: {result['has_text']}")
                    print(f"PyMuPDF - Text length: {result['text_length']} chars")
                    print(f"PyMuPDF - Text blocks: {result.get('text_blocks', 0)}")
                    print(f"PyMuPDF - Pages: {result['num_pages']}")
                    if result['preview']:
                        print(f"PyMuPDF - Preview: {result['preview'][:100]}...")
                    if not result['has_text']:
                        print("⚠️  WARNING: This PDF appears to be image-based (scanned/OCRed)")
                        print("   PDF.js may not be able to extract text for selection.")

        # Test with pdfplumber
        if HAS_PDFPLUMBER:
            result = test_pdf_with_pdfplumber(pdf_path)
            if result:
                if "error" in result:
                    print(f"pdfplumber error: {result['error']}")
                else:
                    print(f"pdfplumber - Has text: {result['has_text']}")
                    print(f"pdfplumber - Text length: {result['text_length']} chars")
                    print(f"pdfplumber - Pages: {result['num_pages']}")
                    if result['preview']:
                        print(f"pdfplumber - Preview: {result['preview'][:100]}...")

        # Test with PyPDF2
        if HAS_PYPDF2:
            result = test_pdf_with_pypdf2(pdf_path)
            if result:
                if "error" in result:
                    print(f"PyPDF2 error: {result['error']}")
                else:
                    print(f"PyPDF2 - Has text: {result['has_text']}")
                    print(f"PyPDF2 - Text length: {result['text_length']} chars")
                    print(f"PyPDF2 - Pages: {result['num_pages']}")
                    if result['preview']:
                        print(f"PyPDF2 - Preview: {result['preview'][:100]}...")

        print()


if __name__ == "__main__":
    main()
