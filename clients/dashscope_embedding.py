"""
DashScope Embedding Client for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Client for DashScope Text Embedding API and Multimodal Embedding API.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
import base64
import logging
import os
import time

import httpx
import numpy as np

from config.settings import config
from utils.dashscope_error_handler import (
    handle_dashscope_response,
    DashScopeError,
    should_retry,
    get_retry_delay
)

logger = logging.getLogger(__name__)


class DashScopeEmbeddingClient:
    """
    Client for DashScope Text Embedding API and Multimodal Embedding API.

    Supports:
    - Text embeddings: text-embedding-v1, text-embedding-v2, text-embedding-v3, text-embedding-v4
    - Multimodal embeddings: qwen2.5-vl-embedding, tongyi-embedding-vision-plus,
      tongyi-embedding-vision-flash, multimodal-embedding-v1

    Features:
    - Custom dimensions (v3, v4)
    - text_type parameter (query vs document)
    - instruct parameter (v4 only, for task-specific optimization)
    - output_type (dense/sparse/dense&sparse for v3, v4)
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize DashScope embedding client.

        Args:
            api_key: DashScope API key (default: from config.QWEN_API_KEY)
            model: Embedding model name (default: text-embedding-v4)
        """
        self.api_key = api_key or config.QWEN_API_KEY
        if not self.api_key:
            raise ValueError("DashScope API key is required")

        self.model = (
            model or os.getenv("DASHSCOPE_EMBEDDING_MODEL") or
            getattr(config, 'DASHSCOPE_EMBEDDING_MODEL', 'text-embedding-v4')
        )
        self.base_url = config.DASHSCOPE_API_URL or "https://dashscope.aliyuncs.com/api/v1/"

        # Determine if multimodal model
        self.is_multimodal = self._is_multimodal_model(self.model)

        # Use OpenAI-compatible endpoint by default (cleaner API, better compatibility)
        self.use_openai_compatible = os.getenv("USE_OPENAI_COMPATIBLE_EMBEDDING", "true").lower() == "true"

        if self.is_multimodal:
            self.embedding_url = f"{self.base_url}services/embeddings/multimodal-embedding/multimodal-embedding"
        elif self.use_openai_compatible:
            # OpenAI compatible endpoint
            self.embedding_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        else:
            # Standard DashScope API endpoint
            self.embedding_url = f"{self.base_url}services/embeddings/text-embedding/text-embedding"

        # Batch size (max rows) per model version:
        # - v3/v4: max 10 rows
        # - v1/v2: max 25 rows
        if self.model.startswith("text-embedding-v3") or self.model.startswith("text-embedding-v4"):
            self.batch_size = min(int(os.getenv("EMBEDDING_BATCH_SIZE", "10")), 10)
        else:  # v1, v2
            self.batch_size = min(int(os.getenv("EMBEDDING_BATCH_SIZE", "25")), 25)

        logger.info(
            "[DashScopeEmbedding] Initialized with model=%s "
            "(multimodal=%s, OpenAI-compatible=%s)",
            self.model, self.is_multimodal, self.use_openai_compatible
        )

    @staticmethod
    def _is_multimodal_model(model: str) -> bool:
        """Check if model supports multimodal embeddings."""
        multimodal_models = [
            "qwen2.5-vl-embedding",
            "tongyi-embedding-vision-plus",
            "tongyi-embedding-vision-flash",
            "multimodal-embedding-v1"
        ]
        return model in multimodal_models

    def _make_request(
        self,
        texts: List[str],
        input_type: str = "document",
        dimensions: Optional[int] = None,
        instruct: Optional[str] = None,
        output_type: str = "dense"
    ) -> List[List[float]]:
        """
        Make embedding API request.

        Args:
            texts: List of texts to embed
            input_type: "document" or "query" (for v2, v3, v4)
            dimensions: Custom vector dimension (for v3, v4). Options: 64, 128, 256, 512, 768, 1024, 1536, 2048
            instruct: Task instruction for v4 (requires input_type="query")
            output_type: "dense", "sparse", or "dense&sparse" (for v3, v4)

        Returns:
            List of embedding vectors
        """
        # API Limits per model version:
        # - v3/v4: Max 10 rows, 8,192 tokens per row
        # - v1/v2: Max 25 rows, 2,048 tokens per row
        # Estimate: 1 token ≈ 2 chars (conservative for mixed Chinese/English)
        if self.model.startswith("text-embedding-v3") or self.model.startswith("text-embedding-v4"):
            max_tokens_per_text = 8192
        else:  # v1, v2
            max_tokens_per_text = 2048

        max_chars = max_tokens_per_text * 2

        # Truncate texts that exceed the limit
        truncated_texts = []
        for i, text in enumerate(texts):
            if len(text) > max_chars:
                logger.debug(
                    "[DashScopeEmbedding] Text %d length %d chars exceeds %d "
                    "token limit, truncating",
                    i, len(text), max_tokens_per_text
                )
                truncated_texts.append(text[:max_chars])
            else:
                truncated_texts.append(text)
        texts = truncated_texts

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Build payload based on API type
        if self.use_openai_compatible:
            # OpenAI compatible format
            payload = {
                "model": self.model,
                "input": texts if len(texts) > 1 else texts[0],  # Single text or array
            }

            # Add optional parameters
            if dimensions:
                payload["dimensions"] = dimensions
        else:
            # Standard DashScope API format
            payload = {
                "model": self.model,
                "input": {
                    "texts": texts
                },
                "parameters": {}
            }

            # Add text_type (for v2, v3, v4)
            if input_type:
                payload["parameters"]["text_type"] = input_type

            # Add dimensions (for v3, v4)
            if dimensions:
                payload["parameters"]["dimension"] = dimensions

            # Add instruct (for v4 only, requires query type)
            if instruct and self.model.startswith("text-embedding-v4"):
                if input_type != "query":
                    logger.warning(
                        "[DashScopeEmbedding] instruct parameter requires "
                        "input_type='query', ignoring instruct"
                    )
                else:
                    payload["parameters"]["instruct"] = instruct

            # Add output_type (for v3, v4)
            if (output_type != "dense" and
                    (self.model.startswith("text-embedding-v3") or
                     self.model.startswith("text-embedding-v4"))):
                payload["parameters"]["output_type"] = output_type

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        self.embedding_url,
                        headers=headers,
                        json=payload,
                    )

                    # Check for errors with comprehensive handling
                    success, error = handle_dashscope_response(response, raise_on_error=False)
                    if not success and error:
                        last_error = error
                        # Check if we should retry
                        if should_retry(error, attempt, max_retries):
                            delay = get_retry_delay(attempt, error)
                            logger.warning(
                                "[DashScopeEmbedding] Error on attempt %d/%d: %s. "
                                "Retrying in %ds...",
                                attempt, max_retries, error.message, delay
                            )
                            time.sleep(delay)
                            continue
                        else:
                            # Don't retry, raise the error
                            raise error

                    result = response.json()

                # Handle OpenAI-compatible response format
                if self.use_openai_compatible:
                    if "data" in result:
                        raw_embeddings = [item["embedding"] for item in result["data"]]
                    else:
                        raise ValueError(f"Unexpected OpenAI-compatible response format: {result}")
                elif "output" in result and "embeddings" in result["output"]:
                    embeddings = result["output"]["embeddings"]
                    raw_embeddings = [item["embedding"] for item in embeddings]
                else:
                    raise ValueError(f"Unexpected response format: {result}")

                # Normalize and validate embeddings
                normalized_embeddings = []
                for i, embedding in enumerate(raw_embeddings):
                    try:
                        # Convert to numpy array for normalization
                        embedding_array = np.array(embedding, dtype=np.float32)

                        # Check for NaN or Inf values
                        if np.isnan(embedding_array).any() or np.isinf(embedding_array).any():
                            logger.warning(
                                "[DashScopeEmbedding] Invalid embedding (NaN/Inf) "
                                "at index %d, skipping this embedding",
                                i
                            )
                            continue

                        # L2 normalization for accurate cosine similarity
                        norm = np.linalg.norm(embedding_array)
                        if norm > 0:
                            normalized = (embedding_array / norm).tolist()
                            normalized_embeddings.append(normalized)
                        else:
                            logger.warning(
                                "[DashScopeEmbedding] Zero-norm embedding at index %d, "
                                "skipping this embedding",
                                i
                            )
                            continue

                    except Exception as e:  # pylint: disable=broad-except
                        logger.error(
                            "[DashScopeEmbedding] Failed to normalize embedding "
                            "at index %d: %s",
                            i, e
                        )
                        continue

                if len(normalized_embeddings) != len(raw_embeddings):
                    logger.warning(
                        "[DashScopeEmbedding] Normalized %d/%d embeddings "
                        "(some were invalid)",
                        len(normalized_embeddings), len(raw_embeddings)
                    )

                # Success - return embeddings
                return normalized_embeddings

            except DashScopeError as e:
                # DashScope-specific errors
                last_error = e
                # Check if we should retry
                if should_retry(e, attempt, max_retries):
                    delay = get_retry_delay(attempt, e)
                    logger.warning(
                        "[DashScopeEmbedding] DashScope error on attempt %d/%d: %s. "
                        "Retrying in %ds...",
                        attempt, max_retries, e.message, delay
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Don't retry, raise immediately
                    logger.error(
                        "[DashScopeEmbedding] DashScope API error: %s "
                        "(code: %s, type: %s)",
                        e.message, e.error_code, e.error_type
                    )
                    raise
            except httpx.HTTPError as e:
                # Network/HTTP errors - retry if transient
                status_code = None
                if isinstance(e, httpx.HTTPStatusError):
                    response = getattr(e, 'response', None)
                    if response is not None:
                        status_code = response.status_code
                last_error = DashScopeError(
                    message=f"HTTP error: {str(e)}",
                    status_code=status_code,
                    retryable=True
                )
                if should_retry(last_error, attempt, max_retries):
                    delay = get_retry_delay(attempt)
                    logger.warning(
                        "[DashScopeEmbedding] HTTP error on attempt %d/%d: %s. "
                        "Retrying in %ds...",
                        attempt, max_retries, e, delay
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error("[DashScopeEmbedding] HTTP error: %s", e)
                    raise
            except Exception as e:  # pylint: disable=broad-except
                # Other errors - don't retry
                logger.error("[DashScopeEmbedding] Error embedding texts: %s", e)
                raise

        # If we exhausted retries, raise last error
        if last_error:
            raise last_error
        # This should never be reached, but type checker needs it
        raise RuntimeError("Unexpected end of retry loop")

    def embed_texts(
        self,
        texts: List[str],
        text_type: str = "document",
        dimensions: Optional[int] = None,
        output_type: str = "dense"
    ) -> List[List[float]]:
        """
        Embed multiple texts (for documents).

        Args:
            texts: List of text strings to embed
            text_type: "document" (default) or "query"
            dimensions: Custom vector dimension (for v3, v4). Default: from config or model default
            output_type: "dense" (default), "sparse", or "dense&sparse" (for v3, v4)

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []

        # Use optimized dimensions from config if not specified
        if dimensions is None:
            dimensions = config.EMBEDDING_DIMENSIONS

        # Process in batches
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                batch_embeddings = self._make_request(
                    batch,
                    input_type=text_type,
                    dimensions=dimensions,
                    output_type=output_type
                )
                all_embeddings.extend(batch_embeddings)
                logger.debug(
                    "[DashScopeEmbedding] Embedded batch %d, size=%d",
                    i//self.batch_size + 1, len(batch)
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "[DashScopeEmbedding] Failed to embed batch starting at index %d: %s",
                    i, e
                )
                raise

        return all_embeddings

    def embed_query(
        self,
        query: str,
        dimensions: Optional[int] = None,
        instruct: Optional[str] = None,
        output_type: str = "dense"
    ) -> List[float]:
        """
        Embed a single query text.

        Args:
            query: Query text string
            dimensions: Custom vector dimension (for v3, v4). Default: from config or model default
            instruct: Task instruction for v4 (e.g., "Given a web search query, retrieve relevant passages")
            output_type: "dense" (default), "sparse", or "dense&sparse" (for v3, v4)

        Returns:
            Embedding vector (list of floats)
        """
        if not query:
            raise ValueError("Query text cannot be empty")

        # Use optimized dimensions from config if not specified
        if dimensions is None:
            dimensions = config.EMBEDDING_DIMENSIONS

        try:
            embeddings = self._make_request(
                [query],
                input_type="query",
                dimensions=dimensions,
                instruct=instruct,
                output_type=output_type
            )
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            else:
                raise ValueError("Empty embedding response")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[DashScopeEmbedding] Failed to embed query: %s", e)
            raise

    def embed_image(self, image_path: str) -> List[float]:
        """
        Embed a single image (multimodal models only).

        Args:
            image_path: Path to image file or image URL

        Returns:
            Embedding vector (list of floats)
        """
        if not self.is_multimodal:
            raise ValueError(f"Model {self.model} does not support multimodal embeddings")

        try:
            # Check if it's a URL or local file
            if image_path.startswith(("http://", "https://")):
                # URL
                content = {"image": image_path}
            else:
                # Local file - convert to base64
                image_data = self._image_to_base64(image_path)
                content = {"image": image_data}

            embeddings = self._make_multimodal_request([content])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            else:
                raise ValueError("Empty embedding response")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[DashScopeEmbedding] Failed to embed image: %s", e)
            raise

    def embed_multimodal(
        self,
        contents: List[Union[str, Dict[str, str]]]
    ) -> List[List[float]]:
        """
        Embed multimodal content (text, images, videos).

        Args:
            contents: List of content items. Each item can be:
                - String (text)
                - Dict with "text" key (text)
                - Dict with "image" key (image URL or base64)
                - Dict with "video" key (video URL)
                - Dict with "multi_images" key (list of image URLs/base64)

        Returns:
            List of embedding vectors
        """
        if not self.is_multimodal:
            raise ValueError(f"Model {self.model} does not support multimodal embeddings")

        # Normalize contents format
        normalized_contents = []
        for content in contents:
            if isinstance(content, str):
                normalized_contents.append({"text": content})
            elif isinstance(content, dict):
                # Handle local image paths
                if "image" in content:
                    image_path = content["image"]
                    if not image_path.startswith(("http://", "https://", "data:image")):
                        # Local file - convert to base64
                        content["image"] = self._image_to_base64(image_path)
                normalized_contents.append(content)
            else:
                raise ValueError(f"Invalid content type: {type(content)}")

        return self._make_multimodal_request(normalized_contents)

    def _image_to_base64(self, image_path: str) -> str:
        """
        Convert local image file to base64 Data URI.

        Args:
            image_path: Path to image file

        Returns:
            Base64 Data URI string
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Determine image format
        ext = path.suffix.lower().lstrip(".")
        if ext not in ["jpg", "jpeg", "png", "webp", "bmp", "tiff", "ico"]:
            raise ValueError(f"Unsupported image format: {ext}")

        # Read and encode
        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:image/{ext};base64,{image_data}"

    def _make_multimodal_request(
        self,
        contents: List[Dict[str, Any]]
    ) -> List[List[float]]:
        """
        Make multimodal embedding API request.

        Args:
            contents: List of content dictionaries

        Returns:
            List of embedding vectors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": {
                "contents": contents
            }
        }

        # Add parameters for tongyi-embedding-vision-plus
        if self.model == "tongyi-embedding-vision-plus":
            payload["parameters"] = {
                "output_type": "dense",
                "dimension": 1024  # Default dimension
            }

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=120.0) as client:  # Longer timeout for multimodal
                    response = client.post(
                        self.embedding_url,
                        headers=headers,
                        json=payload,
                    )

                    # Check for errors with comprehensive handling
                    success, error = handle_dashscope_response(response, raise_on_error=False)
                    if not success and error:
                        last_error = error
                        # Check if we should retry
                        if should_retry(error, attempt, max_retries):
                            delay = get_retry_delay(attempt, error)
                            logger.warning(
                                "[DashScopeEmbedding] Error on attempt %d/%d: %s. "
                                "Retrying in %ds...",
                                attempt, max_retries, error.message, delay
                            )
                            time.sleep(delay)
                            continue
                        else:
                            # Don't retry, raise the error
                            raise error

                    result = response.json()

                if "output" in result and "embeddings" in result["output"]:
                    embeddings = result["output"]["embeddings"]
                    # Sort by index to maintain order
                    embeddings.sort(key=lambda x: x.get("index", 0))
                    raw_embeddings = [item["embedding"] for item in embeddings]

                    # Normalize and validate embeddings
                    normalized_embeddings = []
                    for i, embedding in enumerate(raw_embeddings):
                        try:
                            embedding_array = np.array(embedding, dtype=np.float32)

                            # Check for NaN or Inf values
                            if np.isnan(embedding_array).any() or np.isinf(embedding_array).any():
                                logger.warning(
                                    "[DashScopeEmbedding] Invalid embedding (NaN/Inf) "
                                    "at index %d, skipping this embedding",
                                    i
                                )
                                continue

                            # L2 normalization
                            norm = np.linalg.norm(embedding_array)
                            if norm > 0:
                                normalized = (embedding_array / norm).tolist()
                                normalized_embeddings.append(normalized)
                            else:
                                logger.warning(
                                    "[DashScopeEmbedding] Zero-norm embedding at index %d, "
                                    "skipping this embedding",
                                    i
                                )
                                continue

                        except Exception as e:  # pylint: disable=broad-except
                            logger.error(
                                "[DashScopeEmbedding] Failed to normalize embedding "
                                "at index %d: %s",
                                i, e
                            )
                            continue

                    if len(normalized_embeddings) != len(raw_embeddings):
                        logger.warning(
                            "[DashScopeEmbedding] Normalized %d/%d embeddings "
                            "(some were invalid)",
                            len(normalized_embeddings), len(raw_embeddings)
                        )

                    # Success - return embeddings
                    return normalized_embeddings
                else:
                    raise ValueError(f"Unexpected response format: {result}")

            except DashScopeError as e:
                # DashScope-specific errors
                last_error = e
                # Check if we should retry
                if should_retry(e, attempt, max_retries):
                    delay = get_retry_delay(attempt, e)
                    logger.warning(
                        "[DashScopeEmbedding] DashScope error on attempt %d/%d: %s. "
                        "Retrying in %ds...",
                        attempt, max_retries, e.message, delay
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Don't retry, raise immediately
                    logger.error(
                        "[DashScopeEmbedding] DashScope API error: %s "
                        "(code: %s, type: %s)",
                        e.message, e.error_code, e.error_type
                    )
                    raise
            except httpx.HTTPError as e:
                # Network/HTTP errors - retry if transient
                status_code = None
                if isinstance(e, httpx.HTTPStatusError):
                    response = getattr(e, 'response', None)
                    if response is not None:
                        status_code = response.status_code
                last_error = DashScopeError(
                    message=f"HTTP error: {str(e)}",
                    status_code=status_code,
                    retryable=True
                )
                if should_retry(last_error, attempt, max_retries):
                    delay = get_retry_delay(attempt)
                    logger.warning(
                        "[DashScopeEmbedding] HTTP error on attempt %d/%d: %s. "
                        "Retrying in %ds...",
                        attempt, max_retries, e, delay
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error("[DashScopeEmbedding] HTTP error: %s", e)
                    raise
            except Exception as e:  # pylint: disable=broad-except
                # Other errors - don't retry
                logger.error(
                    "[DashScopeEmbedding] Error embedding multimodal content: %s",
                    e
                )
                raise

        # If we exhausted retries, raise last error
        if last_error:
            raise last_error
        # This should never be reached, but type checker needs it
        raise RuntimeError("Unexpected end of retry loop")


# Global instance
_embedding_client: Optional[DashScopeEmbeddingClient] = None


def get_embedding_client() -> DashScopeEmbeddingClient:
    """Get global embedding client instance."""
    global _embedding_client  # pylint: disable=global-statement
    if _embedding_client is None:
        _embedding_client = DashScopeEmbeddingClient()
    return _embedding_client
