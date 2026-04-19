"""
Qdrant diagnostics and compression metrics helpers (mixin for QdrantService).
Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict
import logging
import random

logger = logging.getLogger(__name__)


def _empty_compression_metrics(error: str | None = None) -> Dict[str, Any]:
    """Default metrics dict when collection is missing or on error."""
    result: Dict[str, Any] = {
        "compression_enabled": False,
        "compression_type": None,
        "points_count": 0,
        "vector_size": 0,
        "estimated_uncompressed_size": 0.0,
        "estimated_compressed_size": 0.0,
        "compression_ratio": 1.0,
        "storage_savings_percent": 0.0,
    }
    if error is not None:
        result["error"] = error
    return result


def _build_compression_metrics(
    points_count: int,
    vector_size: int,
    compression_enabled: bool,
    compression_type: str | None,
) -> Dict[str, Any]:
    """Build metrics dict from collection stats and compression settings."""
    bytes_per_vector_uncompressed = vector_size * 4
    metadata_overhead = 200
    estimated_uncompressed = points_count * (bytes_per_vector_uncompressed + metadata_overhead)
    if compression_enabled:
        bytes_per_vector_compressed = vector_size * 1
        estimated_compressed = points_count * (bytes_per_vector_compressed + metadata_overhead)
        compression_ratio = estimated_uncompressed / estimated_compressed if estimated_compressed > 0 else 1.0
        storage_savings = (
            (1.0 - (estimated_compressed / estimated_uncompressed)) * 100 if estimated_uncompressed > 0 else 0.0
        )
    else:
        estimated_compressed = estimated_uncompressed
        compression_ratio = 1.0
        storage_savings = 0.0

    return {
        "compression_enabled": compression_enabled,
        "compression_type": compression_type,
        "points_count": points_count,
        "vector_size": vector_size,
        "estimated_uncompressed_size": estimated_uncompressed,
        "estimated_compressed_size": estimated_compressed,
        "compression_ratio": round(compression_ratio, 2),
        "storage_savings_percent": round(storage_savings, 1),
    }


class QdrantDiagnosticsMixin:
    """
    Compression metrics and collection diagnostics for QdrantService.

    Expects: client (AsyncQdrantClient), use_compression, compression_type,
    get_user_collection (async), _get_collection_name.
    """

    async def get_compression_metrics(self, user_id: int) -> Dict[str, Any]:
        """
        Get compression metrics for user's collection.

        Args:
            user_id: User ID

        Returns:
            Dict with compression metrics:
            - compression_enabled: bool
            - compression_type: str
            - points_count: int
            - vector_size: int
            - estimated_uncompressed_size: float (bytes)
            - estimated_compressed_size: float (bytes)
            - compression_ratio: float
            - storage_savings_percent: float
        """
        collection_name = await self.get_user_collection(user_id)
        if not collection_name:
            return _empty_compression_metrics()

        try:
            info = await self.client.get_collection(collection_name)
            compression_enabled = self.use_compression
            compression_type = self.compression_type if compression_enabled else None
            return _build_compression_metrics(
                info.points_count,
                info.config.params.vectors.size,
                compression_enabled,
                compression_type,
            )
        except Exception as exc:
            logger.error("[Qdrant] Failed to get compression metrics for user %s: %s", user_id, exc)
            return _empty_compression_metrics(str(exc))

    async def get_diagnostics(self, user_id: int) -> Dict[str, Any]:
        """
        Get diagnostic information for user's Qdrant collection.

        Useful for debugging retrieval issues.

        Args:
            user_id: User ID

        Returns:
            Dict with collection info, point count, sample payloads, etc.
        """
        result: Dict[str, Any] = {
            "user_id": user_id,
            "collection_name": self._get_collection_name(user_id),
            "collection_exists": False,
            "points_count": 0,
            "vector_dimensions": None,
            "sample_points": [],
            "payload_keys": set(),
            "errors": [],
        }

        try:
            collection_name = await self.get_user_collection(user_id)
            if not collection_name:
                result["errors"].append(f"Collection does not exist for user {user_id}")
                return result

            result["collection_exists"] = True

            try:
                info = await self.client.get_collection(collection_name)
                result["points_count"] = info.points_count
                if info.config and info.config.params and info.config.params.vectors:
                    vectors_config = info.config.params.vectors
                    if hasattr(vectors_config, "size"):
                        result["vector_dimensions"] = vectors_config.size
                    elif isinstance(vectors_config, dict) and "" in vectors_config:
                        result["vector_dimensions"] = vectors_config[""].size
            except Exception as exc:
                result["errors"].append(f"Failed to get collection info: {exc}")

            try:
                scroll_result = await self.client.scroll(
                    collection_name=collection_name,
                    limit=5,
                    with_payload=True,
                    with_vectors=False,
                )

                points = scroll_result[0] if scroll_result else []
                for point in points:
                    point_info = {"id": point.id, "payload": point.payload}
                    result["sample_points"].append(point_info)

                    if point.payload:
                        result["payload_keys"].update(point.payload.keys())

            except Exception as exc:
                result["errors"].append(f"Failed to scroll points: {exc}")

            result["payload_keys"] = list(result["payload_keys"])

            if result["vector_dimensions"]:
                try:
                    test_vector = [random.random() for _ in range(result["vector_dimensions"])]
                    response = await self.client.query_points(
                        collection_name=collection_name,
                        query=test_vector,
                        limit=1,
                        with_payload=True,
                    )
                    result["test_search_returned"] = len(response.points)
                except Exception as exc:
                    result["errors"].append(f"Test search failed: {exc}")

        except Exception as exc:
            result["errors"].append(f"Diagnostic failed: {exc}")

        return result
