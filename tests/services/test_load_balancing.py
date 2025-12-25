"""
Load Balancing Tests
====================

Tests to verify load balancing works correctly for:
- Auto-complete (single model requests)
- Node palette (multi-model concurrent requests)

@author MindGraph Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
import asyncio

from services.llm_service import llm_service
from services.load_balancer import LLMLoadBalancer
from agents.node_palette.circle_map_palette import CircleMapPaletteGenerator
from agents.tab_mode.tab_agent import TabAgent
from config.settings import config


class TestLoadBalancingAutoComplete:
    """Test load balancing for auto-complete feature."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Initialize service
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    async def test_deepseek_load_balanced(self):
        """Test that DeepSeek requests are load-balanced between Dashscope and Volcengine."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Track which provider was selected
        selected_providers = []
        
        # Mock the load balancer's map_model to track selections
        original_map_model = llm_service.load_balancer.map_model
        
        def track_map_model(model: str) -> str:
            """Track which provider DeepSeek maps to."""
            result = original_map_model(model)
            if model == 'deepseek':
                provider = 'dashscope' if result == 'deepseek' else 'volcengine'
                selected_providers.append(provider)
            return result
        
        llm_service.load_balancer.map_model = track_map_model
        
        try:
            # Make multiple DeepSeek requests
            for _ in range(10):
                try:
                    await llm_service.chat(
                        prompt="Say hello",
                        model='deepseek',
                        max_tokens=10
                    )
                except Exception:
                    # Ignore API errors, we're just testing routing
                    pass
            
            # Verify that both providers were used (with round-robin, should alternate)
            assert len(selected_providers) == 10, f"Expected 10 selections, got {len(selected_providers)}"
            
            # With round-robin, should see both providers
            dashscope_count = selected_providers.count('dashscope')
            volcengine_count = selected_providers.count('volcengine')
            
            assert dashscope_count > 0, "DeepSeek should route to Dashscope at least once"
            assert volcengine_count > 0, "DeepSeek should route to Volcengine at least once"
            
            print(f"DeepSeek routing: Dashscope={dashscope_count}, Volcengine={volcengine_count}")
            
        finally:
            # Restore original method
            llm_service.load_balancer.map_model = original_map_model
    
    @pytest.mark.asyncio
    async def test_qwen_always_dashscope(self):
        """Test that Qwen always routes to Dashscope (not load-balanced)."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Test mapping directly (no need to call API)
        mapped_models = []
        for _ in range(5):
            mapped = llm_service.load_balancer.map_model('qwen')
            mapped_models.append(mapped)
        
        # Verify all Qwen requests map to Dashscope (not ark-qwen)
        assert len(mapped_models) == 5, f"Expected 5 mappings, got {len(mapped_models)}"
        
        # All should be 'qwen' (Dashscope), not 'ark-qwen' (Volcengine)
        for model in mapped_models:
            assert model == 'qwen', f"Qwen should always map to 'qwen', got '{model}'"
            assert model != 'ark-qwen', "Qwen should never map to Volcengine"
        
        print(f"Qwen routing: All {len(mapped_models)} requests mapped to Dashscope (qwen)")
    
    @pytest.mark.asyncio
    async def test_kimi_always_volcengine(self):
        """Test that Kimi always routes to Volcengine (not load-balanced)."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Test mapping directly
        mapped_models = []
        for _ in range(5):
            mapped = llm_service.load_balancer.map_model('kimi')
            mapped_models.append(mapped)
        
        # Verify all Kimi requests map to Volcengine (ark-kimi)
        assert len(mapped_models) == 5, f"Expected 5 mappings, got {len(mapped_models)}"
        
        # All should be 'ark-kimi' (Volcengine endpoint)
        for model in mapped_models:
            assert model == 'ark-kimi', f"Kimi should always map to 'ark-kimi', got '{model}'"
        
        print(f"Kimi routing: All {len(mapped_models)} requests mapped to Volcengine (ark-kimi)")
    
    @pytest.mark.asyncio
    async def test_doubao_always_volcengine(self):
        """Test that Doubao always routes to Volcengine (not load-balanced)."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Test mapping directly
        mapped_models = []
        for _ in range(5):
            mapped = llm_service.load_balancer.map_model('doubao')
            mapped_models.append(mapped)
        
        # Verify all Doubao requests map to Volcengine (ark-doubao)
        assert len(mapped_models) == 5, f"Expected 5 mappings, got {len(mapped_models)}"
        
        # All should be 'ark-doubao' (Volcengine endpoint)
        for model in mapped_models:
            assert model == 'ark-doubao', f"Doubao should always map to 'ark-doubao', got '{model}'"
        
        print(f"Doubao routing: All {len(mapped_models)} requests mapped to Volcengine (ark-doubao)")


