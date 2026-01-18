"""
Teaching materials specific chunker.

Enhances chunking with educational metadata:
- Content type detection
- Learning objective extraction
- Concept extraction
- Code/formula preservation
"""

import re
import logging
from typing import List, Optional
from llm_chunking.models import TeachingChunk, CodeBlock, Formula, ParentChunk
from llm_chunking.chunker import LLMSemanticChunker
from llm_chunking.agents.content_type_agent import ContentTypeAgent
from llm_chunking.teaching.concept_extractor import ConceptExtractor

logger = logging.getLogger(__name__)


class TeachingChunker:
    """
    Enhanced chunker for teaching materials.

    Adds educational metadata and preserves special content types.
    """

    def __init__(self, chunker: Optional[LLMSemanticChunker] = None, llm_service=None):
        """
        Initialize teaching chunker.

        Args:
            chunker: Base LLM chunker instance
            llm_service: LLM service instance
        """
        self.chunker = chunker or LLMSemanticChunker(llm_service=llm_service)
        self.content_type_agent = ContentTypeAgent(llm_service=llm_service)
        self.concept_extractor = ConceptExtractor(llm_service=llm_service)

    async def chunk(
        self,
        text: str,
        document_id: str,
        extract_concepts: bool = True,
        detect_content_types: bool = True,
        **kwargs
    ) -> List[TeachingChunk]:
        """
        Chunk teaching materials with enhancements.

        Args:
            text: Text to chunk
            document_id: Document identifier
            extract_concepts: If True, extract key concepts
            detect_content_types: If True, detect content types
            **kwargs: Additional parameters

        Returns:
            List of TeachingChunk objects
        """
        # Step 1: Base chunking
        base_chunks = await self.chunker.chunk(
            text,
            document_id,
            structure_type="parent_child",  # Teaching materials usually hierarchical
            **kwargs
        )

        # Step 2: Convert to TeachingChunks and enhance
        teaching_chunks = []

        for i, base_chunk in enumerate(base_chunks):
            # Extract chunk text
            if isinstance(base_chunk, ParentChunk):
                # Use first child or parent text
                chunk_text = base_chunk.children[0].text if base_chunk.children else base_chunk.text
            else:
                chunk_text = base_chunk.text

            # Detect content type
            content_type = "theory"  # Default
            if detect_content_types:
                content_type = await self.content_type_agent.detect_content_type(chunk_text)

            # Preserve code blocks
            code_block = self._extract_code_block(chunk_text)

            # Preserve formulas
            formula = self._extract_formula(chunk_text)

            # Create teaching chunk
            teaching_chunk = TeachingChunk(
                text=chunk_text,
                start_char=base_chunk.start_char,
                end_char=base_chunk.end_char,
                chunk_index=i,
                token_count=base_chunk.token_count or 0,
                content_type=content_type,
                code_block=code_block,
                formula=formula,
                metadata=base_chunk.metadata or {},
            )

            teaching_chunks.append(teaching_chunk)

        # Step 3: Extract concepts (optional)
        if extract_concepts:
            concepts = await self.concept_extractor.extract_concepts(text)
            # Associate concepts with chunks (simplified)
            for chunk in teaching_chunks:
                chunk.key_concepts = [
                    c.name for c in concepts
                    if c.name.lower() in chunk.text.lower()
                ][:5]  # Limit to 5 concepts per chunk

        chunks_count = len(teaching_chunks)
        logger.info("Created %s teaching chunks", chunks_count)
        return teaching_chunks

    def _extract_code_block(self, text: str) -> Optional[CodeBlock]:
        """Extract code block from text."""
        # Markdown code blocks
        pattern = r'```(\w+)?\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            language = match.group(1) or "unknown"
            code = match.group(2)
            return CodeBlock(
                code=code,
                language=language,
                start_pos=match.start(),
                end_pos=match.end()
            )

        return None

    def _extract_formula(self, text: str) -> Optional[Formula]:
        """Extract formula from text."""
        # LaTeX inline: $...$
        latex_inline = r'\$([^$]+)\$'
        match = re.search(latex_inline, text)

        if match:
            return Formula(
                formula=match.group(1),
                format="latex",
                start_pos=match.start(),
                end_pos=match.end()
            )

        # LaTeX block: $$...$$
        latex_block = r'\$\$([^$]+)\$\$'
        match = re.search(latex_block, text)

        if match:
            return Formula(
                formula=match.group(1),
                format="latex",
                start_pos=match.start(),
                end_pos=match.end()
            )

        return None
