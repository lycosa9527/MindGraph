"""Knowledge Base Rate Limiter.

KB-specific rate limiting for knowledge base operations (retrieval, embedding, etc.).
Separate from general API rate limiting to control costs and prevent abuse.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Tuple, Optional
import logging
import os

from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter



logger = logging.getLogger(__name__)


class KBRateLimiter:
    """
    Knowledge Base-specific rate limiter.

    Provides separate rate limits for KB operations:
    - Retrieval requests (queries per minute)
    - Embedding generation (cost-based limiting)
    - Document uploads (per user)

    Uses RedisRateLimiter for sliding window tracking.
    """

    def __init__(self):
        """Initialize KB rate limiter."""
        self.rate_limiter = RedisRateLimiter()

        # Configuration from environment
        # Retrievals per minute per user
        self.retrieval_rpm = int(os.getenv("KB_RETRIEVAL_RPM", "60"))
        self.retrieval_window = 60  # 1 minute window

        # Embeddings per minute per user
        self.embedding_rpm = int(os.getenv("KB_EMBEDDING_RPM", "100"))
        self.embedding_window = 60  # 1 minute window

        # Uploads per hour per user
        self.upload_per_hour = int(os.getenv("KB_UPLOAD_PER_HOUR", "10"))
        self.upload_window = 3600  # 1 hour window

        logger.info(
            "[KBRateLimiter] Initialized: "
            "Retrieval=%s/min, "
            "Embedding=%s/min, "
            "Upload=%s/hour",
            self.retrieval_rpm,
            self.embedding_rpm,
            self.upload_per_hour
        )

    def check_retrieval_limit(self, user_id: int) -> Tuple[bool, int, str]:
        """
        Check if user can make a retrieval request.

        Args:
            user_id: User ID

        Returns:
            Tuple of (is_allowed, count, error_message)
        """
        return self.rate_limiter.check_and_record(
            category="kb_retrieval",
            identifier=str(user_id),
            max_attempts=self.retrieval_rpm,
            window_seconds=self.retrieval_window
        )

    def check_embedding_limit(self, user_id: int) -> Tuple[bool, int, str]:
        """
        Check if user can generate embeddings (cost-based limiting).

        Args:
            user_id: User ID

        Returns:
            Tuple of (is_allowed, count, error_message)
        """
        return self.rate_limiter.check_and_record(
            category="kb_embedding",
            identifier=str(user_id),
            max_attempts=self.embedding_rpm,
            window_seconds=self.embedding_window
        )

    def check_upload_limit(self, user_id: int) -> Tuple[bool, int, str]:
        """
        Check if user can upload a document.

        Args:
            user_id: User ID

        Returns:
            Tuple of (is_allowed, count, error_message)
        """
        return self.rate_limiter.check_and_record(
            category="kb_upload",
            identifier=str(user_id),
            max_attempts=self.upload_per_hour,
            window_seconds=self.upload_window
        )

    def get_retrieval_remaining(self, user_id: int) -> Tuple[int, int]:
        """
        Get remaining retrieval attempts and seconds until reset.

        Args:
            user_id: User ID

        Returns:
            Tuple of (remaining_attempts, seconds_until_reset)
        """
        return self.rate_limiter.get_remaining(
            category="kb_retrieval",
            identifier=str(user_id),
            max_attempts=self.retrieval_rpm,
            window_seconds=self.retrieval_window
        )

    def get_embedding_remaining(self, user_id: int) -> Tuple[int, int]:
        """
        Get remaining embedding attempts and seconds until reset.

        Args:
            user_id: User ID

        Returns:
            Tuple of (remaining_attempts, seconds_until_reset)
        """
        return self.rate_limiter.get_remaining(
            category="kb_embedding",
            identifier=str(user_id),
            max_attempts=self.embedding_rpm,
            window_seconds=self.embedding_window
        )

    def get_upload_remaining(self, user_id: int) -> Tuple[int, int]:
        """
        Get remaining upload attempts and seconds until reset.

        Args:
            user_id: User ID

        Returns:
            Tuple of (remaining_attempts, seconds_until_reset)
        """
        return self.rate_limiter.get_remaining(
            category="kb_upload",
            identifier=str(user_id),
            max_attempts=self.upload_per_hour,
            window_seconds=self.upload_window
        )

    def clear_retrieval_limit(self, user_id: int) -> bool:
        """Clear retrieval rate limit for user (e.g., admin override)."""
        return self.rate_limiter.clear("kb_retrieval", str(user_id))

    def clear_embedding_limit(self, user_id: int) -> bool:
        """Clear embedding rate limit for user (e.g., admin override)."""
        return self.rate_limiter.clear("kb_embedding", str(user_id))

    def clear_upload_limit(self, user_id: int) -> bool:
        """Clear upload rate limit for user (e.g., admin override)."""
        return self.rate_limiter.clear("kb_upload", str(user_id))


# Global singleton
_kb_rate_limiter: Optional[KBRateLimiter] = None


def get_kb_rate_limiter() -> KBRateLimiter:
    """Get or create global KB rate limiter instance."""
    global _kb_rate_limiter
    if _kb_rate_limiter is None:
        _kb_rate_limiter = KBRateLimiter()
    return _kb_rate_limiter
