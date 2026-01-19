"""
QA Generator for RAG Chunk Testing
===================================

Generates Q&A pairs from documents using LLM (similar to Dify's QA mode).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any, Optional
import logging
import re
import asyncio

from services.knowledge.chunking_service import Chunk
from services.llm import llm_service as llm_svc


logger = logging.getLogger(__name__)


GENERATOR_QA_PROMPT = (
    "<Task> The user will send a long text. Generate a Question and Answer pairs only using the knowledge"
    " in the long text. Please think step by step."
    "Step 1: Understand and summarize the main content of this text.\n"
    "Step 2: What key information or concepts are mentioned in this text?\n"
    "Step 3: Decompose or combine multiple pieces of information and concepts.\n"
    "Step 4: Generate questions and answers based on these key information and concepts.\n"
    "<Constraints> The questions should be clear and detailed, and the answers should be detailed and complete. "
    "You must answer in {language}, in a style that is clear and detailed in {language}."
    " No language other than {language} should be used. \n"
    "<Format> Use the following format: Q1:\nA1:\nQ2:\nA2:...\n"
    "<QA Pairs>"
)


class QAGenerator:
    """Generate Q&A pairs from documents using LLM."""

    def __init__(self):
        """Initialize QA generator."""
        self.llm_service = llm_svc

    def generate_qa_chunks(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        language: str = "English"
    ) -> List[Chunk]:
        """
        Generate Q&A chunks from text using LLM.

        Args:
            text: Text to generate Q&A pairs from
            metadata: Optional metadata to attach to chunks
            language: Language for Q&A generation (default: "English")

        Returns:
            List of Chunk objects with Q&A pairs
        """
        if not self.llm_service:
            raise RuntimeError(
                "[QAGenerator] LLM service not available. "
                "QA mode requires LLM service to be initialized."
            )

        if not text or not text.strip():
            return []

        # Generate Q&A pairs using LLM
        system_prompt = GENERATOR_QA_PROMPT.format(language=language)

        logger.info(
            "[QAGenerator] Generating Q&A pairs for text length=%s, language=%s",
            len(text),
            language
        )

        try:
            # Handle async LLM call in sync context (similar to MindChunkAdapter)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Call LLM service to generate Q&A pairs
            # System message contains the QA generation instructions
            # User message contains the text to process
            response = loop.run_until_complete(
                self.llm_service.chat(
                    prompt=text,
                    model='qwen',
                    max_tokens=2000,
                    temperature=0.01,
                    system_message=system_prompt
                )
            )

            if not response or not response.strip():
                logger.warning(
                    "[QAGenerator] Empty response from LLM service"
                )
                return []

            # Parse Q&A pairs from response
            qa_pairs = self._parse_qa_response(response)

            if not qa_pairs:
                logger.warning(
                    "[QAGenerator] No Q&A pairs parsed from LLM response"
                )
                return []

            # Convert Q&A pairs to Chunk objects
            chunks = []
            base_metadata = dict(metadata or {})
            current_pos = 0

            for idx, (question, answer) in enumerate(qa_pairs):
                # Create chunk with question as text and answer in metadata
                # This matches Dify's approach where question is the content
                # and answer is stored in metadata
                chunk_text = question
                start_char = current_pos
                end_char = start_char + len(chunk_text)
                current_pos = end_char

                chunk_metadata = {
                    **base_metadata,
                    "answer": answer,
                    "question": question,
                    "qa_index": idx,
                    "structure_type": "qa"
                }

                chunk = Chunk(
                    text=chunk_text,
                    start_char=start_char,
                    end_char=end_char,
                    chunk_index=idx,
                    metadata=chunk_metadata
                )
                chunks.append(chunk)

            logger.info(
                "[QAGenerator] Generated %s Q&A chunks from text",
                len(chunks)
            )

            return chunks

        except Exception as e:
            logger.error(
                "[QAGenerator] Failed to generate Q&A pairs: %s",
                e,
                exc_info=True
            )
            raise RuntimeError(
                f"[QAGenerator] QA generation failed: {e}"
            ) from e

    def _parse_qa_response(self, response: str) -> List[tuple[str, str]]:
        """
        Parse Q&A pairs from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of (question, answer) tuples
        """
        # Use regex pattern similar to Dify's QAIndexProcessor
        # Pattern: Q1: question A1: answer Q2: question A2: answer ...
        regex = r"Q\d+:\s*(.*?)\s*A\d+:\s*([\s\S]*?)(?=Q\d+:|$)"
        matches = re.findall(regex, response, re.UNICODE)

        qa_pairs = []
        for question, answer in matches:
            if question and answer:
                # Clean up answer (remove extra whitespace)
                cleaned_answer = re.sub(r"\n\s*", "\n", answer.strip())
                qa_pairs.append((question.strip(), cleaned_answer))

        logger.debug(
            "[QAGenerator] Parsed %s Q&A pairs from response",
            len(qa_pairs)
        )

        return qa_pairs