class TestLoadBalancingNodePalette:
    """Test load balancing for node palette feature."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Initialize service
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    async def test_node_palette_load_balancing(self):
        """Test that node palette applies load balancing to DeepSeek."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Test the mapping that node palette would use
        # Node palette uses: ['qwen', 'deepseek', 'kimi', 'doubao']
        logical_models = ['qwen', 'deepseek', 'kimi', 'doubao']
        
        # Apply load balancing (same as stream_progressive does)
        physical_models = [
            llm_service.load_balancer.map_model(m)
            for m in logical_models
        ]
        
        # Verify all 4 models are present
        assert len(logical_models) == 4, "Should have 4 models"
        assert len(physical_models) == 4, "Should have 4 physical models"
        
        # Verify Qwen maps to Dashscope
        qwen_idx = logical_models.index('qwen')
        assert physical_models[qwen_idx] == 'qwen', f"Qwen should map to Dashscope, got '{physical_models[qwen_idx]}'"
        
        # Verify Kimi maps to Volcengine
        kimi_idx = logical_models.index('kimi')
        assert physical_models[kimi_idx] == 'ark-kimi', f"Kimi should map to Volcengine, got '{physical_models[kimi_idx]}'"
        
        # Verify Doubao maps to Volcengine
        doubao_idx = logical_models.index('doubao')
        assert physical_models[doubao_idx] == 'ark-doubao', f"Doubao should map to Volcengine, got '{physical_models[doubao_idx]}'"
        
        # Verify DeepSeek is load-balanced (could be either)
        deepseek_idx = logical_models.index('deepseek')
        deepseek_physical = physical_models[deepseek_idx]
        assert deepseek_physical in ['deepseek', 'ark-deepseek'], \
            f"DeepSeek should map to either 'deepseek' or 'ark-deepseek', got '{deepseek_physical}'"
        
        print(f"Node Palette routing:")
        print(f"  Logical models: {logical_models}")
        print(f"  Physical models: {physical_models}")
        print(f"  DeepSeek mapped to: {deepseek_physical}")
    
    @pytest.mark.asyncio
    async def test_node_palette_deepseek_distribution(self):
        """Test that DeepSeek requests in node palette are distributed across providers."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Simulate multiple node palette batches (each batch calls map_model for deepseek)
        # In real usage, each batch would call stream_progressive which calls map_model
        deepseek_providers = []
        
        # Simulate 10 batches (each batch maps deepseek once)
        for _ in range(10):
            mapped = llm_service.load_balancer.map_model('deepseek')
            provider = 'dashscope' if mapped == 'deepseek' else 'volcengine'
            deepseek_providers.append(provider)
        
        # Verify we got selections
        assert len(deepseek_providers) == 10, f"Expected 10 selections, got {len(deepseek_providers)}"
        
        # With round-robin, should see both providers
        dashscope_count = deepseek_providers.count('dashscope')
        volcengine_count = deepseek_providers.count('volcengine')
        
        print(f"DeepSeek distribution across {len(deepseek_providers)} batches:")
        print(f"  Dashscope: {dashscope_count}")
        print(f"  Volcengine: {volcengine_count}")
        
        # With round-robin, both should be present
        assert dashscope_count > 0, "Should see Dashscope at least once"
        assert volcengine_count > 0, "Should see Volcengine at least once"


class TestLoadBalancingIntegration:
    """Integration tests for load balancing with real service calls."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Initialize service
        if not llm_service.client_manager.is_initialized():
            llm_service.initialize()
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not config.LOAD_BALANCING_ENABLED,
        reason="Load balancing not enabled in config"
    )
    async def test_load_balancer_initialized(self):
        """Test that load balancer is properly initialized."""
        assert llm_service.load_balancer is not None, "Load balancer should be initialized"
        assert llm_service.load_balancer.enabled, "Load balancer should be enabled"
        assert llm_service.load_balancer.strategy in ['weighted', 'round_robin', 'random'], \
            f"Invalid strategy: {llm_service.load_balancer.strategy}"
        
        print(f"Load balancer initialized:")
        print(f"  Strategy: {llm_service.load_balancer.strategy}")
        print(f"  Enabled: {llm_service.load_balancer.enabled}")
        print(f"  Weights: {llm_service.load_balancer.weights}")
    
    @pytest.mark.asyncio
    async def test_map_model_deepseek(self):
        """Test that map_model correctly routes DeepSeek."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Test multiple calls to see distribution
        results = []
        for _ in range(20):
            mapped = llm_service.load_balancer.map_model('deepseek')
            results.append(mapped)
        
        # Should see both providers
        dashscope_count = results.count('deepseek')
        volcengine_count = results.count('ark-deepseek')
        
        print(f"DeepSeek mapping (20 calls):")
        print(f"  'deepseek' (Dashscope): {dashscope_count}")
        print(f"  'ark-deepseek' (Volcengine): {volcengine_count}")
        
        # With round-robin, should alternate
        assert dashscope_count > 0, "Should route to Dashscope"
        assert volcengine_count > 0, "Should route to Volcengine"
    
    @pytest.mark.asyncio
    async def test_map_model_fixed_routes(self):
        """Test that fixed models (Qwen, Kimi, Doubao) use correct providers."""
        if not llm_service.load_balancer or not llm_service.load_balancer.enabled:
            pytest.skip("Load balancing not enabled")
        
        # Qwen should always map to Dashscope
        qwen_result = llm_service.load_balancer.map_model('qwen')
        assert qwen_result == 'qwen', f"Qwen should map to 'qwen', got '{qwen_result}'"
        
        # Kimi should always map to Volcengine
        kimi_result = llm_service.load_balancer.map_model('kimi')
        assert kimi_result == 'ark-kimi', f"Kimi should map to 'ark-kimi', got '{kimi_result}'"
        
        # Doubao should always map to Volcengine
        doubao_result = llm_service.load_balancer.map_model('doubao')
        assert doubao_result == 'ark-doubao', f"Doubao should map to 'ark-doubao', got '{doubao_result}'"
        
        print("Fixed model routing:")
        print(f"  Qwen → {qwen_result} (Dashscope)")
        print(f"  Kimi → {kimi_result} (Volcengine)")
        print(f"  Doubao → {doubao_result} (Volcengine)")

