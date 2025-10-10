"""
Integration Tests with Real LLM APIs
=====================================

These tests call actual LLM APIs to verify the complete integration.
Make sure you have valid API keys configured in .env file.

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import asyncio
from services.llm_service import llm_service


class TestRealLLMIntegration:
    """Integration tests with real LLM API calls."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    async def test_qwen_basic_chat(self):
        """Test basic chat with Qwen."""
        print("\n[TEST] Testing Qwen basic chat...")
        
        response = await llm_service.chat(
            prompt="Say 'Hello' in one word",
            model='qwen',
            max_tokens=20,
            timeout=10.0
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        print(f"✅ Qwen response: {response}")
    
    @pytest.mark.asyncio
    async def test_qwen_streaming(self):
        """Test streaming with Qwen."""
        print("\n[TEST] Testing Qwen streaming...")
        
        chunks = []
        async for chunk in llm_service.chat_stream(
            prompt="Count from 1 to 3",
            model='qwen',
            max_tokens=50,
            timeout=10.0
        ):
            chunks.append(chunk)
            print(f"Chunk: {chunk}", end='', flush=True)
        
        assert len(chunks) > 0
        full_response = ''.join(chunks)
        assert len(full_response) > 0
        print(f"\n✅ Full streamed response: {full_response}")
    
    @pytest.mark.asyncio
    async def test_multi_llm_parallel(self):
        """Test parallel calls to multiple LLMs."""
        print("\n[TEST] Testing multi-LLM parallel execution...")
        
        results = await llm_service.generate_multi(
            prompt="Say 'hello' in one word",
            models=['qwen', 'deepseek'],
            max_tokens=20,
            timeout=20.0
        )
        
        assert isinstance(results, dict)
        assert len(results) > 0
        
        for model, result in results.items():
            print(f"  {model}: success={result['success']}, duration={result['duration']}s")
            if result['success']:
                print(f"    Response: {result['response'][:50]}...")
            else:
                print(f"    Error: {result['error']}")
        
        # At least one should succeed
        successes = [r for r in results.values() if r['success']]
        assert len(successes) > 0, "At least one LLM should succeed"
        print(f"✅ {len(successes)}/{len(results)} LLMs succeeded")
    
    @pytest.mark.asyncio
    async def test_progressive_streaming(self):
        """Test progressive multi-LLM streaming."""
        print("\n[TEST] Testing progressive multi-LLM streaming...")
        
        results_received = []
        
        async for result in llm_service.generate_progressive(
            prompt="Say 'test' in one word",
            models=['qwen', 'deepseek'],
            max_tokens=20,
            timeout=20.0
        ):
            results_received.append(result)
            print(f"  Received from {result['llm']}: success={result['success']}, duration={result['duration']}s")
            if result['success']:
                print(f"    Response: {result['response'][:50]}...")
        
        assert len(results_received) > 0
        successes = [r for r in results_received if r['success']]
        print(f"✅ Received {len(results_received)} results, {len(successes)} successful")
    
    @pytest.mark.asyncio
    async def test_race_fastest_response(self):
        """Test race condition - get fastest response."""
        print("\n[TEST] Testing race for fastest response...")
        
        result = await llm_service.generate_race(
            prompt="Say 'hi'",
            models=['qwen-turbo', 'qwen', 'deepseek'],
            max_tokens=20,
            timeout=15.0
        )
        
        assert result is not None
        assert 'llm' in result
        assert 'response' in result
        assert 'duration' in result
        assert result['success'] is True
        
        print(f"✅ Winner: {result['llm']} in {result['duration']}s")
        print(f"   Response: {result['response'][:50]}...")
    
    @pytest.mark.asyncio
    async def test_compare_responses(self):
        """Test comparing responses from multiple LLMs."""
        print("\n[TEST] Testing LLM response comparison...")
        
        comparison = await llm_service.compare_responses(
            prompt="What is 2+2? Answer briefly.",
            models=['qwen', 'deepseek'],
            max_tokens=30,
            timeout=15.0
        )
        
        assert isinstance(comparison, dict)
        assert 'prompt' in comparison
        assert 'responses' in comparison
        assert 'metrics' in comparison
        
        print(f"Prompt: {comparison['prompt']}")
        for model, response in comparison['responses'].items():
            metrics = comparison['metrics'][model]
            print(f"  {model}: {response[:50]}...")
            print(f"    Duration: {metrics['duration']}s, Success: {metrics['success']}")
        
        print("✅ Comparison complete")
    
    @pytest.mark.asyncio
    async def test_performance_tracking(self):
        """Test that performance is being tracked."""
        print("\n[TEST] Testing performance tracking...")
        
        # Make a few calls
        for i in range(3):
            await llm_service.chat(
                prompt=f"Say number {i+1}",
                model='qwen',
                max_tokens=10,
                timeout=10.0
            )
        
        # Get performance metrics
        metrics = llm_service.get_performance_metrics('qwen')
        
        assert isinstance(metrics, dict)
        assert metrics['total_requests'] >= 3
        assert 'avg_response_time' in metrics
        assert 'success_rate' in metrics
        assert 'circuit_state' in metrics
        
        print(f"✅ Qwen Performance Metrics:")
        print(f"   Total requests: {metrics['total_requests']}")
        print(f"   Success rate: {metrics['success_rate']}%")
        print(f"   Avg response time: {metrics['avg_response_time']}s")
        print(f"   Circuit state: {metrics['circuit_state']}")
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check with real LLM calls."""
        print("\n[TEST] Testing health check...")
        
        health = await llm_service.health_check()
        
        assert isinstance(health, dict)
        assert 'available_models' in health
        assert len(health['available_models']) > 0
        
        print(f"✅ Available models: {health['available_models']}")
        if 'rate_limiter' in health:
            print(f"   Rate limiter: {health['rate_limiter']}")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling with invalid inputs."""
        print("\n[TEST] Testing error handling...")
        
        # Test invalid model
        with pytest.raises(ValueError):
            await llm_service.chat(
                prompt="test",
                model='invalid-model'
            )
        print("✅ Invalid model raises ValueError")
        
        # Test very short timeout (should fail gracefully)
        try:
            result = await llm_service.chat(
                prompt="This is a long prompt that requires thinking time to generate a comprehensive response",
                model='qwen',
                max_tokens=100,
                timeout=0.001  # Extremely short timeout
            )
            # If it somehow succeeds, that's okay
            print("✅ Very short timeout handled")
        except Exception as e:
            print(f"✅ Timeout error handled gracefully: {type(e).__name__}")
    
    @pytest.mark.asyncio
    async def test_system_message(self):
        """Test chat with system message."""
        print("\n[TEST] Testing system message...")
        
        response = await llm_service.chat(
            prompt="What is your purpose?",
            model='qwen',
            system_message="You are a helpful math tutor. Keep responses brief.",
            max_tokens=50,
            timeout=10.0
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        print(f"✅ Response with system message: {response[:100]}...")
    
    @pytest.mark.asyncio
    async def test_temperature_control(self):
        """Test temperature parameter."""
        print("\n[TEST] Testing temperature control...")
        
        # Low temperature (more deterministic)
        response1 = await llm_service.chat(
            prompt="Say 'hello'",
            model='qwen',
            temperature=0.1,
            max_tokens=20,
            timeout=10.0
        )
        
        # High temperature (more creative)
        response2 = await llm_service.chat(
            prompt="Say 'hello'",
            model='qwen',
            temperature=0.9,
            max_tokens=20,
            timeout=10.0
        )
        
        assert isinstance(response1, str)
        assert isinstance(response2, str)
        print(f"✅ Low temp (0.1): {response1}")
        print(f"✅ High temp (0.9): {response2}")


if __name__ == '__main__':
    print("=" * 70)
    print("LLM SERVICE INTEGRATION TESTS - REAL API CALLS")
    print("=" * 70)
    pytest.main([__file__, '-v', '-s'])

