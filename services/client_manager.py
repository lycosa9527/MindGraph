"""
LLM Client Manager
==================

Manages lifecycle and access to all LLM client instances.
Implements singleton pattern for efficient resource usage.

IMPORTANT: This is a STATELESS service layer!
- Does NOT manage user sessions
- Does NOT store conversation history
- Does NOT maintain state between calls
- Only provides access to LLM clients

Session management remains in agents (CircleMapThinkingAgent, etc.)

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Dict, Optional, Any
from threading import Lock

from clients.llm import (
    QwenClient,
    DeepSeekClient,
    KimiClient,
    HunyuanClient
)
from clients.omni_client import OmniClient
from config.settings import config

logger = logging.getLogger(__name__)


class ClientManager:
    """
    Thread-safe manager for all LLM clients.
    Ensures only one instance of each client exists (singleton per client type).
    """
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._lock = Lock()
        self._initialized = False
        logger.info("[ClientManager] Initialized")
    
    def initialize(self) -> None:
        """
        Initialize all LLM clients.
        Called once during application startup.
        """
        if self._initialized:
            logger.warning("[ClientManager] Already initialized, skipping")
            return
        
        with self._lock:
            if self._initialized:  # Double-check after acquiring lock
                return
            
            logger.info("[ClientManager] Initializing LLM clients...")
            
            try:
                # Initialize Qwen clients (two instances for different purposes)
                self._clients['qwen'] = QwenClient('generation')
                self._clients['qwen-turbo'] = QwenClient('classification')
                self._clients['qwen-plus'] = QwenClient('generation')
                
                # Initialize other LLM clients
                self._clients['deepseek'] = DeepSeekClient()
                self._clients['kimi'] = KimiClient()
                self._clients['hunyuan'] = HunyuanClient()
                
                # Initialize Qwen Omni client (for VoiceAgent)
                self._clients['omni'] = OmniClient()
                logger.info("[ClientManager] Omni client initialized")
                
                # Optional: ChatGLM (if configured)
                # NOTE: CHATGLM_API_KEY is NOT currently in config/settings.py
                # If you need ChatGLM support, add the property to config first
                # For now, we skip ChatGLM initialization
                # if hasattr(config, 'CHATGLM_API_KEY') and config.CHATGLM_API_KEY:
                #     self._clients['chatglm'] = ChatGLMClient()
                
                self._initialized = True
                logger.info(f"[ClientManager] Initialized {len(self._clients)} LLM clients")
                
            except Exception as e:
                logger.error(f"[ClientManager] Initialization failed: {e}", exc_info=True)
                raise
    
    def get_client(self, model: str) -> Any:
        """
        Get LLM client instance by model name.
        
        Args:
            model: Model name ('qwen', 'deepseek', 'kimi', 'hunyuan', 'chatglm')
            
        Returns:
            Appropriate client instance
            
        Raises:
            ValueError: If model not supported
            RuntimeError: If clients not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                "ClientManager not initialized. Call initialize() first."
            )
        
        if model not in self._clients:
            available = ', '.join(self._clients.keys())
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Available models: {available}"
            )
        
        return self._clients[model]
    
    def get_all_clients(self) -> Dict[str, Any]:
        """Get all initialized clients."""
        if not self._initialized:
            raise RuntimeError("ClientManager not initialized")
        return self._clients.copy()
    
    def is_initialized(self) -> bool:
        """Check if client manager is initialized."""
        return self._initialized
    
    def get_available_models(self) -> list:
        """Get list of available model names."""
        return list(self._clients.keys())
    
    def cleanup(self) -> None:
        """
        Cleanup all clients (called during shutdown).
        """
        logger.info("[ClientManager] Cleaning up clients...")
        with self._lock:
            self._clients.clear()
            self._initialized = False
        logger.info("[ClientManager] Cleanup complete")
    
    @property
    def omni_client(self):
        """Get Omni client for VoiceAgent"""
        return self.get_client('omni')


# Singleton instance
client_manager = ClientManager()

