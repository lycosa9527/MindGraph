"""
Manual Evaluator for RAG Chunk Testing
=======================================

Evaluates chunk quality and answer relevance using DashScope LLM models.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Dict, Any
import logging
import asyncio
import json

from services.knowledge.chunking_service import Chunk
from services.llm import llm_service as llm_svc


logger = logging.getLogger(__name__)


CHUNK_QUALITY_PROMPT = """You are an expert evaluator for RAG (Retrieval-Augmented Generation) systems.

Evaluate the quality of a text chunk in the context of answering a query.

Query: {query}

Chunk Text:
{chunk_text}

Please evaluate the chunk on the following dimensions (provide scores from 0.0 to 1.0):

1. **Relevance**: How relevant is this chunk to answering the query? (0.0 = not relevant, 1.0 = highly relevant)
2. **Completeness**: Does this chunk contain complete information, or is it fragmented? (0.0 = fragmented, 1.0 = complete)
3. **Clarity**: Is the information in this chunk clear and well-structured? (0.0 = unclear, 1.0 = very clear)
4. **Information Density**: How much useful information does this chunk contain relative to its length? (0.0 = low density, 1.0 = high density)

Respond in JSON format:
{{
    "relevance": <float>,
    "completeness": <float>,
    "clarity": <float>,
    "information_density": <float>,
    "overall_score": <float>,
    "reasoning": "<brief explanation>"
}}
"""

ANSWER_RELEVANCE_PROMPT = """You are an expert evaluator for RAG (Retrieval-Augmented Generation) systems.

Evaluate how well a set of retrieved chunks can answer a query, given a ground truth answer.

Query: {query}

Ground Truth Answer: {answer}

Retrieved Chunks:
{chunks_text}

Please evaluate on the following dimensions (provide scores from 0.0 to 1.0):

1. **Answer Coverage**: Do the retrieved chunks contain the information needed to answer the query? (0.0 = no coverage, 1.0 = complete coverage)
2. **Answer Faithfulness**: Would an answer generated from these chunks be faithful to the ground truth? (0.0 = not faithful, 1.0 = highly faithful)
3. **Context Utilization**: How well do the chunks provide context for answering the query? (0.0 = poor context, 1.0 = excellent context)
4. **Information Completeness**: Do the chunks contain all necessary information, or are there gaps? (0.0 = major gaps, 1.0 = complete)

Respond in JSON format:
{{
    "answer_coverage": <float>,
    "answer_faithfulness": <float>,
    "context_utilization": <float>,
    "information_completeness": <float>,
    "overall_score": <float>,
    "reasoning": "<brief explanation>"
}}
"""

SEMANTIC_SIMILARITY_PROMPT = """You are an expert evaluator for semantic similarity.

Evaluate the semantic similarity between two text chunks.

Chunk 1:
{chunk1_text}

Chunk 2:
{chunk2_text}

Provide a similarity score from 0.0 to 1.0, where:
- 0.0 = completely different topics/meanings
- 0.5 = somewhat related but different
- 1.0 = very similar or identical meaning

