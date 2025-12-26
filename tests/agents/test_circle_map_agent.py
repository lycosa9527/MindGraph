"""
Unit Tests for CircleMapAgent
==============================

Tests circle map generation functionality.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.thinking_maps.circle_map_agent import CircleMapAgent


class TestCircleMapAgent:
    """Test suite for CircleMapAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create a CircleMapAgent instance."""
        return CircleMapAgent(model='qwen')
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for circle map."""
        return {
            'content': '{"topic": "Photosynthesis", "context": ["Plants", "Sunlight", "Carbon Dioxide"]}',
            'usage': {'prompt_tokens': 50, 'completion_tokens': 30, 'total_tokens': 80}
        }
    
    @pytest.mark.asyncio
    async def test_generate_graph_success(self, agent, mock_llm_response):
        """Test successful circle map generation."""
        with patch('services.llm_service.llm_service.chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_llm_response['content']
            
            result = await agent.generate_graph(
                prompt="Define photosynthesis",
                language="en"
            )
            
            assert result['success'] is True
            assert 'spec' in result
            assert result['diagram_type'] == 'circle_map'
            assert 'topic' in result['spec']
    
    @pytest.mark.asyncio
    async def test_generate_graph_invalid_prompt(self, agent):
        """Test generation with empty prompt."""
        result = await agent.generate_graph(
            prompt="",
            language="en"
        )
        
        # Should handle empty prompt gracefully
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_generate_graph_llm_error(self, agent):
        """Test generation when LLM returns error."""
        with patch('services.llm_service.llm_service.chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("LLM API error")
            
            result = await agent.generate_graph(
                prompt="Define photosynthesis",
                language="en"
            )
            
            assert result['success'] is False
            assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_generate_graph_invalid_json(self, agent):
        """Test generation when LLM returns invalid JSON."""
        with patch('services.llm_service.llm_service.chat', new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "This is not JSON"
            
            result = await agent.generate_graph(
                prompt="Define photosynthesis",
                language="en"
            )
            
            # Should handle invalid JSON gracefully
            assert result is not None
    
    def test_validate_output_valid(self, agent):
        """Test validation of valid output."""
        output = {
            'topic': 'Photosynthesis',
            'context': ['Plants', 'Sunlight']
        }
        
        is_valid, msg = agent.validate_output(output)
        assert is_valid is True
        assert msg == ""
    
    def test_validate_output_empty(self, agent):
        """Test validation of empty output."""
        is_valid, msg = agent.validate_output({})
        assert is_valid is True  # Empty dict is valid
    
    def test_validate_output_with_error(self, agent):
        """Test validation of output with error."""
        output = {
            'error': 'Generation failed'
        }
        
        is_valid, msg = agent.validate_output(output)
        assert is_valid is False
        assert 'error' in msg.lower()
    
    def test_set_language(self, agent):
        """Test language setting."""
        agent.set_language('zh')
        assert agent.get_language() == 'zh'
        
        agent.set_language('en')
        assert agent.get_language() == 'en'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

