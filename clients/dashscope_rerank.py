from typing import List, Dict, Any, Optional
import hashlib
import json
import logging
import os
import time

import httpx

from config.settings import config
from services.redis.redis_client import get_redis, is_redis_available
from utils.dashscope_error_handler import (

"""
DashScope Rerank Client for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Client for DashScope Rerank API.
Supports qwen3-rerank and gte-rerank-v2 models.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

    handle_dashscope_response,
    DashScopeError,
    should_retry,
    get_retry_delay
)

logger = logging.getLogger(__name__)


class DashScopeRerankClient:
    """
    Client for DashScope Rerank API.

    Reorders search results by semantic relevance.
    Supports qwen3-rerank and gte-rerank-v2 models.

    Model differences:
    - qwen3-rerank: Uses flat structure (query, documents, top_n at same level)
    - gte-rerank-v2: Uses nested structure (input.query, input.documents, parameters.top_n)
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize DashScope rerank client.

        Args:
            api_key: DashScope API key (default: from config.QWEN_API_KEY)
            model: Rerank model name (default: qwen3-rerank)
        """
        self.api_key = api_key or config.QWEN_API_KEY
        if not self.api_key:
            raise ValueError("DashScope API key is required")

        # Get model from parameter, environment variable, or config (in order of priority)
        self.model = model or os.getenv("DASHSCOPE_RERANK_MODEL") or getattr(config, 'DASHSCOPE_RERANK_MODEL', 'qwen3-rerank')

        # Check if model is qwen3-rerank (uses compatible API with flat structure)
        self.is_qwen3 = self.model == "qwen3-rerank"

        # Different API endpoints for different models:
        # - qwen3-rerank: uses new compatible API (flat structure)
        # - gte-rerank-v2: uses old API (nested input/parameters structure)
        if self.is_qwen3:
            self.rerank_url = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
        else:
            self.rerank_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

        # Rerank cache configuration (10 minutes TTL for query-document pairs)
        self.cache_enabled = os.getenv("RERANK_CACHE_ENABLED", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("RERANK_CACHE_TTL", "600"))  # 10 minutes

        logger.info(
            f"[DashScopeRerank] Initialized with model={self.model} "
            f"(API URL: {self.rerank_url}, cache={'enabled' if self.cache_enabled else 'disabled'})"
        )

    def _generate_cache_key(self, query: str, documents: List[str], top_n: int, score_threshold: float, instruct: Optional[str]) -> str:
        """Generate cache key for rerank request."""
        # Create hash of query + document texts + parameters
        cache_data = {
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "score_threshold": score_threshold,
            "instruct": instruct,
            "model": self.model
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        cache_hash = hashlib.md5(cache_str.encode('utf-8')).hexdigest()
        return f"rerank:{self.model}:{cache_hash}"

    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached rerank result from Redis."""
        if not self.cache_enabled or not is_redis_available():
            return None

        redis = get_redis()
        if not redis:
            return None

        try:
            cached = redis.get(cache_key)
            if cached:
                # Refresh TTL
                redis.expire(cache_key, self.cache_ttl)
                result = json.loads(cached)
                logger.debug(f"[DashScopeRerank] Cache hit for rerank request")
                return result
        except Exception as  # pylint: disable=broad-except e:
            logger.debug(f"[DashScopeRerank] Failed to get cached result: {e}")

        return None

    def _cache_result(self, cache_key: str, result: List[Dict[str, Any]]) -> None:
        """Cache rerank result in Redis."""
        if not self.cache_enabled or not is_redis_available():
            return

        redis = get_redis()
        if not redis:
            return

        try:
            cached_data = json.dumps(result)
            redis.setex(cache_key, self.cache_ttl, cached_data)
            logger.debug(f"[DashScopeRerank] Cached rerank result")
        except Exception as  # pylint: disable=broad-except e:
            logger.debug(f"[DashScopeRerank] Failed to cache result: {e}")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = 5,
        score_threshold: float = 0.5,
        instruct: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Query string (max 4,000 tokens)
            documents: List of document texts to rerank (max 500 docs, each max 4,000 tokens)
            top_n: Number of top results to return (default: 5)
            score_threshold: Minimum relevance score (0.0-1.0)
            instruct: Custom instruction for qwen3-rerank model (optional)
                     Default: "Given a web search query, retrieve relevant passages that answer the query."

        Returns:
            List of dicts with 'document', 'score', 'index' sorted by relevance
        """
        if not query:
            raise ValueError("Query cannot be empty")

        if not documents:
            return []

        # API Limits (DashScope qwen3-rerank / gte-rerank-v2):
        # - Max 4,000 tokens per query or document (truncated by API, may cause inaccurate ranking)
        # - Max 500 documents per request
        # - Max 30,000 total tokens across query + all documents
        MAX_TOKENS_PER_TEXT = 4000
        MAX_DOCUMENTS = 500
        MAX_TOTAL_TOKENS = 30000

        # Estimate tokens (rough: 1 token ≈ 1.5 chars for Chinese, 4 chars for English)
        # Use conservative estimate of 2 chars per token
        def estimate_tokens(text: str) -> int:
            return len(text) // 2 + 1

        # Truncate query if too long (4000 tokens ≈ 8000 chars)
        max_chars = MAX_TOKENS_PER_TEXT * 2
        if len(query) > max_chars:
            logger.warning(f"[DashScopeRerank] Query length {len(query)} chars exceeds limit, truncating to {max_chars}")
            query = query[:max_chars]

        # Truncate each document if too long
        truncated_docs = []
        for i, doc in enumerate(documents):
            if len(doc) > max_chars:
                logger.debug(f"[DashScopeRerank] Document {i} length {len(doc)} chars exceeds limit, truncating")
                truncated_docs.append(doc[:max_chars])
            else:
                truncated_docs.append(doc)
        documents = truncated_docs

        # Limit document count to 500
        if len(documents) > MAX_DOCUMENTS:
            logger.warning(f"[DashScopeRerank] Document count {len(documents)} exceeds limit {MAX_DOCUMENTS}, truncating")
            documents = documents[:MAX_DOCUMENTS]

        # Check total token limit (30,000)
        total_tokens = estimate_tokens(query) + sum(estimate_tokens(doc) for doc in documents)
        if total_tokens > MAX_TOTAL_TOKENS:
            # Reduce documents to fit within limit
            query_tokens = estimate_tokens(query)
            remaining_tokens = MAX_TOTAL_TOKENS - query_tokens

            kept_docs = []
            used_tokens = 0
            for doc in documents:
                doc_tokens = estimate_tokens(doc)
                if used_tokens + doc_tokens <= remaining_tokens:
                    kept_docs.append(doc)
                    used_tokens += doc_tokens
                else:
                    break

            if len(kept_docs) < len(documents):
                logger.warning(
                    f"[DashScopeRerank] Total tokens {total_tokens} exceeds limit {MAX_TOTAL_TOKENS}, "
                    f"reduced from {len(documents)} to {len(kept_docs)} documents"
                )
                documents = kept_docs

        if not documents:
            logger.warning("[DashScopeRerank] No documents left after applying limits")
            return []

        # Check cache first (after truncation to ensure consistent cache keys)
        cache_key = self._generate_cache_key(query, documents, top_n, score_threshold, instruct)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Build payload based on model type
        # Documents should be simple list of strings for both models
        if self.is_qwen3:
            # qwen3-rerank: flat structure (query, documents, top_n at same level)
            payload = {
                "model": self.model,
                "query": query,
                "documents": documents,  # Simple list of strings
                "top_n": min(top_n, len(documents)),
            }

            # Add custom instruction if provided (qwen3-rerank only, at top level)
            if instruct:
                payload["instruct"] = instruct
        else:
            # gte-rerank-v2: nested structure (input.query, input.documents, parameters.top_n)
            payload = {
                "model": self.model,
                "input": {
                    "query": query,
                    "documents": documents,  # Simple list of strings
                },
                "parameters": {
                    "top_n": min(top_n, len(documents)),
                    "return_documents": False,  # We already have documents
                }
            }

        logger.debug(f"[DashScopeRerank] Payload: model={self.model}, query_len={len(query)}, docs_count={len(documents)}")
        logger.debug(f"[DashScopeRerank] Full payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        self.rerank_url,
                        headers=headers,
                        json=payload,
                    )

                    # Log raw response for debugging
                    logger.debug(f"[DashScopeRerank] Response status={response.status_code}, body={response.text[:500]}")

                    # Check for errors with comprehensive handling
                    success, error = handle_dashscope_response(response, raise_on_error=False)
                    if not success and error:
                        last_error = error
                        # Check if we should retry
                        if should_retry(error, attempt, max_retries):
                            delay = get_retry_delay(attempt, error)
                            logger.warning(
                                f"[DashScopeRerank] Error on attempt {attempt}/{max_retries}: {error.message}. "
                                f"Retrying in {delay}s..."
                            )
                            time.sleep(delay)
                            continue
                        else:
                            # Don't retry, raise the error
                            raise error

                    result = response.json()

                # Handle both response formats:
                # - New compatible API (qwen3-rerank): {"results": [...]}
                # - Old API (gte-rerank-v2): {"output": {"results": [...]}}
                if "results" in result:
                    # New compatible API format
                    results = result["results"]
                elif "output" in result and "results" in result["output"]:
                    # Old API format
                    results = result["output"]["results"]
                else:
                    raise ValueError(f"Unexpected response format: {result}")

                # Process results
                reranked = []
                for item in results:
                    score = item.get("relevance_score", 0.0)
                    index = item.get("index", 0)

                    # Validate index and score
                    if score >= score_threshold and 0 <= index < len(documents):
                        reranked.append({
                            "document": documents[index],
                            "score": score,
                            "index": index,
                        })

                # Results are already sorted by relevance_score descending
                # But we sort again to be safe
                reranked.sort(key=lambda x: x["score"], reverse=True)

                logger.debug(
                    f"[DashScopeRerank] Reranked {len(documents)} documents, "
                    f"returned {len(reranked)} above threshold {score_threshold}"
                )

                # Cache the result
                self._cache_result(cache_key, reranked)

                # Success - return reranked results
                return reranked

            except DashScopeError as e:
                # DashScope-specific errors
                last_error = e
                # Check if we should retry
                if should_retry(e, attempt, max_retries):
                    delay = get_retry_delay(attempt, e)
                    logger.warning(
                        f"[DashScopeRerank] DashScope error on attempt {attempt}/{max_retries}: {e.message}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Don't retry, raise immediately
                    logger.error(f"[DashScopeRerank] DashScope API error: {e.message} (code: {e.error_code}, type: {e.error_type})")
                    raise
            except httpx.HTTPError as e:
                # Network/HTTP errors - retry if transient
                # Get status_code safely - only HTTPStatusError has response attribute
                status_code = None
                response = getattr(e, 'response', None)
                if response is not None:
                    status_code = getattr(response, 'status_code', None)

                last_error = DashScopeError(
                    message=f"HTTP error: {str(e)}",
                    status_code=status_code,
                    retryable=True
                )
                if should_retry(last_error, attempt, max_retries):
                    delay = get_retry_delay(attempt)
                    logger.warning(
                        f"[DashScopeRerank] HTTP error on attempt {attempt}/{max_retries}: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    if response is not None:
                        try:
                            error_detail = response.json()
                            logger.debug(f"[DashScopeRerank] Error details: {error_detail}")
                        except:
                            logger.debug(f"[DashScopeRerank] Response text: {getattr(response, 'text', 'N/A')}")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"[DashScopeRerank] HTTP error: {e}")
                    if response is not None:
                        try:
                            error_detail = response.json()
                            logger.error(f"[DashScopeRerank] Error details: {error_detail}")
                        except:
                            logger.error(f"[DashScopeRerank] Response text: {getattr(response, 'text', 'N/A')}")
                    raise
            except Exception as  # pylint: disable=broad-except e:
                # Other errors - don't retry
                logger.error(f"[DashScopeRerank] Error reranking: {e}")
                raise

        # If we exhausted retries, raise last error
        if last_error:
            raise last_error

        # This should never be reached, but satisfies type checker
        # If we somehow exit the loop without an error or return, raise a generic error
        raise RuntimeError("Rerank operation failed after all retries without a specific error")


# Global instance
_rerank_client: Optional[DashScopeRerankClient] = None


def get_rerank_client() -> DashScopeRerankClient:
    """Get global rerank client instance."""
    global _rerank_client
    if _rerank_client is None:
        _rerank_client = DashScopeRerankClient()
    return _rerank_client
