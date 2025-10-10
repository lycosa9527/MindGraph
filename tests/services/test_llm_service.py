"""
Unit Tests for LLM Service
===========================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
from services.llm_service import llm_service
from services.error_handler import LLMServiceError


class TestLLMService:
    """Test suite for LLMService."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Initialize service
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    async def test_chat_simple(self):
        """Test simple chat completion."""
        response = await llm_service.chat(
            prompt="Say hello in one word",
            model='qwen',
            max_tokens=10
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        print(f"Response: {response}")
    
    @pytest.mark.asyncio
    async def test_chat_with_system_message(self):
        """Test chat with system message."""
        response = await llm_service.chat(
            prompt="What is 2+2?",
            model='qwen',
            system_message="You are a math teacher. Answer briefly.",
            max_tokens=20
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        print(f"Response: {response}")
    
    @pytest.mark.asyncio
    async def test_invalid_model_raises_error(self):
        """Test that invalid model raises error."""
        with pytest.raises(ValueError):
            await llm_service.chat(
                prompt="Hello",
                model='invalid_model'
            )
    
    @pytest.mark.asyncio
    async def test_get_available_models(self):
        """Test getting available models."""
        models = llm_service.get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert 'qwen' in models
        print(f"Available models: {models}")
    
    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Test streaming chat completion."""
        chunks_received = []
        
        async for chunk in llm_service.chat_stream(
            prompt="Count from 1 to 3",
            model='qwen',
            max_tokens=30
        ):
            chunks_received.append(chunk)
            print(f"Chunk: {chunk}")
        
        assert len(chunks_received) > 0
        full_response = ''.join(chunks_received)
        assert len(full_response) > 0
        print(f"Full streamed response: {full_response}")
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint with real LLM."""
        # This test calls real LLM APIs
        results = await llm_service.health_check()
        assert isinstance(results, dict)
        assert 'available_models' in results
        assert len(results['available_models']) > 0
        print(f"Health check results: {results}")


