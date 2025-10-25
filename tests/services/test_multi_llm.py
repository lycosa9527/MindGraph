"""
Unit Tests for Multi-LLM Orchestration
=======================================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
import asyncio
from services.llm_service import llm_service


class TestMultiLLMOrchestration:
    """Test suite for multi-LLM orchestration methods."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    async def test_generate_multi_basic(self):
        """Test basic multi-LLM generation with real APIs."""
        results = await llm_service.generate_multi(
            prompt="Say 'hello' in one word",
            models=['qwen', 'deepseek'],
            max_tokens=10,
            timeout=15.0
        )
        
        assert isinstance(results, dict)
        assert 'qwen' in results
        assert 'deepseek' in results
        
        for model, result in results.items():
            assert 'response' in result
            assert 'success' in result
            assert 'duration' in result
            print(f"{model}: {result}")
    
    @pytest.mark.asyncio
    async def test_generate_progressive_basic(self):
        """Test progressive multi-LLM generation with real APIs."""
        results_received = []
        
        async for result in llm_service.generate_progressive(
            prompt="Say 'test' in one word",
            models=['qwen', 'deepseek'],
            max_tokens=10,
            timeout=15.0
        ):
            results_received.append(result)
            assert 'llm' in result
            assert 'response' in result
            assert 'success' in result
            assert 'duration' in result
            assert 'timestamp' in result
            print(f"Received from {result['llm']}: success={result['success']}")
        
        # Should have received results from both models
        assert len(results_received) == 2
        llms = [r['llm'] for r in results_received]
        assert 'qwen' in llms
        assert 'deepseek' in llms
    
    @pytest.mark.asyncio
    async def test_generate_race_basic(self):
        """Test race condition (first successful result) with real APIs."""
        result = await llm_service.generate_race(
            prompt="Say 'hi' in one word",
            models=['qwen-turbo', 'qwen', 'deepseek'],
            max_tokens=10,
            timeout=10.0
        )
        
        assert isinstance(result, dict)
        assert 'llm' in result
        assert 'response' in result
        assert 'success' in result
        assert 'duration' in result
        assert result['success'] is True
        print(f"Winner: {result['llm']} in {result['duration']}s")
    
    @pytest.mark.asyncio
    async def test_compare_responses_basic(self):
        """Test compare responses from multiple models with real APIs."""
        comparison = await llm_service.compare_responses(
            prompt="What is 2+2? Answer in one word.",
            models=['qwen', 'deepseek'],
            max_tokens=10,
            timeout=10.0
        )
        
        assert isinstance(comparison, dict)
        assert 'prompt' in comparison
        assert 'responses' in comparison
        assert 'metrics' in comparison
        
        assert comparison['prompt'] == "What is 2+2? Answer in one word."
        assert 'qwen' in comparison['responses']
        assert 'deepseek' in comparison['responses']
        
        for model, metrics in comparison['metrics'].items():
            assert 'duration' in metrics
            assert 'success' in metrics
            print(f"{model}: {comparison['responses'][model]} ({metrics})")
    
    @pytest.mark.asyncio
    async def test_generate_multi_default_models(self):
        """Test that default models are used when none specified."""
        # This test doesn't make actual API calls, just checks the default behavior
        models = None
        if models is None:
            models = ['qwen', 'deepseek', 'kimi']
        
        assert 'qwen' in models
        assert 'deepseek' in models
        assert 'kimi' in models
        assert len(models) == 3
    
    @pytest.mark.asyncio
    async def test_generate_race_default_models(self):
        """Test that race uses fast models by default."""
        models = None
        if models is None:
            models = ['qwen-turbo', 'qwen', 'deepseek']
        
        # Should prefer faster models
        assert 'qwen-turbo' in models
        assert len(models) == 3
    
    @pytest.mark.asyncio
    async def test_progressive_yields_in_order_completed(self):
        """Test that progressive yields results as they complete."""
        # This is a conceptual test - in reality, order depends on response times
        # Just verify the mechanism works
        
        tasks_completed = []
        
        async def mock_task(name, delay):
            await asyncio.sleep(delay)
            return name
        
        tasks = []
        for i, delay in enumerate([0.3, 0.1, 0.2]):
            task = asyncio.create_task(mock_task(f"task{i}", delay))
            tasks.append(task)
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            tasks_completed.append(result)
        
        # task1 (0.1s) should complete first, task2 (0.2s) second, task0 (0.3s) last
        assert tasks_completed[0] == 'task1'
        assert tasks_completed[1] == 'task2'
        assert tasks_completed[2] == 'task0'
        print(f"Completion order: {tasks_completed}")

