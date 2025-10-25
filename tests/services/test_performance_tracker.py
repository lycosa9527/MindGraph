"""
Unit tests for PerformanceTracker
==================================

Tests performance tracking, circuit breaker, and metrics collection.

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta

from services.performance_tracker import (
    PerformanceTracker,
    CircuitState
)


class TestPerformanceTracker:
    """Test suite for PerformanceTracker."""
    
    def setup_method(self):
        """Setup for each test."""
        # Create fresh tracker for each test
        self.tracker = PerformanceTracker(
            failure_threshold=3,
            success_threshold=2,
            timeout_window=60,
            circuit_open_duration=5
        )
    
    def test_record_successful_request(self):
        """Test recording a successful request."""
        self.tracker.record_request(
            model='test-model',
            duration=1.5,
            success=True
        )
        
        metrics = self.tracker.get_metrics('test-model')
        
        assert metrics['total_requests'] == 1
        assert metrics['successful_requests'] == 1
        assert metrics['failed_requests'] == 0
        assert metrics['success_rate'] == 100.0
        assert metrics['avg_response_time'] == 1.5
        assert metrics['circuit_state'] == CircuitState.CLOSED
    
    def test_record_failed_request(self):
        """Test recording a failed request."""
        self.tracker.record_request(
            model='test-model',
            duration=2.0,
            success=False,
            error='Connection timeout'
        )
        
        metrics = self.tracker.get_metrics('test-model')
        
        assert metrics['total_requests'] == 1
        assert metrics['successful_requests'] == 0
        assert metrics['failed_requests'] == 1
        assert metrics['success_rate'] == 0.0
        assert len(metrics['recent_errors']) == 1
        assert metrics['recent_errors'][0]['error'] == 'Connection timeout'
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        model = 'failing-model'
        
        # Record failures
        for i in range(3):
            self.tracker.record_request(
                model=model,
                duration=1.0,
                success=False,
                error=f'Error {i+1}'
            )
        
        # Circuit should be open
        metrics = self.tracker.get_metrics(model)
        assert metrics['circuit_state'] == CircuitState.OPEN
        
        # Should not allow calls
        assert self.tracker.can_call_model(model) is False
    
    def test_circuit_breaker_transitions_to_half_open(self):
        """Test circuit breaker transitions to half-open after timeout."""
        model = 'recovery-model'
        
        # Open circuit
        for i in range(3):
            self.tracker.record_request(
                model=model,
                duration=1.0,
                success=False
            )
        
        assert self.tracker.get_metrics(model)['circuit_state'] == CircuitState.OPEN
        
        # Wait for circuit open duration
        time.sleep(6)  # Open duration is 5 seconds
        
        # Should transition to half-open on next check
        can_call = self.tracker.can_call_model(model)
        assert can_call is True
        
        metrics = self.tracker.get_metrics(model)
        assert metrics['circuit_state'] == CircuitState.HALF_OPEN
    
    def test_circuit_breaker_closes_after_successes(self):
        """Test circuit breaker closes after successful requests in half-open state."""
        model = 'recovery-model'
        
        # Open circuit
        for i in range(3):
            self.tracker.record_request(model=model, duration=1.0, success=False)
        
        # Transition to half-open
        time.sleep(6)
        self.tracker.can_call_model(model)
        
        # Record successful requests
        for i in range(2):  # success_threshold = 2
            self.tracker.record_request(
                model=model,
                duration=1.0,
                success=True
            )
        
        # Circuit should be closed
        metrics = self.tracker.get_metrics(model)
        assert metrics['circuit_state'] == CircuitState.CLOSED
    
    def test_response_time_tracking(self):
        """Test response time min/max/avg tracking."""
        model = 'test-model'
        
        # Record requests with different durations
        self.tracker.record_request(model=model, duration=1.0, success=True)
        self.tracker.record_request(model=model, duration=3.0, success=True)
        self.tracker.record_request(model=model, duration=2.0, success=True)
        
        metrics = self.tracker.get_metrics(model)
        
        assert metrics['min_response_time'] == 1.0
        assert metrics['max_response_time'] == 3.0
        assert metrics['avg_response_time'] == 2.0  # (1+3+2)/3
        assert metrics['recent_avg_response_time'] == 2.0
    
    def test_get_fastest_model(self):
        """Test getting fastest model from a list."""
        # Record different performance for models
        self.tracker.record_request(model='slow-model', duration=5.0, success=True)
        self.tracker.record_request(model='medium-model', duration=2.0, success=True)
        self.tracker.record_request(model='fast-model', duration=0.5, success=True)
        
        fastest = self.tracker.get_fastest_model(['slow-model', 'medium-model', 'fast-model'])
        
        assert fastest == 'fast-model'
    
    def test_get_fastest_model_with_no_data(self):
        """Test get_fastest_model returns None when no data."""
        fastest = self.tracker.get_fastest_model(['unknown-model'])
        assert fastest is None
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        model = 'test-model'
        
        # 7 successes, 3 failures = 70% success rate
        for i in range(7):
            self.tracker.record_request(model=model, duration=1.0, success=True)
        
        for i in range(3):
            self.tracker.record_request(model=model, duration=1.0, success=False)
        
        metrics = self.tracker.get_metrics(model)
        
        assert metrics['total_requests'] == 10
        assert metrics['successful_requests'] == 7
        assert metrics['failed_requests'] == 3
        assert metrics['success_rate'] == 70.0
    
    def test_recent_errors_limited(self):
        """Test that recent errors are limited to 10."""
        model = 'error-model'
        
        # Record 15 errors
        for i in range(15):
            self.tracker.record_request(
                model=model,
                duration=1.0,
                success=False,
                error=f'Error {i+1}'
            )
        
        metrics = self.tracker.get_metrics(model)
        
        # Should only keep last 10 errors
        assert len(metrics['recent_errors']) == 10
        assert metrics['recent_errors'][0]['error'] == 'Error 6'  # First kept error
        assert metrics['recent_errors'][-1]['error'] == 'Error 15'  # Last error
    
    def test_get_all_metrics(self):
        """Test getting metrics for all models."""
        # Record data for multiple models
        self.tracker.record_request(model='model1', duration=1.0, success=True)
        self.tracker.record_request(model='model2', duration=2.0, success=True)
        self.tracker.record_request(model='model3', duration=3.0, success=False)
        
        all_metrics = self.tracker.get_metrics()
        
        assert len(all_metrics) == 3
        assert 'model1' in all_metrics
        assert 'model2' in all_metrics
        assert 'model3' in all_metrics
    
    def test_reset_specific_model_metrics(self):
        """Test resetting metrics for a specific model."""
        self.tracker.record_request(model='model1', duration=1.0, success=True)
        self.tracker.record_request(model='model2', duration=2.0, success=True)
        
        # Reset model1
        self.tracker.reset_metrics('model1')
        
        all_metrics = self.tracker.get_metrics()
        
        # model1 should be gone, model2 should remain
        assert 'model1' not in all_metrics
        assert 'model2' in all_metrics
    
    def test_reset_all_metrics(self):
        """Test resetting all metrics."""
        self.tracker.record_request(model='model1', duration=1.0, success=True)
        self.tracker.record_request(model='model2', duration=2.0, success=True)
        
        # Reset all
        self.tracker.reset_metrics()
        
        all_metrics = self.tracker.get_metrics()
        
        # Should be empty
        assert len(all_metrics) == 0
    
    def test_can_call_model_initializes_for_new_model(self):
        """Test can_call_model initializes state for new models."""
        # First call to new model should return True
        assert self.tracker.can_call_model('new-model') is True
        
        # Should have initialized state
        metrics = self.tracker.get_metrics('new-model')
        assert metrics['circuit_state'] == CircuitState.CLOSED
    
    def test_last_success_and_failure_timestamps(self):
        """Test that last success and failure timestamps are recorded."""
        model = 'test-model'
        
        # Record failure
        self.tracker.record_request(model=model, duration=1.0, success=False)
        metrics = self.tracker.get_metrics(model)
        assert metrics['last_failure'] is not None
        assert metrics['last_success'] is None
        
        # Record success
        self.tracker.record_request(model=model, duration=1.0, success=True)
        metrics = self.tracker.get_metrics(model)
        assert metrics['last_success'] is not None
        assert metrics['last_failure'] is not None


@pytest.mark.asyncio
class TestPerformanceTrackerIntegration:
    """Integration tests with async operations."""
    
    def setup_method(self):
        """Setup for each test."""
        self.tracker = PerformanceTracker(
            failure_threshold=5,
            success_threshold=2,
            timeout_window=60,
            circuit_open_duration=3
        )
    
    async def test_concurrent_recording(self):
        """Test concurrent request recording."""
        async def record_requests(model: str, count: int, success: bool):
            for i in range(count):
                self.tracker.record_request(
                    model=model,
                    duration=0.1,
                    success=success
                )
                await asyncio.sleep(0.01)
        
        # Record requests concurrently
        await asyncio.gather(
            record_requests('model1', 10, True),
            record_requests('model2', 10, False),
            record_requests('model3', 10, True)
        )
        
        metrics = self.tracker.get_metrics()
        
        assert metrics['model1']['total_requests'] == 10
        assert metrics['model1']['success_rate'] == 100.0
        assert metrics['model2']['total_requests'] == 10
        assert metrics['model2']['success_rate'] == 0.0
        assert metrics['model3']['total_requests'] == 10
        assert metrics['model3']['success_rate'] == 100.0
    
    async def test_circuit_breaker_timing(self):
        """Test circuit breaker timing behavior."""
        model = 'timing-test'
        
        # Open circuit with failures
        for i in range(5):
            self.tracker.record_request(model=model, duration=1.0, success=False)
        
        assert self.tracker.get_metrics(model)['circuit_state'] == CircuitState.OPEN
        assert self.tracker.can_call_model(model) is False
        
        # Wait for circuit to transition to half-open
        await asyncio.sleep(4)  # circuit_open_duration = 3
        
        assert self.tracker.can_call_model(model) is True
        assert self.tracker.get_metrics(model)['circuit_state'] == CircuitState.HALF_OPEN
        
        # Record successes to close circuit
        for i in range(2):
            self.tracker.record_request(model=model, duration=1.0, success=True)
        
        assert self.tracker.get_metrics(model)['circuit_state'] == CircuitState.CLOSED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

