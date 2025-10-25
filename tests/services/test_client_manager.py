"""
Unit Tests for Client Manager
==============================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
from services.client_manager import client_manager


class TestClientManager:
    """Test suite for ClientManager."""
    
    def test_initialization(self):
        """Test client manager initialization."""
        if not client_manager.is_initialized():
            client_manager.initialize()
        
        assert client_manager.is_initialized()
        print("ClientManager initialized successfully")
    
    def test_get_client(self):
        """Test getting client by model name."""
        if not client_manager.is_initialized():
            client_manager.initialize()
        
        client = client_manager.get_client('qwen')
        assert client is not None
        print(f"Got client for qwen: {type(client).__name__}")
    
    def test_get_invalid_client_raises_error(self):
        """Test that invalid model raises ValueError."""
        if not client_manager.is_initialized():
            client_manager.initialize()
        
        with pytest.raises(ValueError):
            client_manager.get_client('invalid_model')
    
    def test_get_available_models(self):
        """Test getting list of available models."""
        if not client_manager.is_initialized():
            client_manager.initialize()
        
        models = client_manager.get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert 'qwen' in models
        print(f"Available models: {models}")
    
    def test_get_all_clients(self):
        """Test getting all clients."""
        if not client_manager.is_initialized():
            client_manager.initialize()
        
        clients = client_manager.get_all_clients()
        assert isinstance(clients, dict)
        assert len(clients) > 0
        assert 'qwen' in clients
        print(f"Total clients: {len(clients)}")


