"""
TOC (Table of Contents) detection using hybrid approach.

Combines:
1. PDF outline extraction (if available)
2. Heading pattern detection
3. LLM inference (for complex cases)
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TOCDetector:
    """
    Hybrid TOC detection combining multiple methods.

    Priority:
    1. PDF outline (most reliable)
    2. Heading patterns (fast, reliable)
    3. LLM inference (for complex/unclear cases)
    """

    def __init__(self):
        """Initialize TOC detector."""
        self.heading_pattern = re.compile(
            r'^(#{1,6}|\d+(?:\.\d+)*)\s+(.+)$',
            re.MULTILINE
        )

    def detect_from_pdf_outline(
        self,
        pdf_outline: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Extract TOC from PDF outline.

        Args:
            pdf_outline: PDF outline structure (if available)

        Returns:
            List of TOC entries with 'title', 'level', 'start_page', 'end_page'
        """
        if not pdf_outline:
            return []

        toc = []
        for entry in pdf_outline:
            toc.append({
                "title": entry.get("title", ""),
                "level": entry.get("level", 1),
                "start_page": entry.get("page", 0),
                "end_page": entry.get("end_page"),
                "start_char": entry.get("start_char"),
                "end_char": entry.get("end_char"),
                "source": "pdf_outline"
            })

        return toc

    def detect_from_headings(
        self,
        text: str,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect TOC from heading patterns.

        Looks for:
        - Markdown headings: # ## ###
        - Numbered headings: 1. 1.1 1.1.1

        Args:
            text: Text to analyze
            max_pages: Limit analysis to first N pages (for sampling)

        Returns:
            List of TOC entries
        """
        # Limit text if sampling
        if max_pages:
            # Approximate: 2000 chars per page
            max_chars = max_pages * 2000
            text = text[:max_chars]

        headings = []
        for match in self.heading_pattern.finditer(text):
            marker = match.group(1)
            title = match.group(2).strip()

            # Determine level
            if marker.startswith('#'):
                level = len(marker)
            else:
                level = marker.count('.') + 1

            headings.append({
                "title": title,
                "level": level,
                "position": match.start(),
                "number": marker if not marker.startswith('#') else None,
                "source": "heading_pattern"
            })

        # Estimate page numbers (rough approximation)
        chars_per_page = 2000
        for heading in headings:
            heading["start_page"] = heading["position"] // chars_per_page + 1

        return headings

    def detect_hybrid(
        self,
        text: str,
        pdf_outline: Optional[List[Dict[str, Any]]] = None,
        max_pages: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """
        Hybrid TOC detection combining multiple methods.

        Priority:
        1. PDF outline (if available)
        2. Heading patterns
        3. Fallback to LLM (not implemented here, done by agent)

        Args:
            text: Text to analyze
            pdf_outline: PDF outline structure (if available)
            max_pages: Limit analysis to first N pages (for sampling)

        Returns:
            List of TOC entries
        """
        # Try PDF outline first
        if pdf_outline:
            toc = self.detect_from_pdf_outline(pdf_outline)
            if toc:
                toc_count = len(toc)
                logger.info("Detected %s TOC entries from PDF outline", toc_count)
                return toc

        # Fallback to heading patterns
        toc = self.detect_from_headings(text, max_pages=max_pages)
        if toc:
            toc_count = len(toc)
            logger.info("Detected %s TOC entries from heading patterns", toc_count)
            return toc

        logger.warning("No TOC detected using pattern matching")
        return []

    def apply_toc_boundaries(
        self,
        document: str,
        toc: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply TOC boundaries to extract sections.

        Args:
            document: Full document text
            toc: TOC entries with positions

        Returns:
            List of sections with text and boundaries
        """
        sections = []

        for i, toc_entry in enumerate(toc):
            start_pos = toc_entry.get("start_char") or toc_entry.get("position", 0)

            # Determine end position
            if i + 1 < len(toc):
                end_pos = toc[i + 1].get("start_char") or toc[i + 1].get("position", len(document))
            else:
                end_pos = len(document)

            section_text = document[start_pos:end_pos]

            sections.append({
                "title": toc_entry["title"],
                "level": toc_entry["level"],
                "text": section_text,
                "start_pos": start_pos,
                "end_pos": end_pos,
                "start_page": toc_entry.get("start_page"),
                "end_page": toc_entry.get("end_page"),
            })

        return sections
