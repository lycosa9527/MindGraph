"""
LLM client wrappers and timing statistics.

This module provides legacy LLM client stubs and timing statistics tracking
for backward compatibility with existing code.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import logging
import threading
from typing import Any

from services.llm import llm_service

logger = logging.getLogger(__name__)


class LLMTimingStats:
    """Thread-safe LLM timing statistics tracker."""

    def __init__(self):
        self._lock = threading.Lock()  # pylint: disable=protected-access
        self._total_calls = 0  # pylint: disable=protected-access
        self._total_time = 0.0  # pylint: disable=protected-access
        self._call_times = []  # pylint: disable=protected-access
        self._last_call_time = 0.0  # pylint: disable=protected-access

    def add_call_time(self, call_time: float) -> None:
        """Add a new call time to statistics."""
        with self._lock:
            self._total_calls += 1
            self._total_time += call_time
            self._last_call_time = call_time
            self._call_times.append(call_time)

            # Keep only last 100 call times to prevent memory bloat
            if len(self._call_times) > 100:
                self._call_times = self._call_times[-100:]

    def get_stats(self) -> dict:
        """Get current timing statistics."""
        with self._lock:
            avg_time = (self._total_time / self._total_calls if self._total_calls > 0 else 0.0)
            return {
                'total_calls': self._total_calls,
                'total_time': self._total_time,
                'average_time': avg_time,
                'last_call_time': self._last_call_time,
                'call_times': self._call_times[-10:]
            }


# Thread-safe global timing tracker
llm_timing_stats = LLMTimingStats()


def get_llm_timing_stats() -> dict:
    """Get current LLM timing statistics."""
    return llm_timing_stats.get_stats()


class _LegacyLLMStub:
    """Stub for old concept map functions - uses LLM Service"""

    def invoke(self, prompt: str) -> str:
        """Public interface for LLM invocation."""
        async def _async_call():
            return await llm_service.chat(
                prompt=prompt,
                model='qwen',
                timeout=30.0
            )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_async_call())


# Legacy stubs for old concept map code - now using LLM Service
llm_classification = _LegacyLLMStub()
llm_generation = _LegacyLLMStub()
llm = _LegacyLLMStub()


class QwenLLM:
    """
    Backward-compatible sync wrapper for learning agents that haven't been migrated to async yet.

    Now uses LLM Service instead of direct client (Phase 5 migration).
    Used by: LearningAgent, LearningAgentV3, and qwen_langchain.py
    """
    def __init__(self, model_type='generation'):
        """
        Initialize QwenLLM wrapper.

        Args:
            model_type: 'generation' or 'classification' (uses qwen model from LLM Service)
        """
        self.model_type = model_type

    def _call(self, prompt: str, stop: Any = None) -> str:
        """
        Synchronous wrapper for async LLM Service call.

        Args:
            prompt: The prompt to send to the LLM
            stop: Stop sequences (not used, kept for compatibility)

        Returns:
            str: The LLM response content
        """
        # stop parameter is kept for API compatibility but not used
        del stop

        async def _async_call():
            return await llm_service.chat(
                prompt=prompt,
                model='qwen',
                timeout=30.0
            )

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_async_call())
