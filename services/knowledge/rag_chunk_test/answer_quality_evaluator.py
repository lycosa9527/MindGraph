"""
Answer Quality Evaluator for RAG Chunk Testing
===============================================

Evaluates answer quality metrics for QA datasets.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List
import logging
import re

from services.knowledge.chunking_service import Chunk


logger = logging.getLogger(__name__)


class AnswerQualityEvaluator:
    """Evaluate answer quality metrics for retrieved chunks."""

    def __init__(self):
        """Initialize answer quality evaluator."""

    def calculate_answer_coverage(
        self,
        retrieved_chunks: List[Chunk],
        ground_truth_answer: str
    ) -> float:
        """
        Calculate answer coverage: percentage of answer tokens found in retrieved chunks.

        Args:
            retrieved_chunks: List of retrieved chunks
            ground_truth_answer: Ground truth answer text

        Returns:
            Coverage score (0-1)
        """
        if not ground_truth_answer or not ground_truth_answer.strip():
            return 1.0

        if not retrieved_chunks:
            return 0.0

        # Tokenize answer (simple whitespace-based tokenization)
        answer_tokens = set(self._tokenize(ground_truth_answer.lower()))

        if not answer_tokens:
            return 1.0

        # Get all tokens from retrieved chunks
        chunk_tokens = set()
        for chunk in retrieved_chunks:
            chunk_tokens.update(self._tokenize(chunk.text.lower()))

        # Calculate coverage
        found_tokens = answer_tokens & chunk_tokens
        coverage = len(found_tokens) / len(answer_tokens) if answer_tokens else 0.0

        return coverage

    def calculate_answer_completeness(
        self,
        retrieved_chunks: List[Chunk],
        ground_truth_answer: str
    ) -> float:
        """
        Calculate answer completeness: binary score if full answer is present.

        Args:
            retrieved_chunks: List of retrieved chunks
            ground_truth_answer: Ground truth answer text

        Returns:
            Completeness score (0.0 or 1.0)
        """
        if not ground_truth_answer or not ground_truth_answer.strip():
            return 1.0

        if not retrieved_chunks:
            return 0.0

        # Get all text from retrieved chunks
        retrieved_text = " ".join(chunk.text for chunk in retrieved_chunks).lower()
        answer_lower = ground_truth_answer.lower()

        # Check if all key phrases from answer are present
        # Simple approach: check if answer appears as substring or key phrases
        answer_tokens = self._tokenize(answer_lower)
        key_phrases = self._extract_key_phrases(answer_tokens)

        all_phrases_found = True
        for phrase in key_phrases:
            if phrase not in retrieved_text:
                all_phrases_found = False
                break

        return 1.0 if all_phrases_found else 0.0

    def calculate_context_recall(
        self,
        retrieved_chunks: List[Chunk],
        ground_truth_answer: str,
        document_text: str
    ) -> float:
        """
        Calculate context recall: token-level recall of answer-relevant tokens.

        Args:
            retrieved_chunks: List of retrieved chunks
            ground_truth_answer: Ground truth answer text
            document_text: Full document text

        Returns:
            Context recall score (0-1)
        """
        if not ground_truth_answer or not ground_truth_answer.strip():
            return 1.0

        if not document_text or not document_text.strip():
            return 0.0

        if not retrieved_chunks:
            return 0.0

        # Tokenize answer to find relevant tokens
        answer_tokens = set(self._tokenize(ground_truth_answer.lower()))

        if not answer_tokens:
            return 1.0

        # Find answer-relevant tokens in document
        doc_tokens = self._tokenize(document_text.lower())
        relevant_doc_tokens = set(
            token for token in doc_tokens if token in answer_tokens
        )

        if not relevant_doc_tokens:
            return 1.0

        # Find which relevant tokens are in retrieved chunks
        retrieved_text = " ".join(chunk.text for chunk in retrieved_chunks).lower()
        retrieved_tokens = set(self._tokenize(retrieved_text))
        retrieved_relevant = relevant_doc_tokens & retrieved_tokens

        recall = (
            len(retrieved_relevant) / len(relevant_doc_tokens)
            if relevant_doc_tokens else 0.0
        )

        return recall

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization: split by whitespace and punctuation.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Remove punctuation and split by whitespace
        text_clean = re.sub(r'[^\w\s]', ' ', text)
        tokens = text_clean.split()
        # Filter out empty tokens
        return [t for t in tokens if t.strip()]

    def _extract_key_phrases(self, tokens: List[str], min_length: int = 3) -> List[str]:
        """
        Extract key phrases from tokens (n-grams of length 2-3).

        Args:
            tokens: List of tokens
            min_length: Minimum phrase length

        Returns:
            List of key phrases
        """
        if len(tokens) < min_length:
            return [" ".join(tokens)] if tokens else []

        phrases = []
        # Add unigrams (filter short ones)
        phrases.extend([t for t in tokens if len(t) >= min_length])

        # Add bigrams
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i+1]}"
            phrases.append(bigram)

        # Add trigrams
        for i in range(len(tokens) - 2):
            trigram = f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
            phrases.append(trigram)

        return phrases
