"""Structure detection agent using 30-page sampling.

Analyzes first 30 pages to detect document structure and determine
optimal chunking strategy (General, Parent-Child, or Q&A).
"""
from typing import Dict, Any, Optional, List
import json
import logging
import traceback

from llm_chunking.models import DocumentStructure
from llm_chunking.patterns.toc_detector import TOCDetector

try:
    from services.llm import llm_service as default_llm_service
except ImportError:
    default_llm_service = None


logger = logging.getLogger(__name__)


class StructureAgent:
    """
    Agent for detecting document structure via sampling.

    Uses 30-page sampling + LLM analysis to determine:
    - Document type (book, article, FAQ, exercise book, etc.)
    - Optimal chunk structure (General, Parent-Child, Q&A)
    - Chunking strategy and rules
    """

    def __init__(self, llm_service=None):
        """
        Initialize structure agent.

        Args:
            llm_service: LLM service instance (uses services.llm_service if None)
        """
        self.llm_service = llm_service
        if llm_service is None:
            try:
                # Verify LLM service is initialized
                if (default_llm_service is None or
                        not hasattr(default_llm_service, 'client_manager') or
                        not default_llm_service.client_manager.is_initialized()):
                    logger.warning(
                        "[StructureAgent] LLM service not initialized. "
                        "Structure detection will use heuristics fallback."
                    )
                    self.llm_service = None
                else:
                    self.llm_service = default_llm_service
            except Exception as e:
                logger.warning(
                    "[StructureAgent] LLM service not available: %s. "
                    "Structure detection will use heuristics fallback.",
                    e
                )
                self.llm_service = None

        self.toc_detector = TOCDetector()

    async def analyze_structure(
        self,
        sample_text: str,
        document_id: str,
        pdf_outline: Optional[List[Dict[str, Any]]] = None
    ) -> DocumentStructure:
        """
        Analyze document structure from sample.

        Args:
            sample_text: Sampled text (first 30 pages)
            document_id: Document identifier
            pdf_outline: Optional PDF outline

        Returns:
            DocumentStructure with detected structure
        """
        # Step 1: Try TOC detection first (fast, pattern-based)
        toc = self.toc_detector.detect_hybrid(sample_text, pdf_outline, max_pages=30)

        # Step 2: LLM analysis for structure type and chunking strategy
        structure_type, document_type, chunking_rules = await self._llm_analyze(
            sample_text,
            toc
        )

        # Step 3: Create structure
        try:
            logger.info(
                "[StructureAgent] Creating DocumentStructure: doc_id=%s, "
                "structure_type=%s, doc_type=%s",
                document_id,
                structure_type,
                document_type
            )
            structure = DocumentStructure(
                document_id=document_id,
                structure_type=structure_type,
                toc=toc,
                chunking_rules=chunking_rules,
                document_type=document_type,
            )
            logger.info(
                "[StructureAgent] ✓ DocumentStructure created: type=%s, "
                "doc_type=%s, toc_entries=%d",
                structure.structure_type,
                structure.document_type,
                len(toc)
            )
        except Exception as e:
            logger.error("[StructureAgent] ✗ Failed to create DocumentStructure: %s", e)
            logger.error("[StructureAgent] Full traceback:")
            logger.error(traceback.format_exc())
            logger.error("[StructureAgent] Exception type: %s", type(e).__name__)
            logger.error("[StructureAgent] Exception args: %s", e.args)
            logger.error("[StructureAgent] DocumentStructure import check:")
            logger.error("[StructureAgent] DocumentStructure imported successfully: %s", DocumentStructure)
            raise

        return structure

    async def _llm_analyze(
        self,
        sample_text: str,
        toc: List[Dict[str, Any]]
    ) -> tuple[str, Optional[str], Dict[str, Any]]:
        """
        Use LLM to analyze structure.

        Args:
            sample_text: Sample text
            toc: Detected TOC entries

        Returns:
            Tuple of (structure_type, document_type, chunking_rules)
        """
        if not self.llm_service:
            # Fallback: Use heuristics
            return self._heuristic_analyze(sample_text, toc)

        # Build prompt
        toc_info = ""
        if toc:
            toc_info = "\n".join([
                f"  {entry.get('title', '')} (level {entry.get('level', 1)})"
                for entry in toc[:10]  # Limit to first 10 entries
            ])

        prompt = f"""Analyze this document sample and determine the optimal chunking structure.

Document Sample (first 30 pages):
{sample_text[:5000]}

Table of Contents (if detected):
{toc_info if toc_info else "No TOC detected"}

Determine:
1. Document type: book, article, FAQ, exercise_book, manual, thesis, etc.
2. Optimal chunk structure: "general", "parent_child", or "qa"
3. Chunking rules: chunk sizes, parent mode (if parent_child), etc.

Return JSON:
{{
    "document_type": "book",
    "structure_type": "parent_child",
    "chunking_rules": {{
        "parent_max_tokens": 2000,
        "child_max_tokens": 500,
        "parent_mode": "paragraph"
    }}
}}
"""

        try:
            response = await self.llm_service.chat(
                prompt=prompt,
                model='qwen',
                temperature=0.3,
                max_tokens=500
            )

            # Parse JSON response
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)

                structure_type = result.get("structure_type", "general")
                document_type = result.get("document_type")
                chunking_rules = result.get("chunking_rules", {})

                return structure_type, document_type, chunking_rules
            else:
                logger.warning("Failed to parse LLM response as JSON, using heuristics")
                return self._heuristic_analyze(sample_text, toc)

        except Exception as e:
            logger.warning("LLM analysis failed: %s, using heuristics", e)
            return self._heuristic_analyze(sample_text, toc)

    def _heuristic_analyze(
        self,
        sample_text: str,
        toc: List[Dict[str, Any]]
    ) -> tuple[str, Optional[str], Dict[str, Any]]:
        """
        Heuristic analysis fallback.

        Args:
            sample_text: Sample text
            toc: TOC entries

        Returns:
            Tuple of (structure_type, document_type, chunking_rules)
        """
        # If TOC detected with multiple levels, use parent-child
        if toc and len(toc) > 3:
            max_level = max(entry.get("level", 1) for entry in toc)
            if max_level >= 2:
                return (
                    "parent_child",
                    "book",
                    {
                        "parent_max_tokens": 2000,
                        "child_max_tokens": 500,
                        "parent_mode": "paragraph"
                    }
                )

        # Check for Q&A patterns
        qa_patterns = ["Q:", "A:", "Question", "Answer", "FAQ"]
        if any(pattern in sample_text for pattern in qa_patterns):
            return (
                "qa",
                "faq",
                {
                    "generate_questions": True
                }
            )

        # Default: general structure
        return (
            "general",
            "article",
            {
                "chunk_size": 500,
                "overlap": 50
            }
        )
