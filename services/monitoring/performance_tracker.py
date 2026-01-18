from collections import deque
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Any
import logging


"""
Performance Tracker
===================

Tracks LLM performance metrics and implements circuit breaker pattern.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


logger = logging.getLogger(__name__)


class CircuitState:
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, block requests
    HALF_OPEN = "half_open"  # Testing if recovered


class PerformanceTracker:
    """
    Tracks LLM performance and implements circuit breaker pattern.

    Features:
    - Response time tracking per model
    - Success/failure rate monitoring
    - Circuit breaker for consistently failing models
    - Performance metrics collection
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_window: int = 60,
        circuit_open_duration: int = 30
    ):
        """
        Initialize performance tracker.

        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes to close circuit from half-open
            timeout_window: Time window for tracking failures (seconds)
            circuit_open_duration: How long circuit stays open (seconds)
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_window = timeout_window
        self.circuit_open_duration = circuit_open_duration

        # Per-model tracking
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._circuit_states: Dict[str, str] = {}
        self._circuit_open_times: Dict[str, datetime] = {}
        self._recent_failures: Dict[str, deque] = {}
        self._recent_successes: Dict[str, deque] = {}

        self._lock = Lock()

        logger.info("[PerformanceTracker] Initialized")

    def record_request(
        self,
        model: str,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Record a request's performance.

        Args:
            model: Model name
            duration: Request duration in seconds
            success: Whether request succeeded
            error: Error message if failed
        """
        with self._lock:
            # Initialize model metrics if needed
            if model not in self._metrics:
                self._metrics[model] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'total_duration': 0.0,
                    'min_duration': float('inf'),
                    'max_duration': 0.0,
                    'response_times': deque(maxlen=100),  # Last 100 requests
                    'last_success': None,
                    'last_failure': None,
                    'errors': deque(maxlen=10)  # Last 10 errors
                }
                self._circuit_states[model] = CircuitState.CLOSED
                self._recent_failures[model] = deque(maxlen=self.failure_threshold)
                self._recent_successes[model] = deque(maxlen=self.success_threshold)

            metrics = self._metrics[model]

            # Update counters
            metrics['total_requests'] += 1

            if success:
                metrics['successful_requests'] += 1
                metrics['last_success'] = datetime.now()

                # Track recent successes for circuit breaker
                self._recent_successes[model].append(datetime.now())

                # Check if we should close circuit from half-open
                if self._circuit_states[model] == CircuitState.HALF_OPEN:
                    if len(self._recent_successes[model]) >= self.success_threshold:
                        self._close_circuit(model)
            else:
                metrics['failed_requests'] += 1
                metrics['last_failure'] = datetime.now()

                if error:
                    metrics['errors'].append({
                        'timestamp': datetime.now(),
                        'error': error
                    })

                # Track recent failures for circuit breaker
                self._recent_failures[model].append(datetime.now())

                # Check if we should open circuit
                if self._should_open_circuit(model):
                    self._open_circuit(model)

            # Update duration stats
            metrics['total_duration'] += duration
            metrics['min_duration'] = min(metrics['min_duration'], duration)
            metrics['max_duration'] = max(metrics['max_duration'], duration)
            metrics['response_times'].append(duration)

            logger.debug(
                "[PerformanceTracker] %s: success=%s, duration=%.2fs, circuit=%s",
                model, success, duration, self._circuit_states[model]
            )

    def _should_open_circuit(self, model: str) -> bool:
        """Check if circuit should be opened."""
        if self._circuit_states[model] == CircuitState.OPEN:
            return False

        # Clean old failures outside time window
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.timeout_window)

        recent = self._recent_failures[model]
        while recent and recent[0] < cutoff:
            recent.popleft()

        # Open if failures exceed threshold
        return len(recent) >= self.failure_threshold

    def _open_circuit(self, model: str):
        """Open circuit for a model."""
        self._circuit_states[model] = CircuitState.OPEN
        self._circuit_open_times[model] = datetime.now()
        logger.warning("[PerformanceTracker] Circuit OPEN for %s", model)

    def _close_circuit(self, model: str):
        """Close circuit for a model."""
        self._circuit_states[model] = CircuitState.CLOSED
        self._recent_failures[model].clear()
        self._recent_successes[model].clear()
        logger.info("[PerformanceTracker] Circuit CLOSED for %s", model)

    def can_call_model(self, model: str) -> bool:
        """
        Check if model can be called (circuit breaker check).

        Args:
            model: Model name

        Returns:
            True if model can be called
        """
        with self._lock:
            # Initialize if first call
            if model not in self._circuit_states:
                self._circuit_states[model] = CircuitState.CLOSED
                return True

            state = self._circuit_states[model]

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                # Check if circuit should transition to half-open
                open_time = self._circuit_open_times.get(model)
                if open_time:
                    elapsed = (datetime.now() - open_time).total_seconds()
                    if elapsed >= self.circuit_open_duration:
                        self._circuit_states[model] = CircuitState.HALF_OPEN
                        logger.info("[PerformanceTracker] Circuit HALF-OPEN for %s", model)
                        return True
                return False

            if state == CircuitState.HALF_OPEN:
                return True

            return True

    def get_metrics(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics.

        Args:
            model: Specific model name, or None for all models

        Returns:
            Dictionary of metrics
        """
        with self._lock:
            if model:
                return self._get_model_metrics(model)
            else:
                return {
                    model_name: self._get_model_metrics(model_name)
                    for model_name in self._metrics.keys()
                }

    def _get_model_metrics(self, model: str) -> Dict[str, Any]:
        """Get metrics for a specific model."""
        if model not in self._metrics:
            return {
                'total_requests': 0,
                'success_rate': 0.0,
                'circuit_state': CircuitState.CLOSED
            }

        metrics = self._metrics[model]
        total = metrics['total_requests']
        successful = metrics['successful_requests']

        # Calculate average response time
        avg_duration = 0.0
        if total > 0:
            avg_duration = metrics['total_duration'] / total

        # Calculate success rate
        success_rate = 0.0
        if total > 0:
            success_rate = (successful / total) * 100

        # Get recent average (last 100 requests)
        recent_avg = 0.0
        if metrics['response_times']:
            recent_avg = sum(metrics['response_times']) / len(metrics['response_times'])

        return {
            'total_requests': total,
            'successful_requests': successful,
            'failed_requests': metrics['failed_requests'],
            'success_rate': round(success_rate, 2),
            'avg_response_time': round(avg_duration, 2),
            'min_response_time': round(metrics['min_duration'], 2) if metrics['min_duration'] != float('inf') else 0.0,
            'max_response_time': round(metrics['max_duration'], 2),
            'recent_avg_response_time': round(recent_avg, 2),
            'circuit_state': self._circuit_states.get(model, CircuitState.CLOSED),
            'last_success': metrics['last_success'].isoformat() if metrics['last_success'] else None,
            'last_failure': metrics['last_failure'].isoformat() if metrics['last_failure'] else None,
            'recent_errors': [
                {'timestamp': e['timestamp'].isoformat(), 'error': e['error']}
                for e in list(metrics['errors'])
            ]
        }

    def get_fastest_model(self, models: List[str]) -> Optional[str]:
        """
        Get fastest model from a list based on recent performance.

        Args:
            models: List of model names to compare

        Returns:
            Name of fastest model, or None if no data
        """
        with self._lock:
            valid_models = []

            for model in models:
                if model in self._metrics:
                    metrics = self._metrics[model]
                    if metrics['response_times']:
                        recent_avg = sum(metrics['response_times']) / len(metrics['response_times'])
                        valid_models.append((model, recent_avg))

            if not valid_models:
                return None

            # Sort by average response time
            valid_models.sort(key=lambda x: x[1])
            return valid_models[0][0]

    def reset_metrics(self, model: Optional[str] = None):
        """
        Reset metrics.

        Args:
            model: Specific model to reset, or None for all
        """
        with self._lock:
            if model:
                if model in self._metrics:
                    del self._metrics[model]
                    del self._circuit_states[model]
                    del self._recent_failures[model]
                    del self._recent_successes[model]
                    if model in self._circuit_open_times:
                        del self._circuit_open_times[model]
                    logger.info("[PerformanceTracker] Reset metrics for %s", model)
            else:
                self._metrics.clear()
                self._circuit_states.clear()
                self._circuit_open_times.clear()
                self._recent_failures.clear()
                self._recent_successes.clear()
                logger.info("[PerformanceTracker] Reset all metrics")


# Singleton instance
performance_tracker = PerformanceTracker()