Respond in JSON format:
{{
    "similarity_score": <float>,
    "reasoning": "<brief explanation>"
}}
"""


class ManualEvaluator:
    """Evaluate chunk quality and answer relevance using DashScope LLM models."""

    def __init__(self):
        """Initialize manual evaluator."""
        self.llm_service = llm_svc
        if not self.llm_service:
            raise RuntimeError(
                "[ManualEvaluator] LLM service not available. "
                "Manual evaluation requires LLM service to be initialized."
            )

    def evaluate_chunk_quality(
        self,
        chunk: Chunk,
        query: str,
        model: str = "qwen-max"
    ) -> Dict[str, Any]:
        """
        Evaluate chunk quality in the context of a query.

        Args:
            chunk: Chunk to evaluate
            query: Query that the chunk should answer
            model: DashScope model to use (default: "qwen-max")

        Returns:
            Dictionary with evaluation scores and reasoning
        """
        if not chunk or not chunk.text:
            return {
                "relevance": 0.0,
                "completeness": 0.0,
                "clarity": 0.0,
                "information_density": 0.0,
                "overall_score": 0.0,
                "reasoning": "Empty chunk"
            }

        prompt = CHUNK_QUALITY_PROMPT.format(
            query=query,
            chunk_text=chunk.text[:2000]  # Limit chunk text length
        )

        logger.info(
            "[ManualEvaluator] Evaluating chunk quality: query='%s', chunk_length=%s",
            query[:50],
            len(chunk.text)
        )

        try:
            # Handle async LLM call in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            response = loop.run_until_complete(
                self.llm_service.chat(
                    prompt=prompt,
                    model=model,
                    max_tokens=500,
                    temperature=0.1,
                    system_message="You are a precise evaluator. Always respond with valid JSON."
                )
            )

            if not response or not response.strip():
                logger.warning("[ManualEvaluator] Empty response from LLM")
                return self._default_evaluation()

            # Parse JSON response
            evaluation = self._parse_json_response(response)
            return evaluation

        except Exception as e:
            logger.error(
                "[ManualEvaluator] Failed to evaluate chunk quality: %s",
                e,
                exc_info=True
            )
            return self._default_evaluation()

    def evaluate_answer_relevance(
        self,
        chunks: List[Chunk],
        query: str,
        answer: str,
        model: str = "qwen-max"
    ) -> Dict[str, Any]:
        """
        Evaluate how well retrieved chunks can answer a query, given ground truth answer.

        Args:
            chunks: List of retrieved chunks
            query: Query that should be answered
            answer: Ground truth answer
            model: DashScope model to use (default: "qwen-max")

        Returns:
            Dictionary with evaluation scores and reasoning
        """
        if not chunks:
            return {
                "answer_coverage": 0.0,
                "answer_faithfulness": 0.0,
                "context_utilization": 0.0,
                "information_completeness": 0.0,
                "overall_score": 0.0,
                "reasoning": "No chunks provided"
            }

        # Format chunks text (limit total length)
        chunks_text = "\n\n--- Chunk {} ---\n{}".format(
            "{}",
            "{}"
        )
        chunks_list = []
        total_length = 0
        max_total_length = 3000

        for idx, chunk in enumerate(chunks):
            chunk_text = chunk.text[:500]  # Limit per chunk
            if total_length + len(chunk_text) > max_total_length:
                break
            chunks_list.append(f"--- Chunk {idx + 1} ---\n{chunk_text}")
            total_length += len(chunk_text)

        chunks_text = "\n\n".join(chunks_list)

        prompt = ANSWER_RELEVANCE_PROMPT.format(
            query=query,
            answer=answer[:1000],  # Limit answer length
            chunks_text=chunks_text
        )

        logger.info(
            "[ManualEvaluator] Evaluating answer relevance: query='%s', chunks=%s",
            query[:50],
            len(chunks)
        )

        try:
            # Handle async LLM call in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            response = loop.run_until_complete(
                self.llm_service.chat(
                    prompt=prompt,
                    model=model,
                    max_tokens=500,
                    temperature=0.1,
                    system_message="You are a precise evaluator. Always respond with valid JSON."
                )
            )

            if not response or not response.strip():
                logger.warning("[ManualEvaluator] Empty response from LLM")
                return self._default_answer_evaluation()

            # Parse JSON response
            evaluation = self._parse_json_response(response)
            return evaluation

        except Exception as e:
            logger.error(
                "[ManualEvaluator] Failed to evaluate answer relevance: %s",
                e,
                exc_info=True
            )
            return self._default_answer_evaluation()

    def evaluate_semantic_similarity(
        self,
        chunk1: Chunk,
        chunk2: Chunk,
        model: str = "qwen-max"
    ) -> float:
        """
        Evaluate semantic similarity between two chunks.

        Args:
            chunk1: First chunk
            chunk2: Second chunk
            model: DashScope model to use (default: "qwen-max")

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not chunk1 or not chunk1.text or not chunk2 or not chunk2.text:
            return 0.0

        prompt = SEMANTIC_SIMILARITY_PROMPT.format(
            chunk1_text=chunk1.text[:1000],
            chunk2_text=chunk2.text[:1000]
        )

        logger.debug(
            "[ManualEvaluator] Evaluating semantic similarity between chunks"
        )

        try:
            # Handle async LLM call in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            response = loop.run_until_complete(
                self.llm_service.chat(
                    prompt=prompt,
                    model=model,
                    max_tokens=200,
                    temperature=0.1,
                    system_message="You are a precise evaluator. Always respond with valid JSON."
                )
            )

            if not response or not response.strip():
                logger.warning("[ManualEvaluator] Empty response from LLM")
                return 0.0

            # Parse JSON response
            result = self._parse_json_response(response)
            similarity = result.get("similarity_score", 0.0)
            return float(similarity)

        except Exception as e:
            logger.error(
                "[ManualEvaluator] Failed to evaluate semantic similarity: %s",
                e,
                exc_info=True
            )
            return 0.0

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM, handling various formats.

        Args:
            response: LLM response text

        Returns:
            Parsed dictionary
        """
        # Try to extract JSON from response (may be wrapped in markdown code blocks)
        response_clean = response.strip()

        # Remove markdown code blocks if present
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        elif response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()

        try:
            return json.loads(response_clean)
        except json.JSONDecodeError:
            # Try to find JSON object in response
            import re
            json_match = re.search(r'\{[^{}]*\}', response_clean, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            logger.warning(
                "[ManualEvaluator] Failed to parse JSON response: %s",
                response_clean[:200]
            )
            return {}

    def _default_evaluation(self) -> Dict[str, Any]:
        """Return default evaluation scores."""
        return {
            "relevance": 0.0,
            "completeness": 0.0,
            "clarity": 0.0,
            "information_density": 0.0,
            "overall_score": 0.0,
            "reasoning": "Evaluation failed"
        }

    def _default_answer_evaluation(self) -> Dict[str, Any]:
        """Return default answer evaluation scores."""
        return {
            "answer_coverage": 0.0,
            "answer_faithfulness": 0.0,
            "context_utilization": 0.0,
            "information_completeness": 0.0,
            "overall_score": 0.0,
            "reasoning": "Evaluation failed"
        }


def get_manual_evaluator() -> ManualEvaluator:
    """Get global manual evaluator instance."""
    if not hasattr(get_manual_evaluator, 'instance'):
        get_manual_evaluator.instance = ManualEvaluator()
    return get_manual_evaluator.instance
