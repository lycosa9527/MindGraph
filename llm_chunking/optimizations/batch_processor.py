"""Batch processing for LLM calls.

Groups multiple items into batches for efficient LLM API calls.
Reduces API calls by 10x (10 items per batch).
"""
from typing import List, TypeVar, Callable, Awaitable, Optional
import logging


logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class BatchProcessor:
    """
    Batch processor for LLM API calls.

    Groups items into batches and processes them together,
    reducing API calls and improving performance.
    """

    # Default batch size (DashScope limit: 10)
    DEFAULT_BATCH_SIZE = 10

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        """
        Initialize batch processor.

        Args:
            batch_size: Number of items per batch (default: 10)
        """
        self.batch_size = batch_size

    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[List[T]], Awaitable[List[R]]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[R]:
        """
        Process items in batches.

        Args:
            items: List of items to process
            processor: Async function that processes a batch
            progress_callback: Optional callback for progress updates

        Returns:
            List of results
        """
        if not items:
            return []

        all_results = []
        total_batches = (len(items) + self.batch_size - 1) // self.batch_size

        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1

            logger.info(
                "Processing batch %d/%d (%d items)",
                batch_num, total_batches, len(batch)
            )

            if progress_callback:
                progress_callback(batch_num, total_batches)

            # Process batch
            batch_results = await processor(batch)
            all_results.extend(batch_results)

        logger.info("Processed %d items in %d batches", len(items), total_batches)
        return all_results

    def create_batches(self, items: List[T]) -> List[List[T]]:
        """
        Create batches from items.

        Args:
            items: List of items

        Returns:
            List of batches
        """
        batches = []
        for i in range(0, len(items), self.batch_size):
            batches.append(items[i:i + self.batch_size])
        return batches
