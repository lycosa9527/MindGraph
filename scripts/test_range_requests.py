"""
Test if PDF files support Range requests correctly.

Simulates what PDF.js does when loading a PDF:
1. HEAD request to check Accept-Ranges
2. Range request for xref table (beginning of file)
3. Verify server responds with 206 Partial Content

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import argparse
import logging
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_range_request_support(pdf_path: Path, base_url: str, document_id: int) -> None:
    """
    Test Range request support for a PDF file.

    Args:
        pdf_path: Local path to PDF file
        base_url: Base URL of the server (e.g., http://localhost:9527)
        document_id: Document ID for the API endpoint
    """
    if requests is None:
        logger.error("requests library not available. Install with: pip install requests")
        sys.exit(1)

    # Construct API URL
    api_url = f"{base_url}/api/library/documents/{document_id}/file"

    logger.info("=" * 80)
    logger.info("TESTING RANGE REQUEST SUPPORT")
    logger.info("=" * 80)
    logger.info("")
    logger.info("PDF File: %s", pdf_path.name)
    logger.info("API URL: %s", api_url)
    logger.info("")

    file_size = pdf_path.stat().st_size
    logger.info("File Size: %s bytes (~%s MB)", file_size, round(file_size / 1024 / 1024, 2))
    logger.info("")

    # Test 1: HEAD request
    logger.info("Test 1: HEAD Request")
    logger.info("-" * 80)
    try:
        response = requests.head(api_url, timeout=10)
        logger.info("Status: %s %s", response.status_code, response.reason)

        accept_ranges = response.headers.get('Accept-Ranges', 'not set')
        content_length = response.headers.get('Content-Length', 'not set')
        content_type = response.headers.get('Content-Type', 'not set')

        logger.info("Accept-Ranges: %s", accept_ranges)
        logger.info("Content-Length: %s", content_length)
        logger.info("Content-Type: %s", content_type)

        if accept_ranges == 'bytes':
            logger.info("✅ Server supports Range requests")
        else:
            logger.warning("⚠️  Server may not support Range requests: %s", accept_ranges)

        logger.info("")
    except Exception as e:
        logger.error("❌ HEAD request failed: %s", e)
        logger.info("")
        return

    # Test 2: Range request for first 64KB (xref table)
    logger.info("Test 2: Range Request (bytes=0-65535)")
    logger.info("-" * 80)
    logger.info("This simulates what PDF.js does to read xref table")
    logger.info("")

    try:
        headers = {'Range': 'bytes=0-65535'}
        response = requests.get(api_url, headers=headers, timeout=10, stream=True)

        logger.info("Status: %s %s", response.status_code, response.reason)

        if response.status_code == 206:
            logger.info("✅ Server returned 206 Partial Content")

            content_range = response.headers.get('Content-Range', 'not set')
            content_length = response.headers.get('Content-Length', 'not set')

            logger.info("Content-Range: %s", content_range)
            logger.info("Content-Length: %s", content_length)

            # Read the data
            data = response.content
            logger.info("Actual bytes received: %s", len(data))

            if len(data) <= 65536:
                logger.info("✅ Received correct amount of data (expected <= 65536 bytes)")
            else:
                logger.warning("⚠️  Received more data than requested: %s bytes", len(data))

        elif response.status_code == 200:
            logger.error("❌ Server returned 200 OK instead of 206 Partial Content")
            logger.error("   This means Range requests are NOT working!")
            logger.error("   PDF.js will download the entire file.")

            # Check if full file was sent
            data = response.content
            logger.info("Bytes received: %s (full file)", len(data))

        else:
            logger.error("❌ Unexpected status code: %s", response.status_code)

        logger.info("")
    except Exception as e:
        logger.error("❌ Range request failed: %s", e)
        logger.info("")
        return

    # Test 3: Range request for end of file (simulating non-linearized PDF)
    logger.info("Test 3: Range Request (bytes=-16384)")
    logger.info("-" * 80)
    logger.info("This simulates reading from end (for non-linearized PDFs)")
    logger.info("")

    try:
        headers = {'Range': 'bytes=-16384'}  # Last 16KB
        response = requests.get(api_url, headers=headers, timeout=10, stream=True)

        logger.info("Status: %s %s", response.status_code, response.reason)

        if response.status_code == 206:
            logger.info("✅ Server returned 206 Partial Content")

            content_range = response.headers.get('Content-Range', 'not set')
            content_length = response.headers.get('Content-Length', 'not set')

            logger.info("Content-Range: %s", content_range)
            logger.info("Content-Length: %s", content_length)

            data = response.content
            logger.info("Actual bytes received: %s", len(data))

        elif response.status_code == 200:
            logger.error("❌ Server returned 200 OK instead of 206 Partial Content")
        else:
            logger.error("❌ Unexpected status code: %s", response.status_code)

        logger.info("")
    except Exception as e:
        logger.error("❌ Range request failed: %s", e)
        logger.info("")

    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info("")
    logger.info("If all tests show 206 Partial Content:")
    logger.info("  ✅ Server properly supports Range requests")
    logger.info("  ✅ PDF.js should be able to load PDFs efficiently")
    logger.info("")
    logger.info("If any test shows 200 OK:")
    logger.info("  ❌ Range requests are not working")
    logger.info("  ❌ PDF.js will download entire file")
    logger.info("  ❌ Check server configuration and middleware")
    logger.info("")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Range request support for PDF files"
    )
    parser.add_argument(
        '--base-url',
        type=str,
        default='http://localhost:9527',
        help='Base URL of the server (default: http://localhost:9527)'
    )
    parser.add_argument(
        '--document-id',
        type=int,
        required=True,
        help='Document ID to test'
    )
    parser.add_argument(
        '--pdf-path',
        type=Path,
        default=None,
        help='Local path to PDF file (optional, for file size reference)'
    )

    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path and args.document_id:
        # We can't determine filename from document_id, so skip file size check
        pdf_path = None

    test_range_request_support(pdf_path or Path('unknown.pdf'), args.base_url, args.document_id)


if __name__ == '__main__':
    if requests is None:
        logger.error("requests library not available. Install with: pip install requests")
        sys.exit(1)

    main()
