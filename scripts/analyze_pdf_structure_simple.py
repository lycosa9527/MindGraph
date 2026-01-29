"""
Analyze PDF structure directly from storage/library/ to find root cause.

No database required - analyzes PDFs directly from filesystem.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import re
import sys
import traceback
from pathlib import Path

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_trailer_dict(trailer_text: str) -> dict:
    """
    Parse PDF trailer dictionary to extract xref offset and other info.

    Returns:
        Dict with parsed trailer values
    """
    result = {}

    # Look for /Prev (previous xref offset)
    prev_match = re.search(r"/Prev\s+(\d+)", trailer_text)
    if prev_match:
        result["prev_xref_offset"] = int(prev_match.group(1))

    # Look for /XRefStm (xref stream offset)
    xref_stm_match = re.search(r"/XRefStm\s+(\d+)", trailer_text)
    if xref_stm_match:
        result["xref_stream_offset"] = int(xref_stm_match.group(1))

    # Check for /Linearized
    result["is_linearized"] = "/Linearized" in trailer_text

    # Look for startxref offset (the xref table this trailer points to)
    # Format: startxref\n12345\n%%EOF
    startxref_match = re.search(r"startxref\s+(\d+)", trailer_text)
    if startxref_match:
        result["startxref_offset"] = int(startxref_match.group(1))

    return result


def read_xref_table_size(pdf_path: Path, xref_offset: int, trailer_offset: int) -> dict:
    """
    Read the actual xref table and calculate its size.

    Returns:
        Dict with xref table size analysis
    """
    result = {
        "xref_type": "unknown",
        "xref_size_bytes": 0,
        "xref_size_kb": 0,
        "xref_size_mb": 0,
        "xref_start": xref_offset,
        "xref_end": trailer_offset,
        "object_count": 0,
        "has_object_streams": False,
        "object_stream_refs": [],
    }

    try:
        file_size = pdf_path.stat().st_size

        # Calculate xref table size (from xref start to trailer start)
        xref_size = trailer_offset - xref_offset
        result["xref_size_bytes"] = xref_size
        result["xref_size_kb"] = round(xref_size / 1024, 2)
        result["xref_size_mb"] = round(xref_size / 1024 / 1024, 2)
        result["xref_end"] = trailer_offset

        with open(pdf_path, "rb") as f:
            f.seek(xref_offset)
            # Read the xref table
            xref_data = f.read(min(xref_size, 8192))  # Read up to 8KB or actual size
            xref_text = xref_data.decode("latin-1", errors="ignore")

            # Check if it's a traditional xref table or xref stream
            if xref_text.startswith("xref"):
                result["xref_type"] = "table"
                # Parse xref table: xref\n0 N\n<offset> <gen> n\n...
                lines = xref_text.split("\n")
                object_positions = []

                i = 1
                while (
                    i < len(lines) and len(object_positions) < 1000
                ):  # Limit to first 1000
                    line = lines[i].strip()
                    if not line:
                        i += 1
                        continue

                    # Check if this is a subsection header: "0 N" or "123 5"
                    parts = line.split()
                    if len(parts) == 2:
                        try:
                            int(parts[0])  # Validate start_obj
                            count = int(parts[1])
                            result["object_count"] += count

                            # Read object entries for this subsection
                            for j in range(count):
                                if i + 1 + j < len(lines):
                                    entry_line = lines[i + 1 + j].strip()
                                    entry_parts = entry_line.split()
                                    if (
                                        len(entry_parts) >= 3 and entry_parts[2] == "n"
                                    ):  # 'n' = in-use object
                                        try:
                                            obj_offset = int(entry_parts[0])
                                            if 0 < obj_offset < file_size:
                                                object_positions.append(obj_offset)
                                        except (ValueError, IndexError):
                                            pass
                            i += count + 1
                        except (ValueError, IndexError):
                            i += 1
                    else:
                        i += 1

                if object_positions:
                    result["object_positions"] = sorted(object_positions)
                    result["first_object_offset"] = min(object_positions)
                    result["last_object_offset"] = max(object_positions)

                    # Check if objects are scattered (not just at end)
                    first_mb = result["first_object_offset"] / 1024 / 1024
                    last_mb = result["last_object_offset"] / 1024 / 1024
                    file_size_mb = file_size / 1024 / 1024

                    if (
                        first_mb < file_size_mb * 0.5
                    ):  # Objects start before 50% of file
                        result["objects_scattered"] = True
                        result["object_spread_mb"] = round(last_mb - first_mb, 2)
                        result["object_spread_percent"] = round(
                            ((last_mb - first_mb) / file_size_mb * 100), 1
                        )
                    else:
                        result["objects_scattered"] = False

            elif "/Type/XRef" in xref_text or "/W[" in xref_text:
                result["xref_type"] = "stream"
                result["has_object_streams"] = True

                # Check for /Index or object stream references
                if "/Index[" in xref_text or "/W[" in xref_text:
                    result["has_object_streams"] = True
    except Exception as e:
        logger.debug("Error reading xref table: %s", e)
        logger.debug(traceback.format_exc())

    return result


def read_xref_table(pdf_path: Path, xref_offset: int) -> dict:
    """
    Read the actual xref table to see what it contains.

    Returns:
        Dict with xref table analysis
    """
    result = {
        "xref_type": "unknown",
        "object_count": 0,
        "has_object_streams": False,
        "object_stream_refs": [],
        "object_positions": [],
        "first_object_offset": None,
        "last_object_offset": None,
    }

    try:
        file_size = pdf_path.stat().st_size
        with open(pdf_path, "rb") as f:
            f.seek(xref_offset)
            # Read more bytes to parse xref table
            xref_data = f.read(8192)  # Read 8KB
            xref_text = xref_data.decode("latin-1", errors="ignore")

            # Check if it's a traditional xref table or xref stream
            if xref_text.startswith("xref"):
                result["xref_type"] = "table"
                # Parse xref table: xref\n0 N\n<offset> <gen> n\n...
                lines = xref_text.split("\n")
                object_positions = []

                i = 1
                while (
                    i < len(lines) and len(object_positions) < 1000
                ):  # Limit to first 1000
                    line = lines[i].strip()
                    if not line:
                        i += 1
                        continue

                    # Check if this is a subsection header: "0 N" or "123 5"
                    parts = line.split()
                    if len(parts) == 2:
                        try:
                            int(parts[0])  # Validate start_obj
                            count = int(parts[1])
                            result["object_count"] += count

                            # Read object entries for this subsection
                            for j in range(count):
                                if i + 1 + j < len(lines):
                                    entry_line = lines[i + 1 + j].strip()
                                    entry_parts = entry_line.split()
                                    if (
                                        len(entry_parts) >= 3 and entry_parts[2] == "n"
                                    ):  # 'n' = in-use object
                                        try:
                                            obj_offset = int(entry_parts[0])
                                            if 0 < obj_offset < file_size:
                                                object_positions.append(obj_offset)
                                        except (ValueError, IndexError):
                                            pass
                            i += count + 1
                        except (ValueError, IndexError):
                            i += 1
                    else:
                        i += 1

                if object_positions:
                    result["object_positions"] = sorted(object_positions)
                    result["first_object_offset"] = min(object_positions)
                    result["last_object_offset"] = max(object_positions)

                    # Check if objects are scattered (not just at end)
                    first_mb = result["first_object_offset"] / 1024 / 1024
                    last_mb = result["last_object_offset"] / 1024 / 1024
                    file_size_mb = file_size / 1024 / 1024

                    if (
                        first_mb < file_size_mb * 0.5
                    ):  # Objects start before 50% of file
                        result["objects_scattered"] = True
                        result["object_spread_mb"] = round(last_mb - first_mb, 2)
                        result["object_spread_percent"] = round(
                            ((last_mb - first_mb) / file_size_mb * 100), 1
                        )
                    else:
                        result["objects_scattered"] = False

            elif "/Type/XRef" in xref_text or "/W[" in xref_text:
                result["xref_type"] = "stream"
                result["has_object_streams"] = True

                # Check for /Index or object stream references
                if "/Index[" in xref_text or "/W[" in xref_text:
                    result["has_object_streams"] = True
    except Exception as e:
        logger.debug("Error reading xref table: %s", e)

    return result


def read_trailer_at_offset(pdf_path: Path, trailer_offset: int) -> dict:
    """
    Read trailer dictionary at specific offset.

    Returns:
        Dict with trailer info
    """
    result = {
        "xref_offset": None,
        "prev_xref_offset": None,
        "is_linearized": False,
        "trailer_offset": trailer_offset,
    }

    try:
        with open(pdf_path, "rb") as f:
            # Read around trailer position
            f.seek(max(0, trailer_offset - 500))
            trailer_data = f.read(2000)
            trailer_text = trailer_data.decode("latin-1", errors="ignore")

            # Parse trailer dictionary
            trailer_dict = parse_trailer_dict(trailer_text)

            result["is_linearized"] = trailer_dict.get("is_linearized", False)
            result["prev_xref_offset"] = trailer_dict.get("prev_xref_offset")
            result["xref_offset"] = trailer_dict.get("startxref_offset")

    except Exception as e:
        logger.debug("Error reading trailer at offset %d: %s", trailer_offset, e)

    return result


def trace_xref_chain(pdf_path: Path) -> list:
    """
    Trace the complete xref chain from latest to oldest (incremental updates).

    Returns:
        List of xref info dicts, from latest to oldest
    """
    xref_chain = []
    file_size = pdf_path.stat().st_size

    # Find the last trailer (latest xref)
    with open(pdf_path, "rb") as f:
        read_size = min(16384, file_size)  # Read last 16KB
        f.seek(max(0, file_size - read_size))
        tail = f.read()

        # Find all startxref positions
        startxref_positions = []
        pos = 0
        while True:
            pos = tail.find(b"startxref", pos)
            if pos == -1:
                break
            # Calculate actual file offset
            file_offset = file_size - read_size + pos
            startxref_positions.append(file_offset)
            pos += 9

        if not startxref_positions:
            return xref_chain

        # Start from the last startxref
        current_trailer_offset = startxref_positions[-1]

    # Trace the chain backwards
    visited_offsets = set()
    while current_trailer_offset and current_trailer_offset not in visited_offsets:
        visited_offsets.add(current_trailer_offset)

        trailer_info = read_trailer_at_offset(pdf_path, current_trailer_offset)

        if trailer_info.get("xref_offset"):
            xref_info = {
                "trailer_offset": current_trailer_offset,
                "xref_offset": trailer_info["xref_offset"],
                "prev_xref_offset": trailer_info.get("prev_xref_offset"),
                "is_linearized": trailer_info.get("is_linearized", False),
            }
            xref_chain.append(xref_info)

            # Move to previous xref if exists
            if trailer_info.get("prev_xref_offset"):
                current_trailer_offset = trailer_info["prev_xref_offset"]
            else:
                break
        else:
            break

    return xref_chain


def read_pdf_trailer(pdf_path: Path) -> dict:
    """
    Read PDF trailer to find xref location and check linearization.

    Returns:
        Dict with trailer info including actual xref offset
    """
    result = {
        "is_linearized": False,
        "xref_location": "unknown",
        "xref_offset": None,
        "xref_offset_mb": None,
        "file_size": 0,
        "has_prev_xref": False,
        "trailer_found": False,
        "trailer_offset": None,
    }

    try:
        file_size = pdf_path.stat().st_size
        result["file_size"] = file_size

        with open(pdf_path, "rb") as f:
            # Read last 8192 bytes (trailer is usually at end)
            read_size = min(8192, file_size)
            f.seek(max(0, file_size - read_size))
            tail = f.read()

            # Find trailer - look for "trailer" keyword
            trailer_pos_in_tail = tail.rfind(b"trailer")
            if trailer_pos_in_tail == -1:
                return result

            # Calculate actual trailer position in file
            trailer_offset = file_size - read_size + trailer_pos_in_tail
            result["trailer_offset"] = trailer_offset
            result["trailer_found"] = True

            # Read more context around trailer if needed
            trailer_section_start = max(0, trailer_pos_in_tail - 100)
            trailer_section = tail[trailer_section_start:].decode(
                "latin-1", errors="ignore"
            )

            # Parse trailer dictionary
            trailer_dict = parse_trailer_dict(trailer_section)

            result["is_linearized"] = trailer_dict.get("is_linearized", False)
            result["has_prev_xref"] = "prev_xref_offset" in trailer_dict

            # Find startxref offset (points to the xref table)
            # Look for "startxref\n<number>\n%%EOF" pattern
            startxref_pos = tail.rfind(b"startxref")
            if startxref_pos != -1:
                # Read the number after startxref
                startxref_section = tail[startxref_pos : startxref_pos + 100].decode(
                    "latin-1", errors="ignore"
                )
                startxref_match = re.search(r"startxref\s+(\d+)", startxref_section)
                if startxref_match:
                    xref_offset = int(startxref_match.group(1))
                    result["xref_offset"] = xref_offset
                    result["xref_offset_mb"] = round(xref_offset / 1024 / 1024, 2)

                    # Determine location
                    xref_position_ratio = (
                        xref_offset / file_size if file_size > 0 else 0
                    )

                    if xref_position_ratio < 0.1:
                        result["xref_location"] = "beginning"
                    elif xref_position_ratio > 0.9:
                        result["xref_location"] = "end"
                    else:
                        percent = round(xref_position_ratio * 100, 1)
                        result["xref_location"] = f"middle ({percent}%)"

                    # Verify by checking if it matches linearization status
                    if result["is_linearized"] and xref_position_ratio > 0.1:
                        result["xref_location"] = "end (unexpected for linearized PDF!)"
                    elif not result["is_linearized"] and xref_position_ratio < 0.1:
                        result["xref_location"] = (
                            "beginning (unexpected for non-linearized PDF!)"
                        )

            # Check for xref stream
            result["has_xref_stream"] = "xref_stream_offset" in trailer_dict

            # If we found xref offset, read the xref table itself and calculate size
            if result.get("xref_offset") and result.get("trailer_offset"):
                xref_info = read_xref_table_size(
                    pdf_path, result["xref_offset"], result["trailer_offset"]
                )
                result["xref_type"] = xref_info.get("xref_type", "unknown")
                result["xref_size_bytes"] = xref_info.get("xref_size_bytes", 0)
                result["xref_size_kb"] = xref_info.get("xref_size_kb", 0)
                result["xref_size_mb"] = xref_info.get("xref_size_mb", 0)
                result["xref_object_count"] = xref_info.get("object_count", 0)
                result["xref_has_object_streams"] = xref_info.get(
                    "has_object_streams", False
                )
                result["objects_scattered"] = xref_info.get("objects_scattered", False)
                result["object_spread_mb"] = xref_info.get("object_spread_mb")
                result["object_spread_percent"] = xref_info.get("object_spread_percent")
                result["first_object_offset"] = xref_info.get("first_object_offset")
                result["last_object_offset"] = xref_info.get("last_object_offset")

            # Trace complete xref chain for incremental updates
            xref_chain = trace_xref_chain(pdf_path)
            result["xref_chain"] = xref_chain
            result["incremental_updates_count"] = len(xref_chain)

            # Calculate how much data PDF.js needs to read
            if xref_chain:
                # Find the oldest xref offset
                oldest_xref = min(
                    xref["xref_offset"]
                    for xref in xref_chain
                    if xref.get("xref_offset")
                )
                if oldest_xref:
                    bytes_from_end = file_size - oldest_xref
                    result["bytes_to_read_from_end"] = bytes_from_end
                    result["mb_to_read_from_end"] = round(
                        bytes_from_end / 1024 / 1024, 2
                    )
                    result["percent_to_read"] = (
                        round((bytes_from_end / file_size * 100), 1)
                        if file_size > 0
                        else 0
                    )

    except Exception as e:
        logger.error("Error reading PDF trailer: %s", e)
        logger.debug(traceback.format_exc())

    return result


def analyze_pdf_structure_detailed(pdf_path: Path) -> dict:
    """
    Detailed PDF structure analysis.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with detailed analysis results
    """
    result = {
        "file_name": pdf_path.name,
        "file_path": str(pdf_path),
        "file_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "file_size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2)
        if pdf_path.exists()
        else 0,
        "is_linearized": False,
        "xref_location": "unknown",
        "needs_end_read": False,
        "analysis_error": None,
        "page_count": 0,
    }

    if not pdf_path.exists():
        result["analysis_error"] = "File not found"
        return result

    # Read PDF trailer
    trailer_info = read_pdf_trailer(pdf_path)
    if trailer_info.get("trailer_found"):
        result["is_linearized"] = trailer_info.get("is_linearized", False)
        result["xref_location"] = trailer_info.get("xref_location", "unknown")
        result["xref_offset"] = trailer_info.get("xref_offset")
        result["xref_offset_mb"] = trailer_info.get("xref_offset_mb")
        result["trailer_offset"] = trailer_info.get("trailer_offset")
        result["has_prev_xref"] = trailer_info.get("has_prev_xref", False)
        result["has_xref_stream"] = trailer_info.get("has_xref_stream", False)
        result["xref_type"] = trailer_info.get("xref_type", "unknown")
        result["xref_size_bytes"] = trailer_info.get("xref_size_bytes", 0)
        result["xref_size_kb"] = trailer_info.get("xref_size_kb", 0)
        result["xref_size_mb"] = trailer_info.get("xref_size_mb", 0)
        result["xref_object_count"] = trailer_info.get("xref_object_count", 0)
        result["xref_has_object_streams"] = trailer_info.get(
            "xref_has_object_streams", False
        )
        result["xref_chain"] = trailer_info.get("xref_chain", [])
        result["incremental_updates_count"] = trailer_info.get(
            "incremental_updates_count", 1
        )
        result["bytes_to_read_from_end"] = trailer_info.get("bytes_to_read_from_end")
        result["mb_to_read_from_end"] = trailer_info.get("mb_to_read_from_end")
        result["percent_to_read"] = trailer_info.get("percent_to_read")
        result["objects_scattered"] = trailer_info.get("objects_scattered", False)
        result["needs_end_read"] = not result["is_linearized"]
    else:
        result["analysis_error"] = "Could not find PDF trailer"

    # Try PyPDF2 for page count
    if PyPDF2 is None:
        result["analysis_error"] = (
            "PyPDF2 not available - install with: pip install PyPDF2"
        )
    else:
        try:
            with open(pdf_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                result["page_count"] = len(pdf_reader.pages)
        except Exception as e:
            if not result.get("analysis_error"):
                result["analysis_error"] = f"PyPDF2 error: {e}"

    return result


def analyze_library_pdfs_detailed() -> None:
    """
    Analyze all PDFs in storage/library/ to find root cause.
    """
    # Find storage/library directory
    storage_dir_env = os.getenv("LIBRARY_STORAGE_DIR", "./storage/library")
    storage_dir = Path(storage_dir_env).resolve()

    if not storage_dir.exists():
        # Try relative to script
        storage_dir = Path(__file__).parent.parent / "storage" / "library"

    if not storage_dir.exists():
        logger.error("Library directory not found: %s", storage_dir)
        logger.info("Please ensure PDFs are in storage/library/ directory")
        return

    # Find all PDF files
    pdf_files = list(storage_dir.glob("*.pdf"))

    if not pdf_files:
        logger.info("No PDF files found in %s", storage_dir)
        return

    logger.info(
        "Found %d PDF file(s) in %s", len(pdf_files), storage_dir
    )
    logger.info("=" * 80)
    logger.info(
        "PDF STRUCTURE ANALYSIS - Finding Root Cause of Large Metadata Downloads"
    )
    logger.info("=" * 80)
    logger.info("")

    analyses = []

    for pdf_path in sorted(pdf_files):
        analysis = analyze_pdf_structure_detailed(pdf_path)
        analyses.append(analysis)

    # Print detailed analysis
    logger.info("DETAILED PDF STRUCTURE ANALYSIS:")
    logger.info("-" * 80)

    for analysis in analyses:
        if analysis.get("analysis_error"):
            logger.warning(
                "⚠️  %s: %s", analysis["file_name"], analysis["analysis_error"]
            )
            logger.info("")
            continue

        logger.info("📄 %s", analysis["file_name"])
        logger.info(
            "   Size: %s MB (%s bytes)",
            analysis["file_size_mb"],
            format(analysis["file_size"], ","),
        )
        logger.info("   Pages: %s", analysis.get("page_count", "unknown"))
        logger.info("")
        logger.info("   📊 PDF STRUCTURE:")
        linearized_status = "✅ YES" if analysis["is_linearized"] else "❌ NO"
        logger.info("      Linearized: %s", linearized_status)

        # Show actual xref offset if found
        if analysis.get("xref_offset") is not None:
            xref_offset = analysis["xref_offset"]
            xref_mb = analysis.get("xref_offset_mb", 0)
            file_size = analysis["file_size"]
            xref_percent = (
                round((xref_offset / file_size * 100), 1) if file_size > 0 else 0
            )
            logger.info(
                "      XRef Offset: %s bytes (%s MB) - %s%% into file",
                format(xref_offset, ","),
                xref_mb,
                xref_percent,
            )
            logger.info("      XRef Location: %s", analysis["xref_location"])
        else:
            logger.info(
                "      XRef Location: %s (offset not found)", analysis["xref_location"]
            )

        if analysis.get("trailer_offset") is not None:
            trailer_offset = analysis["trailer_offset"]
            trailer_mb = round(trailer_offset / 1024 / 1024, 2)
            trailer_percent = (
                round((trailer_offset / analysis["file_size"] * 100), 1)
                if analysis["file_size"] > 0
                else 0
            )
            logger.info(
                "      Trailer Offset: %s bytes (%s MB) - %s%% into file",
                format(trailer_offset, ","),
                trailer_mb,
                trailer_percent,
            )

        needs_end_read_status = "✅ YES" if analysis["needs_end_read"] else "❌ NO"
        logger.info("      Needs End Read: %s", needs_end_read_status)
        has_prev_xref = "Yes" if analysis.get("has_prev_xref") else "No"
        logger.info("      Has Previous XRef: %s", has_prev_xref)
        has_xref_stream = "Yes" if analysis.get("has_xref_stream") else "No"
        logger.info("      Has XRef Stream: %s", has_xref_stream)
        if analysis.get("xref_type"):
            logger.info("      XRef Type: %s", analysis.get("xref_type"))
        if analysis.get("xref_size_bytes", 0) > 0:
            xref_size_kb = analysis.get("xref_size_kb", 0)
            xref_size_mb = analysis.get("xref_size_mb", 0)
            xref_size_bytes = analysis.get("xref_size_bytes", 0)
            logger.info(
                "      📏 XRef Table Size: %s bytes (%s KB / %s MB)",
                format(xref_size_bytes, ","),
                xref_size_kb,
                xref_size_mb,
            )
            logger.info(
                "      📏 XRef Location: bytes %s to %s",
                format(analysis.get("xref_offset", 0), ","),
                format(analysis.get("trailer_offset", 0), ","),
            )
        if analysis.get("xref_object_count", 0) > 0:
            logger.info(
                "      XRef Object Count: %s", analysis.get("xref_object_count")
            )
        if analysis.get("xref_has_object_streams"):
            logger.info(
                "      ⚠️  Has Object Streams: Yes (may require reading more data)"
            )

        # Show object distribution
        if analysis.get("objects_scattered"):
            spread_mb = analysis.get("object_spread_mb", 0)
            spread_percent = analysis.get("object_spread_percent", 0)
            first_mb = round(analysis.get("first_object_offset", 0) / 1024 / 1024, 2)
            last_mb = round(analysis.get("last_object_offset", 0) / 1024 / 1024, 2)
            logger.info("      ⚠️  Objects Scattered: Yes")
            logger.info("         First object: %s MB, Last: %s MB", first_mb, last_mb)
            logger.info(
                "         Spread: %s MB (%s%% of file)", spread_mb, spread_percent
            )
            logger.info("         ⚠️  PDF.js may need to read objects throughout file")

        # Show incremental updates info
        incremental_count = analysis.get("incremental_updates_count", 1)
        if incremental_count > 1:
            logger.info("")
            logger.info("   🔗 INCREMENTAL UPDATES DETECTED:")
            logger.info("      Total XRef Tables: %d", incremental_count)
            logger.info(
                "      ⚠️  PDF has been edited %d time(s)", incremental_count - 1
            )
            logger.info("      ⚠️  Each update added new XRef table at end")

            xref_chain = analysis.get("xref_chain", [])
            if xref_chain:
                logger.info("      XRef Chain (latest → oldest):")
                for i, xref in enumerate(xref_chain[:5]):  # Show first 5
                    xref_offset = xref.get("xref_offset", 0)
                    xref_mb = round(xref_offset / 1024 / 1024, 2) if xref_offset else 0
                    has_prev = "Yes" if xref.get("prev_xref_offset") else "No"
                    logger.info(
                        "         %d. XRef at %s bytes (%s MB) - Prev: %s",
                        i + 1,
                        format(xref_offset, ","),
                        xref_mb,
                        has_prev,
                    )
                if len(xref_chain) > 5:
                    logger.info("         ... and %d more", len(xref_chain) - 5)

            if analysis.get("mb_to_read_from_end"):
                mb_to_read = analysis["mb_to_read_from_end"]
                percent_to_read = analysis.get("percent_to_read", 0)
                logger.info("")
                logger.info("      📊 PDF.js MUST READ:")
                logger.info(
                    "         From oldest XRef to end: %.2f MB (%s%% of file)",
                    mb_to_read,
                    percent_to_read,
                )
                logger.info("         ⚠️  This explains large metadata download!")

        logger.info("")

        # Root cause analysis
        file_size_mb = analysis["file_size_mb"]

        if not analysis["is_linearized"]:
            logger.info("   🔍 ROOT CAUSE ANALYSIS:")
            logger.info("      ❌ PDF is NON-LINEARIZED")

            xref_offset = analysis.get("xref_offset")
            if xref_offset is not None:
                xref_mb = analysis.get("xref_offset_mb", 0)
                file_size = analysis["file_size"]
                bytes_from_end = file_size - xref_offset
                mb_from_end = round(bytes_from_end / 1024 / 1024, 2)
                percent_from_end = (
                    round((bytes_from_end / file_size * 100), 1) if file_size > 0 else 0
                )

                logger.info(
                    "      ✅ VERIFIED: XRef table is at offset %s bytes (%s MB)",
                    format(xref_offset, ","),
                    xref_mb,
                )
                logger.info(
                    "      ✅ VERIFIED: Latest XRef is %s bytes (%s MB) from END",
                    format(bytes_from_end, ","),
                    mb_from_end,
                )
                logger.info(
                    "      ✅ VERIFIED: Latest XRef is at %s%% into file",
                    percent_from_end,
                )

                # Show actual xref table size
                xref_size_mb = analysis.get("xref_size_mb", 0)
                xref_size_kb = analysis.get("xref_size_kb", 0)
                if xref_size_mb > 0:
                    logger.info("")
                    logger.info("      📏 ACTUAL XREF TABLE SIZE:")
                    logger.info(
                        "      ✅ XRef table itself: %s KB (%s MB)",
                        xref_size_kb,
                        xref_size_mb,
                    )
                    logger.info(
                        "      ✅ This is what PDF.js SHOULD download to read xref"
                    )
                    logger.info(
                        "      ⚠️  If PDF.js downloaded ~%s MB, it downloaded ENTIRE FILE",
                        file_size_mb,
                    )
                    logger.info("      ⚠️  Expected download: ~%s KB", xref_size_kb)
                    logger.info("      ⚠️  Actual download: ~%s MB", file_size_mb)
                    diff_mb = file_size_mb - xref_size_mb
                    logger.info("      ⚠️  Difference: ~%.2f MB (unnecessary!)", diff_mb)

                # Check for incremental updates
                incremental_count = analysis.get("incremental_updates_count", 1)
                if incremental_count > 1:
                    mb_to_read = analysis.get("mb_to_read_from_end", mb_from_end)
                    percent_to_read = analysis.get("percent_to_read", percent_from_end)
                    logger.info("")
                    logger.info("      🔗 INCREMENTAL UPDATES ROOT CAUSE:")
                    logger.info(
                        "      ⚠️  PDF has %d XRef tables (incremental updates)",
                        incremental_count,
                    )
                    logger.info("      ⚠️  PDF.js MUST read from OLDEST XRef to end")
                    logger.info(
                        "      ✅ VERIFIED: PDF.js must read %.2f MB (%s%% of file)",
                        mb_to_read,
                        percent_to_read,
                    )
                    logger.info(
                        "      💡 This is WHY metadata download is ~%.1f MB!",
                        mb_to_read,
                    )
                    logger.info(
                        "      💡 Each edit added new XRef table at end of file"
                    )
                else:
                    logger.info("      ⚠️  PDF.js MUST read from end to locate pages")

                    # Check if there are object streams that might require more reading
                    if analysis.get("xref_has_object_streams"):
                        logger.info(
                            "      ⚠️  WARNING: PDF uses Object Streams (compressed objects)"
                        )
                        logger.info(
                            "      ⚠️  PDF.js may need to read object streams scattered in file"
                        )
                        logger.info(
                            "      ⚠️  This could explain large downloads even with xref at end"
                        )

                    # More accurate estimate based on actual xref position
                    if mb_from_end > 10:
                        logger.info(
                            "      ⚠️  PDF.js needs to read at least %.1f MB from end",
                            mb_from_end,
                        )
                        logger.info(
                            "      ⚠️  May need more if xref streams/objects are referenced"
                        )
                    else:
                        logger.info(
                            "      ⚠️  PDF.js needs to read ~%.1f MB from end",
                            mb_from_end,
                        )
                    # Check if objects are scattered
                    if analysis.get("objects_scattered"):
                        spread_mb = analysis.get("object_spread_mb", 0)
                        logger.info("")
                        logger.info("      🔍 OBJECT DISTRIBUTION ANALYSIS:")
                        logger.info(
                            "      ⚠️  PDF objects are SCATTERED throughout file"
                        )
                        logger.info(
                            "      ⚠️  Objects span %s MB across the file", spread_mb
                        )
                        logger.info(
                            "      ⚠️  PDF.js may need to read objects to understand structure"
                        )
                        logger.info("      💡 This could explain large downloads!")
                    else:
                        logger.info(
                            "      ⚠️  BUT: If seeing ~%s MB downloads, PDF.js may be:",
                            file_size_mb,
                        )
                        logger.info(
                            "          - Reading object streams referenced by xref"
                        )
                        logger.info(
                            "          - Following object references throughout file"
                        )
                        logger.info(
                            "          - Not respecting disableAutoFetch properly"
                        )
                        logger.info(
                            "          - Downloading entire file despite disableAutoFetch"
                        )
            else:
                logger.info(
                    "      ⚠️  XRef table location: %s (%s MB file)",
                    analysis["xref_location"],
                    file_size_mb,
                )
                logger.info("      ⚠️  PDF.js MUST read from end to locate pages")

            logger.info(
                "      💡 This explains the large 'metadata' download (%s MB file)",
                file_size_mb,
            )
            logger.info("      💡 Solution: Linearize PDF to move xref to beginning")
            logger.info("")
        else:
            logger.info("   ✅ PDF is LINEARIZED - xref at beginning")
            logger.info("      Expected metadata size: ~5-50 KB")
            logger.info(
                "      If you see large downloads, check Network tab for actual requests"
            )
            logger.info("")

    # Summary and recommendations
    logger.info("=" * 80)
    logger.info("SUMMARY & RECOMMENDATIONS:")
    logger.info("=" * 80)

    valid_analyses = [a for a in analyses if not a.get("analysis_error")]
    linearized_count = sum(1 for a in valid_analyses if a.get("is_linearized"))
    non_linearized_count = len(valid_analyses) - linearized_count

    logger.info("Total PDFs analyzed: %d", len(valid_analyses))
    logger.info("  ✅ Linearized PDFs: %d", linearized_count)
    logger.info("  ❌ Non-linearized PDFs: %d", non_linearized_count)
    logger.info("")

    if non_linearized_count > 0:
        logger.info("⚠️  ROOT CAUSE IDENTIFIED:")
        logger.info("   Non-linearized PDFs have xref table at END of file")
        logger.info("   PDF.js must read from end to locate pages")
        logger.info("   This causes large initial downloads")
        logger.info("")
        logger.info("💡 SOLUTIONS:")
        logger.info("   1. Linearize PDFs using:")
        logger.info("      qpdf --linearize input.pdf output.pdf")
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
