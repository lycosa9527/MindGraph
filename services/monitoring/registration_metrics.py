from datetime import datetime
from threading import Lock
from typing import Optional, Dict, Any
import logging


"""
Registration Metrics Service
============================

Tracks registration performance metrics for monitoring and observability.

Features:
- Registration attempts, successes, and failures
- Failure reasons (lock timeout, database deadlock, phone exists, etc.)
- Average registration time
- Database commit retry counts
- Cache write success rate

Metrics are logged to structured logs and can be exported to Prometheus/StatsD if needed.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


logger = logging.getLogger(__name__)


class RegistrationMetrics:
    """
    Tracks registration performance metrics.

    Thread-safe metrics collection for monitoring registration performance
    across all workers. Metrics are logged to structured logs.
    """

    def __init__(self):
        """Initialize RegistrationMetrics instance."""
        self._lock = Lock()
        self._metrics = {
            'total_attempts': 0,
            'total_successes': 0,
            'total_failures': 0,
            'failures_by_reason': {
                'lock_timeout': 0,
                'database_deadlock': 0,
                'phone_exists': 0,
                'captcha_failed': 0,
                'sms_code_invalid': 0,
                'invitation_code_invalid': 0,
                'other': 0
            },
            'total_registration_time': 0.0,
            'min_registration_time': float('inf'),
            'max_registration_time': 0.0,
            'database_commit_retries': {
                'total_retries': 0,
                'retry_counts': {}  # {retry_count: frequency}
            },
            'cache_write_successes': 0,
            'cache_write_failures': 0,
            'last_reset': datetime.now().isoformat()
        }

    def record_attempt(self):
        """Record a registration attempt."""
        with self._lock:
            self._metrics['total_attempts'] += 1

    def record_success(self, duration: float, retry_count: int = 0, cache_write_success: bool = True):
        """
        Record a successful registration.

        Args:
            duration: Registration duration in seconds
            retry_count: Number of database commit retries (0 = no retries)
            cache_write_success: Whether cache write succeeded
        """
        with self._lock:
            self._metrics['total_successes'] += 1
            self._metrics['total_registration_time'] += duration

            # Update min/max duration
            if duration < self._metrics['min_registration_time']:
                self._metrics['min_registration_time'] = duration
            if duration > self._metrics['max_registration_time']:
                self._metrics['max_registration_time'] = duration

            # Track retries
            if retry_count > 0:
                self._metrics['database_commit_retries']['total_retries'] += retry_count
                retry_counts = self._metrics['database_commit_retries']['retry_counts']
                retry_counts[retry_count] = retry_counts.get(retry_count, 0) + 1

            # Track cache writes
            if cache_write_success:
                self._metrics['cache_write_successes'] += 1
            else:
                self._metrics['cache_write_failures'] += 1

    def record_failure(self, reason: str, duration: Optional[float] = None):
        """
        Record a failed registration.

        Args:
            reason: Failure reason (lock_timeout, database_deadlock, phone_exists, etc.)
            duration: Registration duration in seconds (if available)
        """
        with self._lock:
            self._metrics['total_failures'] += 1

            # Track failure reason
            failures_by_reason = self._metrics['failures_by_reason']
            if reason in failures_by_reason:
                failures_by_reason[reason] += 1
            else:
                failures_by_reason['other'] += 1

            # Track duration if available
            if duration is not None:
                self._metrics['total_registration_time'] += duration
                if duration < self._metrics['min_registration_time']:
                    self._metrics['min_registration_time'] = duration
                if duration > self._metrics['max_registration_time']:
                    self._metrics['max_registration_time'] = duration

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dict with current metrics
        """
        with self._lock:
            metrics = self._metrics.copy()

            # Calculate averages
            total_completed = metrics['total_successes'] + metrics['total_failures']
            if total_completed > 0:
                metrics['avg_registration_time'] = metrics['total_registration_time'] / total_completed
            else:
                metrics['avg_registration_time'] = 0.0

            # Calculate success rate
            if metrics['total_attempts'] > 0:
                metrics['success_rate'] = metrics['total_successes'] / metrics['total_attempts']
            else:
                metrics['success_rate'] = 0.0

            # Calculate cache write success rate
            total_cache_writes = metrics['cache_write_successes'] + metrics['cache_write_failures']
            if total_cache_writes > 0:
                metrics['cache_write_success_rate'] = metrics['cache_write_successes'] / total_cache_writes
            else:
                metrics['cache_write_success_rate'] = 0.0

            # Calculate average retries
            if metrics['total_successes'] > 0:
                metrics['avg_database_retries'] = (
                    metrics['database_commit_retries']['total_retries'] /
                    metrics['total_successes']
                )
            else:
                metrics['avg_database_retries'] = 0.0

            return metrics

    def log_metrics(self):
        """Log current metrics to structured logs."""
        metrics = self.get_metrics()

        logger.info(
            "[RegistrationMetrics] Registration metrics",
            extra={
                'metrics': {
                    'total_attempts': metrics['total_attempts'],
                    'total_successes': metrics['total_successes'],
                    'total_failures': metrics['total_failures'],
                    'success_rate': f"{metrics['success_rate']:.2%}",
                    'avg_registration_time_ms': f"{metrics['avg_registration_time'] * 1000:.2f}",
                    'min_registration_time_ms': (
                        f"{metrics['min_registration_time'] * 1000:.2f}"
                        if metrics['min_registration_time'] != float('inf')
                        else "N/A"
                    ),
                    'max_registration_time_ms': f"{metrics['max_registration_time'] * 1000:.2f}",
                    'failures_by_reason': metrics['failures_by_reason'],
                    'avg_database_retries': f"{metrics['avg_database_retries']:.2f}",
                    'cache_write_success_rate': f"{metrics['cache_write_success_rate']:.2%}",
                }
            }
        )

    def reset(self):
        """Reset all metrics (useful for periodic resets)."""
        with self._lock:
            self._metrics = {
                'total_attempts': 0,
                'total_successes': 0,
                'total_failures': 0,
                'failures_by_reason': {
                    'lock_timeout': 0,
                    'database_deadlock': 0,
                    'phone_exists': 0,
                    'captcha_failed': 0,
                    'sms_code_invalid': 0,
                    'invitation_code_invalid': 0,
                    'other': 0
                },
                'total_registration_time': 0.0,
                'min_registration_time': float('inf'),
                'max_registration_time': 0.0,
                'database_commit_retries': {
                    'total_retries': 0,
                    'retry_counts': {}
                },
                'cache_write_successes': 0,
                'cache_write_failures': 0,
                'last_reset': datetime.now().isoformat()
            }


# Global singleton instance
_registration_metrics: Optional[RegistrationMetrics] = None


def get_registration_metrics() -> RegistrationMetrics:
    """Get or create global RegistrationMetrics instance."""
    global _registration_metrics
    if _registration_metrics is None:
        _registration_metrics = RegistrationMetrics()
        logger.info("[RegistrationMetrics] Initialized")
    return _registration_metrics


# Convenience alias
registration_metrics = get_registration_metrics()

